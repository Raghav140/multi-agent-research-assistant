"""Evidence fusion engine for combining and deduplicating sources.

This module provides functionality for:
- Removing duplicate sources (same URLs, domains, similar content)
- Calculating evidence agreement scores between sources
- Computing source diversity scores
- Selecting best sources based on quality and diversity
"""

import time
from typing import Any, Dict, List, Set
from urllib.parse import urlparse
from backend.utils.logging_config import get_logger
from backend.utils.semantic_similarity import compute_source_agreement

logger = get_logger(__name__)


def fuse_evidence(
    web_results: List[Dict[str, Any]],
    papers: List[Dict[str, Any]],
    documentation: List[Dict[str, Any]],
    query: str,
) -> Dict[str, Any]:
    """Fuse evidence from multiple sources with deduplication and scoring.

    Args:
        web_results: Web search results
        papers: Academic papers
        documentation: Official documentation results
        query: Original query

    Returns:
        Dictionary with:
        - combined_sources: Deduplicated and scored sources
        - agreement_score: Agreement between independent sources
        - diversity_score: Source diversity score
        - best_sources: Top-ranked sources
        - metrics: Fusion metrics
    """
    start_time = time.time()

    # Combine all sources
    all_sources = []
    for source in web_results:
        source["source_type"] = "web"
        all_sources.append(source)
    for source in papers:
        source["source_type"] = "academic"
        all_sources.append(source)
    for source in documentation:
        source["source_type"] = "documentation"
        all_sources.append(source)

    logger.info(
        f"Evidence fusion started",
        extra={
            "total_sources": len(all_sources),
            "web_count": len(web_results),
            "papers_count": len(papers),
            "documentation_count": len(documentation),
        },
    )

    # Remove duplicates
    deduplicated = remove_duplicates(all_sources)

    # Calculate agreement score
    agreement_score = calculate_agreement_score(deduplicated, query)

    # Calculate diversity score
    diversity_score = calculate_diversity_score(deduplicated)

    # Rank sources by quality and diversity
    ranked_sources = rank_sources_by_fusion(deduplicated, agreement_score, diversity_score)

    # Select best sources
    best_sources = select_best_sources(ranked_sources, max_sources=10)

    execution_time = time.time() - start_time

    metrics = {
        "original_count": len(all_sources),
        "deduplicated_count": len(deduplicated),
        "duplicates_removed": len(all_sources) - len(deduplicated),
        "agreement_score": agreement_score,
        "diversity_score": diversity_score,
        "fusion_time_ms": execution_time * 1000,
    }

    logger.info(
        f"Evidence fusion completed",
        extra=metrics,
    )

    return {
        "combined_sources": deduplicated,
        "agreement_score": agreement_score,
        "diversity_score": diversity_score,
        "best_sources": best_sources,
        "metrics": metrics,
    }


def remove_duplicates(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate sources based on URL, domain, and content similarity.

    Args:
        sources: List of sources to deduplicate

    Returns:
        Deduplicated list of sources
    """
    if not sources:
        return []

    seen_urls: Set[str] = set()
    seen_domains: Dict[str, int] = {}  # domain -> count
    seen_signatures: Set[str] = set()
    deduplicated = []

    for source in sources:
        url = source.get("url", "")
        title = source.get("title", "")
        snippet = source.get("snippet", "") or source.get("abstract", "")

        # Skip if no URL
        if not url:
            continue

        # Check for exact URL match
        if url in seen_urls:
            logger.debug(f"Removed duplicate URL: {url[:50]}")
            continue

        # Extract domain
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ""

        # Check domain count (max 2 per domain)
        domain_count = seen_domains.get(domain, 0)
        if domain_count >= 2:
            logger.debug(f"Removed source from over-represented domain: {domain}")
            continue

        # Create content signature for similarity check
        signature = _create_content_signature(title, snippet)
        if signature in seen_signatures:
            logger.debug(f"Removed duplicate content signature: {signature[:50]}")
            continue

        # Source is unique, add to results
        seen_urls.add(url)
        seen_domains[domain] = domain_count + 1
        seen_signatures.add(signature)
        deduplicated.append(source)

    logger.info(
        f"Duplicate removal completed",
        extra={
            "original_count": len(sources),
            "deduplicated_count": len(deduplicated),
            "duplicates_removed": len(sources) - len(deduplicated),
        },
    )

    return deduplicated


def _create_content_signature(title: str, snippet: str) -> str:
    """Create a content signature for duplicate detection.

    Args:
        title: Source title
        snippet: Source snippet or abstract

    Returns:
        Content signature string
    """
    # Normalize text
    title_normalized = title.lower().strip()
    snippet_normalized = snippet.lower().strip()

    # Create signature from first 100 chars of title + snippet
    signature = (title_normalized[:50] + snippet_normalized[:50]).replace(" ", "")

    return signature


def calculate_agreement_score(sources: List[Dict[str, Any]], query: str) -> float:
    """Calculate agreement score between independent sources.

    Args:
        sources: List of sources
        query: Original query

    Returns:
        Agreement score between 0 and 1
    """
    if len(sources) < 2:
        return 0.0

    # Extract source texts
    source_texts = []
    for source in sources:
        if "abstract" in source:
            source_texts.append(source["abstract"])
        elif "snippet" in source:
            source_texts.append(source["snippet"])
        elif "content" in source:
            source_texts.append(source["content"])

    if len(source_texts) < 2:
        return 0.0

    # Calculate pairwise agreements
    agreements = []
    for i in range(len(source_texts)):
        for j in range(i + 1, len(source_texts)):
            agreement = compute_source_agreement(source_texts[i], source_texts[j])
            agreements.append(agreement)

    if not agreements:
        return 0.0

    # Average agreement score
    avg_agreement = sum(agreements) / len(agreements)

    logger.debug(
        f"Agreement score calculated",
        extra={
            "num_sources": len(sources),
            "num_comparisons": len(agreements),
            "agreement_score": avg_agreement,
        },
    )

    return avg_agreement


def calculate_diversity_score(sources: List[Dict[str, Any]]) -> float:
    """Calculate source diversity score based on provider types and domains.

    Rewards:
- Multiple provider types (web, academic, documentation)
- Different domains

    Penalizes:
- Multiple sources from same domain

    Args:
        sources: List of sources

    Returns:
        Diversity score between 0 and 1
    """
    if not sources:
        return 0.0

    # Count provider types
    provider_types = set()
    for source in sources:
        provider_type = source.get("source_type", "web")
        provider_types.add(provider_type)

    # Count unique domains
    domains = set()
    for source in sources:
        url = source.get("url", "")
        if url:
            try:
                domain = urlparse(url).netloc.lower()
                domains.add(domain)
            except Exception:
                pass

    # Calculate diversity score
    provider_diversity = len(provider_types) / 3.0  # Max 3 provider types
    domain_diversity = min(len(domains) / len(sources), 1.0)  # Domain variety

    # Combined score
    diversity_score = (provider_diversity * 0.6) + (domain_diversity * 0.4)

    logger.debug(
        f"Diversity score calculated",
        extra={
            "num_sources": len(sources),
            "provider_types": list(provider_types),
            "num_domains": len(domains),
            "diversity_score": diversity_score,
        },
    )

    return diversity_score


def rank_sources_by_fusion(
    sources: List[Dict[str, Any]],
    agreement_score: float,
    diversity_score: float,
) -> List[Dict[str, Any]]:
    """Rank sources by fusion score combining quality, agreement, and diversity.

    Args:
        sources: List of sources
        agreement_score: Overall agreement between sources
        diversity_score: Overall source diversity

    Returns:
        Ranked list of sources
    """
    for source in sources:
        # Base score from existing quality/relevance
        quality = source.get("quality_score", 0.5)
        relevance = source.get("relevance_score", 0.5)
        semantic = source.get("semantic_similarity", 0.5)

        # Provider type bonus
        source_type = source.get("source_type", "web")
        provider_bonus = 0.0
        if source_type == "academic":
            provider_bonus = 0.1
        elif source_type == "documentation":
            provider_bonus = 0.15

        # Fusion score
        fusion_score = (
            (quality * 0.3) +
            (relevance * 0.3) +
            (semantic * 0.2) +
            (provider_bonus * 0.1) +
            (diversity_score * 0.1)
        )

        source["fusion_score"] = fusion_score

    # Sort by fusion score
    ranked = sorted(sources, key=lambda x: x.get("fusion_score", 0), reverse=True)

    return ranked


def select_best_sources(
    sources: List[Dict[str, Any]],
    max_sources: int = 10,
) -> List[Dict[str, Any]]:
    """Select best sources ensuring diversity.

    Args:
        sources: Ranked list of sources
        max_sources: Maximum number of sources to select

    Returns:
        Selected best sources
    """
    if not sources:
        return []

    # Take top sources
    selected = sources[:max_sources]

    # Ensure diversity by provider type
    provider_types = set()
    diverse_selected = []

    for source in selected:
        source_type = source.get("source_type", "web")

        # Always include if we haven't seen this provider type yet
        if source_type not in provider_types:
            diverse_selected.append(source)
            provider_types.add(source_type)
        # Otherwise include if we still have room
        elif len(diverse_selected) < max_sources:
            diverse_selected.append(source)

    return diverse_selected
