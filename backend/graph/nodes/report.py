"""Report node for LangGraph workflow.

This module implements the report node that synthesizes retrieved information
into a final research report using the LLM provider.
"""

import time
from typing import Any

from backend.core.interfaces import LLMProvider
from backend.graph.state import ResearchState
from backend.utils.logging_config import get_logger
from backend.utils.quality_assessment import (
    calculate_confidence_score,
    detect_contradictions,
    assess_evidence_sufficiency,
    enhance_reference_metadata,
)
from backend.utils.query_classifier import classify_query, get_validation_thresholds
from backend.utils.confidence_calculator import calculate_confidence_from_sources
from backend.utils.evaluation import get_evaluator

logger = get_logger(__name__)


def validate_citations(report: str, search_results: list[dict[str, Any]], research_papers: list[dict[str, Any]]) -> tuple[bool, str, float]:
    """Validate citations in the report and calculate citation quality score.

    Args:
        report: Generated report content
        search_results: Web search results
        research_papers: Academic papers

    Returns:
        Tuple of (is_valid, reason, citation_quality_score)
    """
    import re

    # Extract all citations from report
    citation_pattern = r'\[(\d+)\]'
    citations = re.findall(citation_pattern, report)

    if not citations:
        return True, "No citations found (acceptable if no sources)", 0.0

    # Check for sequential numbering
    citation_numbers = [int(c) for c in citations]
    expected_numbers = list(range(1, max(citation_numbers) + 1))
    if set(citation_numbers) != set(expected_numbers):
        return False, f"Citation numbering not sequential: found {citation_numbers}, expected {expected_numbers}", 0.0

    # Check for duplicate citations
    if len(citation_numbers) != len(set(citation_numbers)):
        return False, "Duplicate citations found in report", 0.0

    # Check that all citations reference existing sources
    total_sources = len(search_results) + len(research_papers)
    max_citation = max(citation_numbers) if citation_numbers else 0
    if max_citation > total_sources:
        return False, f"Citation [{max_citation}] references non-existent source (only {total_sources} sources available)", 0.0

    # Check that all sources are referenced at least once
    if total_sources > 0:
        referenced_sources = set(citation_numbers)
        expected_references = set(range(1, total_sources + 1))
        missing_references = expected_references - referenced_sources
        if missing_references:
            return False, f"Sources not referenced: {sorted(missing_references)}", 0.0

    # Calculate citation quality score based on source reliability and diversity
    citation_quality_score = _calculate_citation_quality_score(citation_numbers, search_results, research_papers)

    return True, "Citation validation passed", citation_quality_score


def _calculate_citation_quality_score(
    citation_numbers: list[int],
    search_results: list[dict[str, Any]],
    research_papers: list[dict[str, Any]],
) -> float:
    """Calculate citation quality score based on source reliability and diversity.

    Args:
        citation_numbers: Citation numbers used in report
        search_results: Web search results
        research_papers: Academic papers

    Returns:
        Citation quality score between 0 and 1
    """
    if not citation_numbers:
        return 0.0

    all_sources = search_results + research_papers
    if not all_sources:
        return 0.0

    # Get cited sources
    cited_sources = []
    for citation_num in citation_numbers:
        if citation_num <= len(all_sources):
            cited_sources.append(all_sources[citation_num - 1])

    if not cited_sources:
        return 0.0

    # Calculate reliability score
    reliability_scores = []
    for source in cited_sources:
        reliability = source.get("reliability_score", 0.5)
        reliability_scores.append(reliability)

    avg_reliability = sum(reliability_scores) / len(reliability_scores) if reliability_scores else 0.0

    # Calculate provider diversity
    provider_types = set()
    for source in cited_sources:
        source_type = source.get("source_type", "web")
        provider_types.add(source_type)

    provider_diversity = len(provider_types) / 3.0  # Max 3 provider types

    # Calculate domain diversity
    domains = set()
    for source in cited_sources:
        url = source.get("url", "")
        if url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
                domains.add(domain)
            except Exception:
                pass

    domain_diversity = min(len(domains) / len(cited_sources), 1.0) if cited_sources else 0.0

    # Combined citation quality score
    citation_quality = (
        (avg_reliability * 0.5) +
        (provider_diversity * 0.3) +
        (domain_diversity * 0.2)
    )

    return citation_quality


def detect_meta_commentary(report: str) -> tuple[bool, str]:
    """Detect meta-commentary in LLM output before expensive validation.

    This is a cheap early detection to avoid full validation on obviously
    invalid outputs like "we are writing a markdown report..."

    Args:
        report: Generated report content

    Returns:
        Tuple of (has_meta_commentary, reason)
    """
    if not report or len(report.strip()) < 10:
        return True, "Report is empty or too short"

    report_lower = report.lower()

    # Meta-commentary patterns that indicate the model is talking about the task
    # instead of doing it
    meta_patterns = [
        "we are writing",
        "the user says",
        "instructions:",
        "the task is",
        "here is the report",
        "i will provide",
        "we need to",
        "let me think",
        "i am going to",
        "we are generating",
        "the system instructed",
        "the model was asked",
        "the request was",
        "to fulfill the request",
        "to complete the task",
        "as requested",
        "per the request",
        "according to the user",
        "the user provided",
        "given the prompt",
        "given the instructions",
        "step by step",
        "reasoning:",
        "analysis:",
        "thoughts:",
        "planning:",
        "internal:",
        "hidden:",
        "secret:",
        "system prompt",
        "assistant",
        "the prompt",
        "we are asked",
        "based on the instructions",
        "the user requested",
        "the user wants",
    ]

    # Check for meta-commentary in the first 200 characters (most likely location)
    first_200 = report_lower[:200]
    for pattern in meta_patterns:
        if pattern in first_200:
            return True, f"Meta-commentary detected: '{pattern}'"

    return False, ""


def validate_report_output(report: str) -> tuple[bool, str]:
    """Validate report output for prompt leakage and structure compliance.

    Args:
        report: Generated report content

    Returns:
        Tuple of (is_valid, reason)
    """
    if not report or len(report.strip()) < 10:
        return False, "Report is empty or too short"

    # Check if report starts with Executive Summary
    if not report.strip().startswith("## Executive Summary"):
        return False, "Report does not start with '## Executive Summary'"

    # Validate required sections exist
    required_sections = [
        "## Executive Summary",
        "## Key Findings",
        "## Detailed Analysis",
        "## Evidence",
        "## References",
    ]

    for section in required_sections:
        if section not in report:
            return False, f"Missing required section: '{section}'"

    # Check for prompt leakage indicators - focused list (meta-commentary already checked)
    leakage_phrases = [
        "the problem states",
        "based on the prompt",
        "the instructions say",
        "as instructed",
        "following the instructions",
        "according to the prompt",
        "the prompt asks",
        "we are given",
        "let me re-read",
        "the prompt said",
        "the instructions stated",
        "the problem said",
        "the system instructed",
        "the model was asked",
        "the request was",
        "internal:",
        "hidden:",
        "secret:",
        "system prompt",
    ]

    report_lower = report.lower()
    for phrase in leakage_phrases:
        if phrase in report_lower:
            return False, f"Prompt leakage detected: '{phrase}'"

    # Check for reasoning indicators - expanded list
    reasoning_phrases = [
        "step 1:",
        "step 2:",
        "step 3:",
        "first,",
        "secondly,",
        "thirdly,",
        "finally,",
        "in conclusion,",
        "to summarize,",
        "in summary,",
        "next,",
        "then,",
        "after that,",
        "subsequently,",
        "furthermore,",
        "moreover,",
        "additionally,",
        "lastly,",
        "ultimately,",
    ]

    for phrase in reasoning_phrases:
        if phrase in report_lower:
            return False, f"Reasoning indicator detected: '{phrase}'"

    return True, "Validation passed"


def post_process_report(report: str) -> str:
    """Safely normalize LLM output before validation.

    Allowed operations:
    - Remove accidental leading/trailing whitespace
    - Remove harmless markdown fences
    - Locate first "## Executive Summary" when model adds harmless intro
    - Normalize duplicated blank lines

    Args:
        report: Generated report content

    Returns:
        Normalized report content
    """
    if not report:
        return report

    # Strip leading/trailing whitespace
    report = report.strip()

    # Remove markdown code fences if present
    if report.startswith("```"):
        lines = report.split("\n")
        if lines[0].startswith("```"):
            # Remove first line (opening fence)
            lines = lines[1:]
            # Remove last line if it's a closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            report = "\n".join(lines).strip()

    # If report doesn't start with ## Executive Summary, try to locate it
    if not report.startswith("## Executive Summary"):
        # Find the first occurrence of ## Executive Summary
        idx = report.find("## Executive Summary")
        if idx != -1:
            # Extract from that point onward
            report = report[idx:].strip()

    # Normalize duplicated blank lines (more than 2 consecutive)
    import re
    report = re.sub(r"\n{3,}", "\n\n", report)

    return report


def generate_deterministic_fallback(user_query: str, search_results: list[dict[str, Any]], research_papers: list[dict[str, Any]]) -> str:
    """Generate a deterministic fallback report using retrieved evidence.

    This function creates a useful report based strictly on the retrieved sources
    without any LLM generation. It preserves citations and structure.

    Args:
        user_query: The user's research query
        search_results: Web search results
        research_papers: Academic papers

    Returns:
        Deterministic fallback report with proper structure and citations
    """
    all_sources = search_results + research_papers

    if not all_sources:
        return f"""## Executive Summary

Unable to generate a valid report for: {user_query}

## Evidence

No sources were retrieved for this query.

## References

No sources available."""

    # Extract key information from sources
    key_findings = []
    evidence_details = []

    for i, source in enumerate(all_sources[:5], 1):  # Limit to top 5 sources
        title = source.get("title", "Unknown")
        snippet = source.get("snippet", source.get("abstract", ""))
        url = source.get("url", source.get("pdf_url", ""))

        key_findings.append(f"- {title} [{i}]")
        evidence_details.append(f"**Source [{i}]**: {title}")
        if snippet:
            evidence_details.append(f"{snippet[:200]}...")
        if url:
            evidence_details.append(f"URL: {url}")
        evidence_details.append("")

    # Build executive summary
    executive_summary = f"Based on {len(all_sources)} retrieved sources, this report addresses: ${user_query}."

    # Build the fallback report
    report = f"""## Executive Summary

{executive_summary}

## Key Findings

{chr(10).join(key_findings)}

## Detailed Analysis

The retrieved sources provide information about {user_query}. The evidence comes from {len(search_results)} web sources and {len(research_papers)} academic papers.

## Evidence

{chr(10).join(evidence_details)}

## References

"""

    # Add numbered references
    for i, source in enumerate(all_sources[:5], 1):
        title = source.get("title", "Unknown")
        url = source.get("url", source.get("pdf_url", ""))
        report += f"[{i}] {title}\n"
        if url:
            report += f"    URL: {url}\n"
    return report


def append_references_section(report: str, search_results: list[dict[str, Any]], research_papers: list[dict[str, Any]]) -> str:
    """Append numbered references section to the report with enhanced metadata.

    Args:
        report: Generated report content
        search_results: Ranked web search results
        research_papers: Ranked academic papers

    Returns:
        Report with references section appended
    """
    if not search_results and not research_papers:
        return report

    references = []

    # Add web search results with enhanced metadata
    for i, result in enumerate(search_results[:2], 1):
        enhanced = enhance_reference_metadata(result, "web")
        ref = f"[{i}] {enhanced.get('title', 'N/A')}"
        if enhanced.get('url'):
            ref += f"\n    URL: {enhanced.get('url')}"
        if enhanced.get('reliability_score'):
            ref += f"\n    Reliability: {enhanced.get('reliability_score'):.2f}"
        references.append(ref)

    # Add academic papers with enhanced metadata
    ref_offset = len(search_results[:2])
    for i, paper in enumerate(research_papers[:1], 1):
        enhanced = enhance_reference_metadata(paper, "academic")
        ref_num = ref_offset + i
        ref = f"[{ref_num}] {enhanced.get('title', 'N/A')}"
        if enhanced.get('entry_id'):
            ref += f"\n    arXiv: {enhanced.get('entry_id')}"
        if enhanced.get('pdf_url'):
            ref += f"\n    PDF: {enhanced.get('pdf_url')}"
        if enhanced.get('reliability_score'):
            ref += f"\n    Reliability: {enhanced.get('reliability_score'):.2f}"
        references.append(ref)

    # Append references section if not already present
    if "## References" not in report:
        report += "\n\n## References\n\n" + "\n\n".join(references)

    return report


async def report_node(
    state: ResearchState,
    llm_provider: LLMProvider,
) -> ResearchState:
    """Report node - synthesizes findings into a final research report.

    This node uses the LLM provider to generate a comprehensive research report
    based on the user query, research plan, search results, and academic papers.

    Args:
        state: Current workflow state containing research data
        llm_provider: LLM provider instance (dependency injection)

    Returns:
        Updated state with report and final_answer
    """
    start_time = time.time()

    request_id = state.get("request_id")
    user_query = state.get("user_query", "")
    search_results = state.get("search_results", [])
    research_papers = state.get("research_papers", [])

    # Classify query type for adaptive validation
    query_type = classify_query(user_query)

    # Get adaptive validation thresholds based on query type
    thresholds = get_validation_thresholds(query_type)

    logger.info(
        f"Report node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
            "query_type": query_type,
            "validation_thresholds": thresholds,
            "num_search_results": len(search_results),
            "num_papers": len(research_papers),
        },
    )

    # Load fusion metrics from research node
    research_metrics = state.get("metadata", {}).get("research_metrics", {})
    diversity_score = research_metrics.get("diversity_score", 0.0)
    agreement_score = research_metrics.get("agreement_score", 0.0)

    # Check if there's any relevant evidence with validation gate
    has_web_results = len(search_results) > 0
    has_papers = len(research_papers) > 0

    # Calculate evidence quality metrics for validation
    evidence_sufficient = False
    evidence_reason = ""
    average_relevance = 0.0
    average_quality = 0.0
    average_semantic_similarity = 0.0
    confidence_score = 0.0
    confidence_level = "Low"
    contradiction_score = 0.0
    coverage_score = 0.0
    validation_start = time.time()

    if has_web_results or has_papers:
        # Calculate average scores
        all_sources = search_results + research_papers
        if all_sources:
            # Use overall_score as the canonical relevance signal from hybrid scoring model
            # Fall back to relevance_score for backward compatibility with older providers
            relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
            qualities = [s.get("quality_score", 0) for s in all_sources]
            semantic_sims = [s.get("semantic_similarity", 0) for s in all_sources]
            average_relevance = sum(relevances) / len(relevances)
            average_quality = sum(qualities) / len(qualities)
            average_semantic_similarity = sum(semantic_sims) / len(semantic_sims)

        # Calculate agreement score between sources before confidence
        if len(all_sources) >= 2:
            from backend.utils.semantic_similarity import compute_source_agreement

            source_texts = []
            for source in all_sources:
                if "abstract" in source:
                    source_texts.append(source["abstract"])
                elif "snippet" in source:
                    source_texts.append(source["snippet"])

            if len(source_texts) >= 2:
                agreements = []
                for i in range(len(source_texts)):
                    for j in range(i + 1, len(source_texts)):
                        agreements.append(compute_source_agreement(source_texts[i], source_texts[j]))
                if agreements:
                    agreement_score = sum(agreements) / len(agreements)

            confidence_result = calculate_confidence_from_sources(
                sources=all_sources,
                agreement_score=agreement_score,
                diversity_score=diversity_score,
            )
            confidence_score = confidence_result["confidence_score"]
            confidence_level = confidence_result["confidence_level"]

        # Use quality assessment to determine sufficiency
        from backend.utils.quality_assessment import (
            assess_evidence_sufficiency,
            detect_contradictions,
        )

        sufficiency_data = assess_evidence_sufficiency(
            search_results,
            research_papers,
            user_query,
        )
        evidence_sufficient = sufficiency_data["is_sufficient"]
        evidence_reason = sufficiency_data["reason"]

        # Calculate contradiction score
        contradiction_data = detect_contradictions(search_results, research_papers)
        # Calculate contradiction score from the list of contradictions
        contradiction_score = min(1.0, len(contradiction_data) / max(len(all_sources), 1))

        # Calculate coverage score (how well sources cover the query)
        coverage_score = min(1.0, len(all_sources) / 5.0)  # Normalized by expecting 5 sources

        logger.info(
            f"Evidence validation gate",
            extra={
                "request_id": request_id,
                "has_web_results": has_web_results,
                "has_papers": has_papers,
                "average_relevance": average_relevance,
                "average_quality": average_quality,
                "average_semantic_similarity": average_semantic_similarity,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
                "agreement_score": agreement_score,
                "contradiction_score": contradiction_score,
                "coverage_score": coverage_score,
                "evidence_sufficient": evidence_sufficient,
                "evidence_reason": evidence_reason,
            },
        )

    # Adaptive evidence validation gate - use thresholds based on query type
    MIN_AVERAGE_RELEVANCE = thresholds["min_relevance"]
    MIN_CONFIDENCE_SCORE = thresholds["min_confidence"]
    MIN_USEFUL_SOURCES = thresholds["min_sources"]
    MIN_SEMANTIC_SIMILARITY = thresholds["min_similarity"]
    MIN_AGREEMENT_SCORE = 0.30
    MAX_CONTRADICTION_SCORE = 0.20
    MIN_COVERAGE_SCORE = 0.40

    validation_passed = True
    validation_reason = ""

    if not has_web_results and not has_papers:
        validation_passed = False
        validation_reason = "No sources retrieved"
    elif len(search_results) + len(research_papers) < MIN_USEFUL_SOURCES:
        validation_passed = False
        validation_reason = f"Insufficient high-quality sources ({len(search_results) + len(research_papers)} < {MIN_USEFUL_SOURCES})"
    elif average_relevance < MIN_AVERAGE_RELEVANCE:
        validation_passed = False
        validation_reason = f"Average relevance ({average_relevance:.2f}) below threshold ({MIN_AVERAGE_RELEVANCE})"
    elif average_semantic_similarity < MIN_SEMANTIC_SIMILARITY:
        validation_passed = False
        validation_reason = f"Average semantic similarity ({average_semantic_similarity:.2f}) below threshold ({MIN_SEMANTIC_SIMILARITY})"
    elif confidence_score < MIN_CONFIDENCE_SCORE:
        validation_passed = False
        validation_reason = f"Confidence score ({confidence_score:.2f}) below threshold ({MIN_CONFIDENCE_SCORE})"
    elif agreement_score < MIN_AGREEMENT_SCORE:
        validation_passed = False
        validation_reason = f"Agreement score ({agreement_score:.2f}) below threshold ({MIN_AGREEMENT_SCORE})"
    elif contradiction_score > MAX_CONTRADICTION_SCORE:
        validation_passed = False
        validation_reason = f"Contradiction score ({contradiction_score:.2f}) above threshold ({MAX_CONTRADICTION_SCORE})"
    elif coverage_score < MIN_COVERAGE_SCORE:
        validation_passed = False
        validation_reason = f"Coverage score ({coverage_score:.2f}) below threshold ({MIN_COVERAGE_SCORE})"

    validation_ms = (time.time() - validation_start) * 1000

    if not validation_passed:
        # Evidence insufficient - generate graceful response without LLM call
        logger.warning(
            f"Evidence validation failed - blocking LLM call",
            extra={
                "request_id": request_id,
                "user_query": user_query,
                "num_search_results": len(search_results),
                "num_papers": len(research_papers),
                "average_relevance": average_relevance,
                "average_semantic_similarity": average_semantic_similarity,
                "confidence_score": confidence_score,
                "agreement_score": agreement_score,
                "contradiction_score": contradiction_score,
                "coverage_score": coverage_score,
                "validation_reason": validation_reason,
            },
        )

        no_evidence_report = f"""## Executive Summary

The system searched for information on: "{user_query}"

## Evidence Assessment

The retrieval system found {len(search_results)} web sources and {len(research_papers)} academic papers, but the evidence did not meet the quality thresholds for this type of query ({query_type}).

**Validation Details:**
- Average relevance: {average_relevance:.2f} (threshold: {MIN_AVERAGE_RELEVANCE:.2f})
- Average semantic similarity: {average_semantic_similarity:.2f} (threshold: {MIN_SEMANTIC_SIMILARITY:.2f})
- Confidence score: {confidence_score:.2f} (threshold: {MIN_CONFIDENCE_SCORE:.2f})
- Sources available: {len(search_results) + len(research_papers)} (required: {MIN_USEFUL_SOURCES})

**Rejection Reason:** {validation_reason}

## Recommendations

For better results, try:
- Using more specific keywords related to your topic
- Rephrasing your question with different terminology
- For technical queries: include "tutorial", "guide", or "documentation"
- For definitions: use "What is X" format
- For research: specify "research", "study", or "analysis"
"""

        execution_time_ms = (time.time() - start_time) * 1000

        updated_state = state.copy()
        updated_state["report"] = {
            "content": no_evidence_report,
            "sources": {
                "web_results": 0,
                "papers": 0,
            },
            "generated_at": time.time(),
            "quality_metrics": {
                "confidence_level": "Low",
                "confidence_score": 0.0,
                "contradictions_detected": 0,
                "evidence_sufficient": False,
                "evidence_reason": "No relevant evidence found",
            },
        }
        updated_state["final_answer"] = no_evidence_report
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "report",
            "action": "no_evidence_found",
            "status": "completed",
            "execution_time_ms": execution_time_ms,
            "report_length": len(no_evidence_report),
        })

        logger.info(
            f"Report node completed - No evidence response generated",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time_ms,
                "report_length": len(no_evidence_report),
                "response_type": "no_evidence",
            },
        )

        return updated_state

    # Build the prompt with improved structure and references (optimized with quality features)
    prompt_build_start = time.time()
    prompt_parts = [
        f"Question: {user_query}",
        "",
    ]

    # Add evidence summary (for internal use only, not exposed in final report)
    evidence_summary = f"Evidence Summary: {len(search_results) + len(research_papers)} sources analyzed from multiple providers. Confidence: {confidence_level} ({confidence_score:.2f})."

    # Add web search results with reference numbers
    if search_results:
        prompt_parts.append("Sources:")
        for i, result in enumerate(search_results[:2], 1):
            prompt_parts.append(f"[{i}] {result.get('title', 'N/A')}")
            prompt_parts.append(f"    {result.get('snippet', 'N/A')[:60]}...")
        prompt_parts.append("")

    # Add research papers with reference numbers
    if research_papers:
        ref_offset = len(search_results[:2]) if search_results else 0
        for i, paper in enumerate(research_papers[:1], 1):
            ref_num = ref_offset + i
            prompt_parts.append(f"[{ref_num}] {paper.get('title', 'N/A')}")
            prompt_parts.append(f"    {paper.get('abstract', 'N/A')[:80]}...")
        prompt_parts.append("")

    # Calculate quality metrics
    confidence_metrics = calculate_confidence_score(search_results, research_papers)
    contradictions = detect_contradictions(search_results, research_papers)
    evidence_assessment = assess_evidence_sufficiency(search_results, research_papers, user_query)

    # Add quality context to prompt
    prompt_parts.extend([
        f"Confidence Level: {confidence_metrics['overall_confidence']}",
        f"Evidence Status: {evidence_assessment['reason']}",
        "",
    ])

    # Add contradiction warning if detected
    if contradictions:
        prompt_parts.append("Note: Some sources may have conflicting information. Present multiple viewpoints if applicable.")
        prompt_parts.append("")

    prompt_parts.extend([
        "Generate the final research report.",
        "Return ONLY the Markdown report.",
        "Do not discuss these instructions.",
        "Do not describe your role.",
        "Do not explain how the report was generated.",
        "Use only the supplied evidence.",
        "Use citations [1], [2], etc.",
        "",
        "Report structure:",
        "## Executive Summary",
        "## Key Findings",
        "## Detailed Analysis",
        "## Evidence",
        "## References",
        "",
        "Start immediately with ## Executive Summary.",
    ])

    prompt = "\n".join(prompt_parts)
    prompt_build_ms = (time.time() - prompt_build_start) * 1000

    # Log detailed prompt construction for debugging
    logger.info(
        "Report prompt construction details",
        extra={
            "request_id": request_id,
            "prompt_build_ms": prompt_build_ms,
            "system_instructions_chars": len("\n".join(prompt_parts[:6])),
            "user_query_chars": len(user_query),
            "num_web_results_in_prompt": len([p for p in prompt_parts if "Sources:" in p or p.startswith(("1.", "2."))]),
            "num_papers_in_prompt": len([p for p in prompt_parts if "arXiv" in p or p.startswith(("1.", "2."))]),
            "structure_rules_chars": len("\n".join(prompt_parts[-9:])),
            "total_prompt_chars": len(prompt),
            "total_prompt_words": len(prompt.split()),
            "max_tokens": 384,
            "confidence_level": confidence_metrics['overall_confidence'],
            "confidence_score": confidence_metrics['confidence_score'],
            "contradictions_detected": len(contradictions),
            "evidence_sufficient": evidence_assessment['is_sufficient'],
        },
    )

    try:
        # Generate report using LLM provider with timeout
        llm_report_start = time.time()
        import asyncio
        from backend.config.config import settings

        report_generation_timeout = settings.ollama_report_timeout  # Use report-specific timeout

        try:
            report = await asyncio.wait_for(
                llm_provider.generate(
                    prompt=prompt,
                    temperature=settings.ollama_report_temperature,  # Use configured temperature
                    max_tokens=settings.ollama_report_max_tokens,  # Use configured max tokens
                    request_id=request_id,
                    function_name="report",
                ),
                timeout=report_generation_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Report generation timeout after {report_generation_timeout}s",
                extra={
                    "request_id": request_id,
                    "timeout_seconds": report_generation_timeout,
                },
            )
            # Use deterministic fallback on timeout
            report_with_refs = generate_deterministic_fallback(user_query, search_results, research_papers)
            report_fallback_used = True
            validation_passed = True
            validation_reason = "Report generation timeout - used deterministic fallback"
            llm_report_ms = report_generation_timeout * 1000
            execution_time_ms = (time.time() - start_time) * 1000

            # Track metrics for timeout case
            try:
                evaluator = get_evaluator()
                evaluator.track_answer_metrics(
                    structure_score=1.0,
                    leakage_score=1.0,
                    hallucination_risk=1.0 - confidence_score,
                    citation_score=0.0,
                    request_id=request_id,
                    report_generation_time_ms=execution_time_ms,
                    citation_count=0,
                    contradiction_count=len(contradictions),
                    regeneration_count=0,
                    final_confidence=confidence_score,
                )
            except Exception as e:
                logger.warning(f"Failed to track answer metrics: {e}")

            updated_state = state.copy()
            updated_state["report"] = {
                "content": report_with_refs,
                "sources": {
                    "web_results": len(search_results),
                    "papers": len(research_papers),
                },
                "generated_at": time.time(),
                "quality_metrics": {
                    "confidence_level": confidence_level,
                    "confidence_score": confidence_score,
                    "contradictions_detected": len(contradictions),
                    "evidence_sufficient": evidence_sufficient,
                    "evidence_reason": evidence_reason,
                },
            }
            updated_state["final_answer"] = report_with_refs
            updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
            updated_state["intermediate_steps"].append({
                "node": "report",
                "action": "timeout_fallback",
                "status": "completed",
                "execution_time_ms": execution_time_ms,
                "report_length": len(report_with_refs),
                "fallback_used": True,
            })

            logger.info(
                f"Report node completed with timeout fallback",
                extra={
                    "request_id": request_id,
                    "execution_time_ms": execution_time_ms,
                    "report_length": len(report_with_refs),
                    "fallback_used": True,
                },
            )

            return updated_state

        llm_report_ms = (time.time() - llm_report_start) * 1000

        # Post-process report before validation
        report = post_process_report(report)
        report_with_refs = append_references_section(report, search_results, research_papers)

        # Validate citations
        citations_valid, citations_reason, citation_quality_score = validate_citations(report_with_refs, search_results, research_papers)

        # Cheap meta-commentary detection before full validation
        has_meta_commentary, meta_reason = detect_meta_commentary(report)
        if has_meta_commentary:
            logger.warning(
                f"Meta-commentary detected in initial generation: {meta_reason}",
                extra={
                    "request_id": request_id,
                    "meta_reason": meta_reason,
                },
            )
            validation_passed = False
            validation_reason = f"Meta-commentary: {meta_reason}"
        else:
            # Full validation only if no meta-commentary
            validation_passed, validation_reason = validate_report_output(report_with_refs)

        # Combine validation results
        if not citations_valid:
            validation_passed = False
            validation_reason = f"Citation validation failed: {citations_reason}"

        # Strict limit: 1 initial generation + 1 regeneration = max 2 LLM calls
        max_regenerations = 1  # Only 1 regeneration allowed
        regeneration_count = 0
        report_generation_attempts = 1
        meta_commentary_detected = has_meta_commentary
        report_fallback_used = False

        while not validation_passed and regeneration_count < max_regenerations:
            regeneration_count += 1
            report_generation_attempts += 1
            regeneration_start = time.time()
            logger.warning(
                f"Report validation failed (attempt {regeneration_count}/{max_regenerations}): {validation_reason}. Regenerating.",
                extra={
                    "request_id": request_id,
                    "validation_reason": validation_reason,
                    "regeneration_attempt": regeneration_count,
                },
            )

            # Simplified regeneration prompt
            simplified_prompt = f"""Question: {user_query}

Sources:
{chr(10).join([f"[{i}] {r.get('title', 'N/A')}" for i, r in enumerate(search_results[:2], 1)])}

Generate the final research report.
Return ONLY the Markdown report.
Start immediately with ## Executive Summary.

Report structure:
## Executive Summary
## Key Findings
## Detailed Analysis
## Evidence
## References"""

            try:
                llm_regeneration_start = time.time()
                report = await asyncio.wait_for(
                    llm_provider.generate(
                        prompt=simplified_prompt,
                        temperature=settings.ollama_report_temperature,  # Use configured temperature
                        max_tokens=settings.ollama_report_max_tokens,  # Use configured max tokens
                        request_id=request_id,
                        function_name="report",
                    ),
                    timeout=report_generation_timeout,
                )
                llm_regeneration_ms = (time.time() - llm_regeneration_start) * 1000

                # Post-process regenerated report
                report = post_process_report(report)
                report_with_refs = append_references_section(report, search_results, research_papers)

                # Check for meta-commentary again
                has_meta_commentary, meta_reason = detect_meta_commentary(report)
                if has_meta_commentary:
                    meta_commentary_detected = True
                    logger.warning(
                        f"Meta-commentary detected in regeneration: {meta_reason}",
                        extra={
                            "request_id": request_id,
                            "meta_reason": meta_reason,
                        },
                    )
                    validation_passed = False
                    validation_reason = f"Meta-commentary in regeneration: {meta_reason}"
                else:
                    # Full validation
                    validation_passed, validation_reason = validate_report_output(report_with_refs)
                    citations_valid, citations_reason, citation_quality_score = validate_citations(report_with_refs, search_results, research_papers)
                    if not citations_valid:
                        validation_passed = False
                        validation_reason = f"Citation validation failed: {citations_reason}"

            except Exception as e:
                logger.error(
                    f"Regeneration attempt {regeneration_count} failed: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "error": str(e),
                        "regeneration_attempt": regeneration_count,
                    },
                )
                validation_passed = False
                validation_reason = f"Regeneration failed: {str(e)}"

            regeneration_ms = (time.time() - regeneration_start) * 1000

        # If validation still failed after 1 regeneration, use deterministic fallback
        if not validation_passed:
            logger.warning(
                f"Validation failed after {report_generation_attempts} attempts. Using deterministic fallback.",
                extra={
                    "request_id": request_id,
                    "validation_reason": validation_reason,
                    "report_generation_attempts": report_generation_attempts,
                },
            )
            report_with_refs = generate_deterministic_fallback(user_query, search_results, research_papers)
            report_fallback_used = True
            validation_passed = True
            validation_reason = "Used deterministic fallback"
        else:
            regeneration_ms = 0

        execution_time_ms = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Track answer metrics
        try:
            evaluator = get_evaluator()
            # Calculate citation count from report
            import re
            citation_count = len(re.findall(r'\[(\d+)\]', report_with_refs))

            evaluator.track_answer_metrics(
                structure_score=1.0 if validation_passed else 0.0,
                leakage_score=1.0 if "prompt leakage" not in validation_reason.lower() else 0.0,
                hallucination_risk=1.0 - confidence_score,  # Inverse of confidence
                citation_score=citation_quality_score,
                request_id=request_id,
                report_generation_time_ms=execution_time_ms,
                citation_count=citation_count,
                contradiction_count=len(contradictions),
                regeneration_count=regeneration_count,
                final_confidence=confidence_score,
            )
        except Exception as e:
            logger.warning(f"Failed to track answer metrics: {e}")

        logger.info(
            f"Report node completed successfully",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time_ms,
                "validation_ms": validation_ms,
                "prompt_build_ms": prompt_build_ms,
                "llm_report_ms": llm_report_ms,
                "regeneration_ms": regeneration_ms,
                "regeneration_count": regeneration_count,
                "report_generation_attempts": report_generation_attempts,
                "meta_commentary_detected": meta_commentary_detected,
                "report_fallback_used": report_fallback_used,
                "prompt_length": len(prompt),
                "report_length": len(report_with_refs),
                "sources_received": len(search_results),
                "sources_used_in_prompt": len(search_results[:2]) if search_results else 0,
                "papers_received": len(research_papers),
                "papers_used_in_prompt": len(research_papers[:1]) if research_papers else 0,
                "references_appended": True,
                "validation_passed": validation_passed,
                "validation_reason": validation_reason,
                "generation_attempt": 1,
                "citation_validation_status": citations_valid,
                "citation_validation_reason": citations_reason,
                "citation_quality_score": citation_quality_score,
                "average_relevance": average_relevance,
                "average_quality": average_quality,
                "average_semantic_similarity": average_semantic_similarity,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
                "agreement_score": agreement_score,
                "contradiction_score": contradiction_score,
                "coverage_score": coverage_score,
                "overall_quality_score": (average_relevance + average_quality + average_semantic_similarity) / 3 if (average_relevance + average_quality + average_semantic_similarity) > 0 else 0,
                "evidence_sufficient": evidence_sufficient,
                "evidence_reason": evidence_reason,
            },
        )

        # Update state with results (avoid duplicate storage)
        updated_state = state.copy()
        updated_state["report"] = {
            "content": report_with_refs,
            "sources": {
                "web_results": len(search_results),
                "papers": len(research_papers),
            },
            "generated_at": time.time(),
            "quality_metrics": {
                "confidence_level": confidence_metrics['overall_confidence'],
                "confidence_score": confidence_metrics['confidence_score'],
                "contradictions_detected": len(contradictions),
                "evidence_sufficient": evidence_assessment['is_sufficient'],
                "evidence_reason": evidence_assessment['reason'],
                "citation_quality": citation_quality_score,
            },
        }
        # Reference the same content instead of duplicating
        updated_state["final_answer"] = updated_state["report"]["content"]
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "report",
            "action": "synthesized_final_report",
            "status": "completed",
            "execution_time_ms": execution_time_ms,
            "report_length": len(report_with_refs),
            "confidence_level": confidence_metrics['overall_confidence'],
            "contradictions_detected": len(contradictions),
        })

        # Track answer metrics for evaluation
        try:
            evaluator = get_evaluator()
            evaluator.track_answer_metrics(
                structure_score=1.0 if structure_valid else 0.0,
                leakage_score=0.0 if leakage_valid else 1.0,
                hallucination_risk=len(contradictions) / max(len(search_results) + len(research_papers), 1),
                citation_score=citation_quality_score,
                request_id=request_id,
            )
        except Exception as e:
            logger.warning(
                f"Failed to track answer metrics: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
            )

        return updated_state

    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000

        logger.error(
            f"Report node failed: {str(e)}",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time_ms,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Create fallback report
        fallback_report = f"""# Research Report

## Question
{user_query}

## Findings
Based on the available information:

### Web Sources
- Found {len(search_results)} web search results
- Key sources include: {', '.join([r.get('title', 'N/A') for r in search_results[:3]])}

### Academic Sources
- Found {len(research_papers)} relevant research papers
- Recent research includes: {', '.join([p.get('title', 'N/A') for p in research_papers[:2]])}

## Note
The automated report generation encountered an error. Please review the raw search results and papers above for detailed information.

Error: {str(e)}
"""

        # Update state with fallback (avoid duplicate storage)
        updated_state = state.copy()
        updated_state["report"] = {
            "content": fallback_report,
            "sources": {
                "web_results": len(search_results),
                "papers": len(research_papers),
            },
            "generated_at": time.time(),
            "fallback": True,
        }
        # Reference the same content instead of duplicating
        updated_state["final_answer"] = updated_state["report"]["content"]
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].append({
            "node": "report",
            "error": str(e),
            "error_type": type(e).__name__,
        })
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "report",
            "action": "synthesized_final_report",
            "status": "failed",
            "execution_time_ms": execution_time_ms,
            "report_length": len(fallback_report),
        })

        return updated_state
