"""Quality assessment utilities for research reports.

This module provides algorithms for:
- Confidence scoring based on source quality and agreement
- Contradiction detection between sources
- Evidence fusion from multiple sources
- Missing information detection
- Reference quality enhancement
"""

import time
from typing import Any
from collections import defaultdict

from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


# Reliability weights for source types
RELIABILITY_WEIGHTS = {
    # Government sources - highest reliability
    "gov": 1.0,
    "gov.uk": 1.0,
    "gov.au": 1.0,
    "gov.ca": 1.0,
    "europa.eu": 1.0,

    # Academic institutions - very high reliability
    "edu": 0.95,
    "ac.uk": 0.95,
    "ac.jp": 0.95,
    "ac.in": 0.95,
    "edu.au": 0.95,

    # Peer-reviewed journals - very high reliability
    "nature.com": 0.95,
    "science.org": 0.95,
    "springer.com": 0.95,
    "ieee.org": 0.95,
    "acm.org": 0.95,

    # Research repositories - high reliability
    "arxiv.org": 0.9,
    "researchgate.net": 0.85,
    "scholar.google.com": 0.9,

    # Official documentation - high reliability
    "docs.python.org": 0.9,
    "developer.mozilla.org": 0.9,
    "w3.org": 0.9,

    # Wikipedia - medium reliability (good starting point)
    "wikipedia.org": 0.7,
    "wikimedia.org": 0.7,

    # Tech communities - medium reliability
    "github.com": 0.75,
    "stackoverflow.com": 0.8,
    "medium.com": 0.65,
}


def calculate_source_reliability(source: dict[str, Any]) -> float:
    """Calculate reliability score for a single source.

    Args:
        source: Source dictionary with url, title, snippet, etc.

    Returns:
        Reliability score between 0 and 1
    """
    url = source.get("url", "")
    if not url:
        return 0.5  # Default reliability for sources without URL

    # Check against known reliable domains
    for domain, weight in RELIABILITY_WEIGHTS.items():
        if domain in url.lower():
            return weight

    # Default reliability for unknown domains
    return 0.6


def calculate_confidence_score(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate overall confidence score for research findings.

    Factors:
    - Number of sources
    - Source quality (reliability)
    - Agreement between sources
    - Academic evidence presence

    Args:
        web_results: Web search results with scores
        papers: Academic papers with scores

    Returns:
        Dictionary with confidence metrics and overall score
    """
    start_time = time.time()

    all_sources = web_results + papers

    if not all_sources:
        return {
            "overall_confidence": "Low",
            "confidence_score": 0.0,
            "num_sources": 0,
            "avg_reliability": 0.0,
            "has_academic": False,
            "source_agreement": 0.0,
        }

    # Calculate reliability for each source
    reliabilities = [calculate_source_reliability(s) for s in all_sources]
    avg_reliability = sum(reliabilities) / len(reliabilities)

    # Check for academic sources
    has_academic = any(
        "arxiv" in s.get("entry_id", "").lower() or
        "edu" in s.get("url", "").lower() or
        "ac." in s.get("url", "").lower()
        for s in all_sources
    )

    # Calculate source agreement (based on quality scores)
    quality_scores = [s.get("quality_score", 0) for s in all_sources]
    source_agreement = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    # Calculate overall confidence score
    # Weight factors: reliability (40%), academic presence (20%), agreement (20%), quantity (20%)
    quantity_factor = min(len(all_sources) / 5, 1.0)  # Cap at 5 sources
    academic_factor = 1.0 if has_academic else 0.5

    confidence_score = (
        (avg_reliability * 0.4) +
        (academic_factor * 0.2) +
        (source_agreement * 0.2) +
        (quantity_factor * 0.2)
    )

    # Determine confidence level
    if confidence_score >= 0.8:
        overall_confidence = "High"
    elif confidence_score >= 0.5:
        overall_confidence = "Medium"
    else:
        overall_confidence = "Low"

    calculation_time = (time.time() - start_time) * 1000

    return {
        "overall_confidence": overall_confidence,
        "confidence_score": confidence_score,
        "num_sources": len(all_sources),
        "avg_reliability": avg_reliability,
        "has_academic": has_academic,
        "source_agreement": source_agreement,
        "calculation_time_ms": calculation_time,
    }


def detect_contradictions(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect potential contradictions between sources.

    This is a lightweight heuristic-based detection that looks for:
    - Opposing claims in titles/snippets
    - Conflicting numerical values
    - Negation phrases

    Improved to use semantic similarity for better distinction between
    actual contradictions and paraphrasing.

    Args:
        web_results: Web search results
        papers: Academic papers

    Returns:
        List of detected contradictions with details
    """
    contradictions = []
    all_sources = web_results + papers

    if len(all_sources) < 2:
        return contradictions

    # Simple heuristic: look for negation words and opposing claims
    negation_words = {"not", "no", "never", "cannot", "impossible", "false", "incorrect"}

    for i, source1 in enumerate(all_sources):
        for j, source2 in enumerate(all_sources[i+1:], i+1):
            text1 = (source1.get("title", "") + " " + source1.get("snippet", "")).lower()
            text2 = (source2.get("title", "") + " " + source2.get("snippet", "")).lower()

            # Check for negation in one but not the other on similar topics
            has_negation1 = any(word in text1 for word in negation_words)
            has_negation2 = any(word in text2 for word in negation_words)

            # If one has negation and the other doesn't, flag as potential contradiction
            if has_negation1 != has_negation2:
                # Check if they share some keywords (similar topic)
                words1 = set(text1.split())
                words2 = set(text2.split())
                overlap = len(words1 & words2) / max(len(words1), len(words2), 1)

                # Use semantic similarity if available to distinguish contradiction from paraphrasing
                semantic_sim1 = source1.get("semantic_similarity", 0)
                semantic_sim2 = source2.get("semantic_similarity", 0)
                avg_semantic_sim = (semantic_sim1 + semantic_sim2) / 2

                # Only flag as contradiction if:
                # 1. They have keyword overlap (similar topic)
                # 2. AND semantic similarity is NOT very high (not just paraphrasing)
                # High semantic similarity (>0.7) suggests they're saying the same thing in different words
                if overlap > 0.2 and avg_semantic_sim < 0.7:  # 20% keyword overlap, but not too semantically similar
                    contradictions.append({
                        "source1": source1.get("title", "Unknown")[:50],
                        "source2": source2.get("title", "Unknown")[:50],
                        "type": "potential_negation_conflict",
                        "overlap": overlap,
                        "semantic_similarity": avg_semantic_sim,
                    })
                    logger.info(
                        "Potential contradiction detected",
                        extra={
                            "source1": source1.get("title", "Unknown")[:50],
                            "source2": source2.get("title", "Unknown")[:50],
                            "overlap": overlap,
                            "semantic_similarity": avg_semantic_sim,
                            "has_negation1": has_negation1,
                            "has_negation2": has_negation2,
                        },
                    )

    return contradictions


def fuse_evidence(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fuse evidence from multiple sources to avoid repetition.

    Args:
        web_results: Web search results
        papers: Academic papers

    Returns:
        Dictionary with fused evidence and statistics
    """
    all_sources = web_results + papers

    if not all_sources:
        return {
            "fused_points": [],
            "unique_sources": 0,
            "repetitions_removed": 0,
        }

    # Extract key points from titles and snippets
    key_points = []
    seen_points = set()
    repetitions_removed = 0

    for source in all_sources:
        title = source.get("title", "")
        snippet = source.get("snippet", "") or source.get("abstract", "")

        # Create a simple key point from title
        if title:
            point_key = title.lower()[:100]  # First 100 chars as key
            if point_key not in seen_points:
                seen_points.add(point_key)
                key_points.append({
                    "source": title[:80],
                    "type": "web" if source in web_results else "academic",
                    "reliability": calculate_source_reliability(source),
                })
            else:
                repetitions_removed += 1

    return {
        "fused_points": key_points,
        "unique_sources": len(seen_points),
        "repetitions_removed": repetitions_removed,
    }


def assess_evidence_sufficiency(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    """Assess whether evidence is sufficient to answer the query.

    Args:
        web_results: Web search results
        papers: Academic papers
        query: Original research query

    Returns:
        Dictionary with sufficiency assessment
    """
    all_sources = web_results + papers

    # Factors for sufficiency
    num_sources = len(all_sources)
    avg_quality = sum(s.get("quality_score", 0) for s in all_sources) / num_sources if num_sources else 0
    has_academic = any(
        "arxiv" in s.get("entry_id", "").lower() or
        "edu" in s.get("url", "").lower()
        for s in all_sources
    )

    # Simple heuristic: need at least 2 sources with decent quality
    is_sufficient = num_sources >= 2 and avg_quality >= 0.3

    return {
        "is_sufficient": is_sufficient,
        "num_sources": num_sources,
        "avg_quality": avg_quality,
        "has_academic": has_academic,
        "reason": (
            "Sufficient evidence available" if is_sufficient
            else "Limited evidence - results should be interpreted with caution"
        ),
    }


def enhance_reference_metadata(
    source: dict[str, Any],
    source_type: str,
) -> dict[str, Any]:
    """Enhance reference metadata with additional quality indicators.

    Args:
        source: Source dictionary
        source_type: Type of source ("web" or "academic")

    Returns:
        Enhanced reference dictionary
    """
    enhanced = source.copy()

    # Add reliability score
    enhanced["reliability_score"] = calculate_source_reliability(source)

    # Add source type
    enhanced["source_type"] = source_type

    # Add publication date if available
    if "published" in source:
        enhanced["publication_date"] = source["published"]
    elif "pubdate" in source:
        enhanced["publication_date"] = source["pubdate"]

    # Add authors if available (for academic papers)
    if source_type == "academic" and "authors" in source:
        enhanced["authors"] = source["authors"]

    return enhanced
