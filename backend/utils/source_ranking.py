"""Source ranking and duplicate detection utilities.

This module provides lightweight algorithms for:
- Source quality scoring (relevance, quality, final scores)
- Duplicate detection and removal
- Academic prioritization
- Domain reliability assessment
- Semantic similarity scoring using sentence-transformers

OPTIMIZED: Single-pass scoring, cached normalization, O(n) duplicate detection
"""

import time
from typing import Any
from urllib.parse import urlparse

from backend.utils.logging_config import get_logger
from backend.utils.semantic_similarity import compute_query_source_similarity, batch_compute_similarity
from backend.utils.query_classifier import get_hybrid_scoring_weights

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

# Non-content page patterns to reject
NON_CONTENT_PATTERNS = {
    "login", "signin", "signup", "register", "auth",
    "download", "pdf", "file", "attachment",
    "pricing", "checkout", "cart", "payment",
    "contact", "about", "careers", "jobs",
    "privacy", "terms", "legal", "policy",
    "sitemap", "rss", "feed", "xml",
    "search", "results", "query",
    "advertisement", "ad", "banner", "promo",
    "landing", "portal", "home", "index",
    "navigation", "nav", "menu", "sidebar",
}

# Irrelevant domains to reject for technical/academic queries
IRRELEVANT_DOMAINS = {
    "gather.town", "hellogather.com", "letsgather.in",
    "play.google.com", "apps.apple.com",
    "www.gather.town", "gather.town/",
}

# Homepage indicators
HOMEPAGE_INDICATORS = {
    "home", "index", "default", "welcome",
    "portal", "landing", "main",
}

# Semantic similarity threshold
SEMANTIC_SIMILARITY_THRESHOLD = 0.45


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


def _is_non_content_page(url: str, title: str, snippet: str) -> tuple[bool, str]:
    """Check if URL/title/snippet indicate a non-content page.

    Args:
        url: Source URL
        title: Source title
        snippet: Source snippet

    Returns:
        Tuple of (is_non_content, reason)
    """
    url_lower = url.lower() if url else ""
    title_lower = title.lower() if title else ""
    snippet_lower = snippet.lower() if snippet else ""

    # Check for non-content patterns in URL path
    try:
        path = urlparse(url).path.lower() if url else ""
        for pattern in NON_CONTENT_PATTERNS:
            if pattern in path or f"/{pattern}" in url_lower:
                return True, f"Non-content page pattern: {pattern}"
    except Exception:
        pass

    # Check for homepage indicators
    if any(indicator in url_lower for indicator in HOMEPAGE_INDICATORS):
        if len(title) < 30 or not snippet:
            return True, "Homepage without content"

    # Check for download pages
    if "download" in url_lower or "pdf" in url_lower:
        return True, "Download page"

    # Check for login/signup pages
    if "login" in url_lower or "signin" in url_lower or "signup" in url_lower:
        return True, "Authentication page"

    return False, ""


def _calculate_semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity using token overlap (lightweight).

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0

    tokens1 = set(_normalize_text(text1).split())
    tokens2 = set(_normalize_text(text2).split())

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    # Require minimum overlap for meaningful similarity
    if intersection < 2:
        return 0.0

    jaccard = intersection / union if union > 0 else 0.0

    # Boost score if significant overlap
    if intersection >= 3:
        return min(jaccard * 1.5, 1.0)

    return jaccard


def rank_sources(
    web_results: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    query: str,
    query_type: str = "research",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Rank and score all sources using semantic similarity and hybrid scoring.

    Args:
        web_results: Web search results
        papers: Academic paper results
        query: Original search query
        query_type: Query category (definition, technical, research)

    Returns:
        Tuple of (ranked web results, ranked papers, ranking metrics)
    """
    start_time = time.time()

    # Compute semantic similarity for all sources
    semantic_start = time.time()

    # Prepare source texts for batch computation
    web_texts = []
    for result in web_results:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        web_texts.append(f"{title} {snippet}")

    paper_texts = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        paper_texts.append(f"{title} {abstract}")

    # Batch compute semantic similarities
    web_similarities = batch_compute_similarity(query, web_texts)
    paper_similarities = batch_compute_similarity(query, paper_texts)

    semantic_ms = (time.time() - semantic_start) * 1000

    # Assign semantic similarity scores
    for i, result in enumerate(web_results):
        result["semantic_similarity"] = web_similarities[i]

    for i, paper in enumerate(papers):
        paper["semantic_similarity"] = paper_similarities[i]

    # Filter web results with strict criteria including semantic similarity
    filtering_start = time.time()

    web_filtered = []
    web_rejected = 0
    seen_domains = {}
    domain_counts = {}  # Track domain counts for max 2 per domain

    for result in web_results:
        semantic_sim = result.get("semantic_similarity", 0.0)
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        url = result.get("url", "")

        # Strict rejection criteria
        reject_reason = None

        # Check for invalid basic fields first
        if not title or len(title.strip()) < 5:
            reject_reason = "Empty or invalid title"
        elif not snippet or len(snippet.strip()) < 40:
            reject_reason = "Empty or invalid snippet (too short)"
        elif not url or len(url.strip()) < 5:
            reject_reason = "Empty or invalid URL"
        elif semantic_sim < SEMANTIC_SIMILARITY_THRESHOLD:
            reject_reason = f"Low semantic similarity ({semantic_sim:.2f} < {SEMANTIC_SIMILARITY_THRESHOLD})"
        else:
            # Check for irrelevant domains
            try:
                domain = urlparse(url).netloc.lower()
                if any(irrelevant in domain for irrelevant in IRRELEVANT_DOMAINS):
                    reject_reason = f"Irrelevant domain: {domain}"
                else:
                    # Check domain count (max 2 per domain)
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    if domain_counts[domain] > 2:
                        reject_reason = f"Too many results from domain: {domain} (max 2)"
            except Exception:
                pass

            if not reject_reason:
                # Check for non-content pages
                is_non_content, non_content_reason = _is_non_content_page(url, title, snippet)
                if is_non_content:
                    reject_reason = non_content_reason

        if reject_reason:
            web_rejected += 1
            logger.warning(
                f"Rejected web result: {title[:50] if title else 'N/A'}",
                extra={
                    "url": url[:50] if url else "N/A",
                    "semantic_similarity": semantic_sim,
                    "reject_reason": reject_reason,
                },
            )
        else:
            web_filtered.append(result)

    # Filter papers with strict criteria including semantic similarity
    papers_filtered = []
    papers_rejected = 0

    for paper in papers:
        semantic_sim = paper.get("semantic_similarity", 0.0)
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        authors = paper.get("authors", [])
        published = paper.get("published", "")

        # Strict rejection criteria
        reject_reason = None

        if not title or len(title.strip()) < 5:
            reject_reason = "Empty or invalid title"
        elif not abstract or len(abstract.strip()) < 50:
            reject_reason = "Empty or invalid abstract (too short)"
        elif semantic_sim < SEMANTIC_SIMILARITY_THRESHOLD:
            reject_reason = f"Low semantic similarity ({semantic_sim:.2f} < {SEMANTIC_SIMILARITY_THRESHOLD})"
        elif not authors or len(authors) < 1:
            reject_reason = "Missing authors"
        elif not published:
            reject_reason = "Missing publication date"

        if reject_reason:
            papers_rejected += 1
            logger.warning(
                f"Rejected paper: {title[:50] if title else 'N/A'}",
                extra={
                    "semantic_similarity": semantic_sim,
                    "reject_reason": reject_reason,
                },
            )
        else:
            papers_filtered.append(paper)

    filtering_ms = (time.time() - filtering_start) * 1000

    # Apply hybrid scoring model to filtered sources
    scoring_start = time.time()

    for source in web_filtered:
        source = _apply_hybrid_scoring(source, query, is_paper=False, query_type=query_type)

    for paper in papers_filtered:
        paper = _apply_hybrid_scoring(paper, query, is_paper=True, query_type=query_type)

    scoring_ms = (time.time() - scoring_start) * 1000

    # Sort by overall score
    sorting_start = time.time()
    web_sorted = sorted(web_filtered, key=lambda x: x.get("overall_score", 0), reverse=True)
    papers_sorted = sorted(papers_filtered, key=lambda x: x.get("overall_score", 0), reverse=True)
    sorting_ms = (time.time() - sorting_start) * 1000

    # Calculate metrics
    ranking_time = (time.time() - start_time) * 1000
    total_before = len(web_results) + len(papers)
    total_after = len(web_sorted) + len(papers_sorted)

    avg_semantic_sim = 0.0
    max_semantic_sim = 0.0
    avg_overall_score = 0.0
    all_sources = web_sorted + papers_sorted

    if all_sources:
        semantic_sims = [s.get("semantic_similarity", 0) for s in all_sources]
        overall_scores = [s.get("overall_score", 0) for s in all_sources]
        avg_semantic_sim = sum(semantic_sims) / len(semantic_sims)
        max_semantic_sim = max(semantic_sims)
        avg_overall_score = sum(overall_scores) / len(overall_scores)

    metrics = {
        "ranking_time_ms": ranking_time,
        "semantic_similarity_ms": semantic_ms,
        "filtering_ms": filtering_ms,
        "hybrid_scoring_ms": scoring_ms,
        "sorting_ms": sorting_ms,
        "web_rejected": web_rejected,
        "papers_rejected": papers_rejected,
        "sources_before": total_before,
        "sources_after": total_after,
        "average_semantic_similarity": avg_semantic_sim,
        "max_semantic_similarity": max_semantic_sim,
        "average_overall_score": avg_overall_score,
        "semantic_similarity_threshold": SEMANTIC_SIMILARITY_THRESHOLD,
    }

    return web_sorted, papers_sorted, metrics


def _apply_hybrid_scoring(
    source: dict[str, Any],
    query: str,
    is_paper: bool = False,
    query_type: str = "research",
) -> dict[str, Any]:
    """Apply hybrid scoring model to a source.

    Scoring weights are adaptive based on query type:
    - Definition: Semantic 30%, Quality 35%, Reliability 25%, Freshness 5%, Diversity 5%
    - Technical: Semantic 40%, Quality 25%, Reliability 20%, Freshness 10%, Diversity 5%
    - Research: Semantic 45%, Quality 20%, Reliability 20%, Freshness 10%, Diversity 5%

    Args:
        source: Source dictionary
        query: Original query
        is_paper: Whether this is an academic paper
        query_type: Query category (definition, technical, research)

    Returns:
        Updated source dictionary with hybrid scores
    """
    semantic_sim = source.get("semantic_similarity", 0.0)

    # Get adaptive weights based on query type
    weights = get_hybrid_scoring_weights(query_type)

    # Source Quality
    quality_score = _calculate_quality_score(source, is_paper)

    # Source Reliability
    reliability_score = _calculate_reliability_score(source)

    # Freshness
    freshness_score = _calculate_freshness_score(source, is_paper)

    # Diversity - simplified for now
    diversity_score = 0.5  # Placeholder, would need global context

    # Hybrid overall score with adaptive weights
    overall_score = (
        (semantic_sim * weights["semantic"]) +
        (quality_score * weights["quality"]) +
        (reliability_score * weights["reliability"]) +
        (freshness_score * weights["freshness"]) +
        (diversity_score * weights["diversity"])
    )

    source["quality_score"] = quality_score
    source["reliability_score"] = reliability_score
    source["freshness_score"] = freshness_score
    source["diversity_score"] = diversity_score
    source["overall_score"] = overall_score

    return source


def _calculate_quality_score(source: dict[str, Any], is_paper: bool) -> float:
    """Calculate source quality score.

    Args:
        source: Source dictionary
        is_paper: Whether this is an academic paper

    Returns:
        Quality score between 0 and 1
    """
    score = 0.0

    if is_paper:
        # Paper quality factors
        abstract = source.get("abstract", "")
        authors = source.get("authors", [])

        # Abstract length and quality
        if abstract and len(abstract) > 200:
            score += 0.4
        elif abstract and len(abstract) > 100:
            score += 0.3
        elif abstract:
            score += 0.2

        # Author count
        if authors and len(authors) >= 3:
            score += 0.3
        elif authors and len(authors) >= 2:
            score += 0.2
        elif authors:
            score += 0.1

        # arXiv quality boost
        entry_id = source.get("entry_id", "")
        if entry_id and "arxiv" in entry_id.lower():
            score += 0.3
    else:
        # Web quality factors
        title = source.get("title", "")
        snippet = source.get("snippet", "")

        # Title quality
        if title and len(title) > 20:
            score += 0.3
        elif title:
            score += 0.2

        # Snippet quality
        if snippet and len(snippet) > 150:
            score += 0.4
        elif snippet and len(snippet) > 80:
            score += 0.3
        elif snippet:
            score += 0.2

        # Domain quality
        url = source.get("url", "")
        domain_score = _calculate_domain_score(url)
        score += domain_score

    return min(score, 1.0)


def _calculate_reliability_score(source: dict[str, Any]) -> float:
    """Calculate source reliability score based on domain.

    Args:
        source: Source dictionary

    Returns:
        Reliability score between 0 and 1
    """
    url = source.get("url", "")
    entry_id = source.get("entry_id", "")

    # arXiv papers are highly reliable
    if entry_id and "arxiv" in entry_id.lower():
        return 1.0

    # Check domain reliability
    return _calculate_domain_score(url) / 0.3 if _calculate_domain_score(url) > 0 else 0.3


def _calculate_freshness_score(source: dict[str, Any], is_paper: bool) -> float:
    """Calculate freshness score based on publication date.

    Args:
        source: Source dictionary
        is_paper: Whether this is an academic paper

    Returns:
        Freshness score between 0 and 1
    """
    if not is_paper:
        # For web sources, assume recent (no date info)
        return 0.7

    published = source.get("published", "")
    if not published:
        return 0.5

    try:
        # Parse date and calculate recency
        from datetime import datetime
        pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        now = datetime.now(pub_date.tzinfo)
        days_old = (now - pub_date).days

        # Score based on recency
        if days_old < 365:  # Less than 1 year
            return 1.0
        elif days_old < 730:  # 1-2 years
            return 0.8
        elif days_old < 1825:  # 2-5 years
            return 0.6
        elif days_old < 3650:  # 5-10 years
            return 0.4
        else:
            return 0.2
    except Exception:
        return 0.5
