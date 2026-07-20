"""Source ranking and duplicate detection utilities.

This module provides lightweight algorithms for:
- Source quality scoring (relevance, quality, final scores)
- Duplicate detection and removal
- Academic prioritization
- Domain reliability assessment

OPTIMIZED: Single-pass scoring, cached normalization, O(n) duplicate detection
"""

import time
from typing import Any
from urllib.parse import urlparse

from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


# Trusted domains for quality scoring
TRUSTED_DOMAINS = {
    # Government
    "gov", "gov.uk", "gov.au", "gov.ca", "europa.eu",
    # Academic
    "edu", "ac.uk", "ac.jp", "ac.in", "edu.au",
    # Research institutions
    "nature.com", "science.org", "springer.com", "ieee.org", "acm.org",
    "arxiv.org", "researchgate.net", "scholar.google.com",
    # Documentation
    "docs.python.org", "developer.mozilla.org", "w3.org",
    # Wikipedia
    "wikipedia.org", "wikimedia.org",
    # Tech
    "github.com", "stackoverflow.com", "medium.com",
}

# Academic query keywords
ACADEMIC_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "data science", "algorithm", "programming",
    "mathematics", "statistics", "physics", "chemistry", "biology",
    "medicine", "medical", "research", "study", "paper", "publication",
    "theory", "theorem", "proof", "experiment", "analysis",
}


def _normalize_text(text: str) -> str:
    """Normalize text for comparison (internal, optimized).
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized lowercase text with extra whitespace removed
    """
    if not text:
        return ""
    return " ".join(text.lower().split())


def _extract_tokens(text: str) -> set[str]:
    """Extract tokens from normalized text (cached).
    
    Args:
        text: Normalized text
        
    Returns:
        Set of tokens
    """
    if not text:
        return set()
    return set(text.split())


def _calculate_domain_score(url: str) -> float:
    """Calculate domain reliability score (cached).
    
    Args:
        url: Source URL
        
    Returns:
        Domain score between 0 and 0.3
    """
    if not url:
        return 0.0
    
    try:
        domain = urlparse(url).netloc.lower()
        for trusted in TRUSTED_DOMAINS:
            if domain.endswith(trusted) or f".{trusted}" in domain:
                return 0.3
    except Exception:
        pass
    
    return 0.0


def _score_source_single_pass(
    source: dict[str, Any],
    query_tokens: set[str],
    query_lower: str,
    cached_normalization: dict[str, str],
    cached_tokens: dict[str, set[str]],
    cached_domains: dict[str, float],
) -> tuple[float, float, float]:
    """Score source in a single pass with cached computations.
    
    Args:
        source: Source dictionary
        query_tokens: Cached query token set
        query_lower: Cached normalized query
        cached_normalization: Dict of cached normalized text
        cached_tokens: Dict of cached token sets
        cached_domains: Dict of cached domain scores
        
    Returns:
        Tuple of (relevance_score, quality_score, final_score)
    """
    if not query_tokens:
        return 0.0, 0.0, 0.0
    
    # Get or cache normalized values
    title = source.get("title", "")
    snippet = source.get("snippet", "") or source.get("abstract", "")
    url = source.get("url", "")
    
    # Cache normalization
    if title not in cached_normalization:
        cached_normalization[title] = _normalize_text(title)
    title_norm = cached_normalization[title]
    
    if snippet not in cached_normalization:
        cached_normalization[snippet] = _normalize_text(snippet)
    snippet_norm = cached_normalization[snippet]
    
    # Cache tokens
    if title not in cached_tokens:
        cached_tokens[title] = _extract_tokens(title_norm)
    title_tokens = cached_tokens[title]
    
    if snippet not in cached_tokens:
        cached_tokens[snippet] = _extract_tokens(snippet_norm)
    snippet_tokens = cached_tokens[snippet]
    
    # Cache domain score
    if url not in cached_domains:
        cached_domains[url] = _calculate_domain_score(url)
    domain_score = cached_domains[url]
    
    # Calculate relevance score (single pass)
    relevance = 0.0
    if title_tokens:
        title_overlap = len(query_tokens & title_tokens) / len(query_tokens)
        relevance += title_overlap * 0.5
    
    if snippet_tokens:
        snippet_overlap = len(query_tokens & snippet_tokens) / len(query_tokens)
        relevance += snippet_overlap * 0.3
    
    if url:
        url_match = sum(1 for token in query_tokens if token in url.lower())
        relevance += (url_match / len(query_tokens)) * 0.2
    
    relevance = min(relevance, 1.0)
    
    # Calculate quality score (single pass)
    quality = domain_score
    
    if title and len(title) > 10:
        quality += 0.2
    elif title:
        quality += 0.1
    
    if snippet:
        if len(snippet) > 100:
            quality += 0.3
        elif len(snippet) > 50:
            quality += 0.2
        else:
            quality += 0.1
    
    entry_id = source.get("entry_id", "")
    if entry_id and "arxiv" in entry_id.lower():
        quality += 0.2
    
    quality = min(quality, 1.0)
    
    # Calculate final score
    final_score = (relevance * 0.6) + (quality * 0.4)
    
    return relevance, quality, final_score


def _detect_duplicates_optimized(sources: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Detect and remove duplicates using hash sets (O(n)).
    
    Args:
        sources: List of source dictionaries
        
    Returns:
        Tuple of (deduplicated sources, number of duplicates removed)
    """
    if not sources:
        return sources, 0
    
    seen = set()
    deduplicated = []
    duplicates_removed = 0
    
    for source in sources:
        # Use URL as primary key (fastest lookup)
        url = source.get("url", "")
        if url:
            signature = url
        else:
            # Fallback to title+snippet fingerprint
            title = _normalize_text(source.get("title", ""))
            snippet = _normalize_text(source.get("snippet", "") or source.get("abstract", ""))
            signature = f"{title[:50]}|{snippet[:50]}"
        
        if signature not in seen:
            seen.add(signature)
            deduplicated.append(source)
        else:
            duplicates_removed += 1
    
    return deduplicated, duplicates_removed


def _is_academic_query_optimized(query: str) -> bool:
    """Check if query is academic/research related (optimized).
    
    Args:
        query: Search query
        
    Returns:
        True if query contains academic keywords
    """
    query_lower = _normalize_text(query)
    return any(keyword in query_lower for keyword in ACADEMIC_KEYWORDS)


def rank_sources(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    query: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Rank and score all sources (optimized single-pass with detailed timing).
    
    Args:
        web_results: Web search results
        papers: Academic paper results
        query: Original search query
        
    Returns:
        Tuple of (ranked web results, ranked papers, ranking metrics)
    """
    start_time = time.time()
    
    # Cache query normalization and tokens (done once)
    norm_start = time.time()
    query_lower = _normalize_text(query)
    query_tokens = _extract_tokens(query_lower)
    normalization_ms = (time.time() - norm_start) * 1000
    
    # Initialize caches
    cached_normalization: dict[str, str] = {}
    cached_tokens: dict[str, set[str]] = {}
    cached_domains: dict[str, float] = {}
    
    # Score web results (single pass per source)
    scoring_start = time.time()
    for result in web_results:
        relevance, quality, final_score = _score_source_single_pass(
            result, query_tokens, query_lower,
            cached_normalization, cached_tokens, cached_domains
        )
        result["relevance_score"] = relevance
        result["quality_score"] = quality
        result["final_score"] = final_score
    
    # Score papers (single pass per source, reusing caches)
    for paper in papers:
        relevance, quality, final_score = _score_source_single_pass(
            paper, query_tokens, query_lower,
            cached_normalization, cached_tokens, cached_domains
        )
        paper["relevance_score"] = relevance
        paper["quality_score"] = quality
        paper["final_score"] = final_score
    scoring_ms = (time.time() - scoring_start) * 1000
    
    # Sort by final score (single sort per list)
    sorting_start = time.time()
    web_results_sorted = sorted(web_results, key=lambda x: x.get("final_score", 0), reverse=True)
    papers_sorted = sorted(papers, key=lambda x: x.get("final_score", 0), reverse=True)
    sorting_ms = (time.time() - sorting_start) * 1000
    
    # Detect duplicates (O(n) hash-based)
    dedup_start = time.time()
    web_deduplicated, web_duplicates = _detect_duplicates_optimized(web_results_sorted)
    papers_deduplicated, paper_duplicates = _detect_duplicates_optimized(papers_sorted)
    duplicate_detection_ms = (time.time() - dedup_start) * 1000
    
    # Academic prioritization (cached query check)
    academic_query = _is_academic_query_optimized(query)
    academic_sources_selected = len(papers_deduplicated) if papers_deduplicated else 0
    
    # Calculate metrics
    ranking_time = (time.time() - start_time) * 1000
    total_duplicates = web_duplicates + paper_duplicates
    total_before = len(web_results) + len(papers)
    total_after = len(web_deduplicated) + len(papers_deduplicated)
    
    avg_score = 0.0
    highest_score = 0.0
    lowest_score = 1.0
    all_sources = web_deduplicated + papers_deduplicated
    if all_sources:
        scores = [s.get("final_score", 0) for s in all_sources]
        avg_score = sum(scores) / len(scores)
        highest_score = max(scores)
        lowest_score = min(scores)
    
    metrics = {
        "ranking_time_ms": ranking_time,
        "normalization_ms": normalization_ms,
        "scoring_ms": scoring_ms,
        "sorting_ms": sorting_ms,
        "duplicate_detection_ms": duplicate_detection_ms,
        "duplicates_removed": total_duplicates,
        "sources_before": total_before,
        "sources_after": total_after,
        "academic_query": academic_query,
        "academic_sources_selected": academic_sources_selected,
        "final_sources_used": total_after,
        "average_source_score": avg_score,
        "highest_source_score": highest_score,
        "lowest_source_score": lowest_score,
    }
    
    return web_deduplicated, papers_deduplicated, metrics
