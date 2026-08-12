"""Query classifier for adaptive evidence validation.

This module classifies queries into categories (definition, technical, research)
and provides appropriate validation thresholds for each category.
"""

from typing import Dict, Any
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


def classify_query(query: str) -> str:
    """Classify the query into a category.

    Categories:
    - definition: "What is X?", "Define X", "Explain X" (simple definitions)
    - technical: "X tutorial", "X authentication", "X setup" (how-to/implementation)
    - research: "Explain X", "X research", "X architecture" (deep research)

    Args:
        query: User query string

    Returns:
        Query category: "definition", "technical", or "research"
    """
    query_lower = query.lower().strip()

    # Definition patterns - simple what-is questions
    definition_patterns = [
        "what is",
        "define",
        "definition of",
        "what does",
        "what are",
        "meaning of",
    ]

    # Technical/tutorial patterns - how-to, implementation
    technical_patterns = [
        "tutorial",
        "how to",
        "how do i",
        "setup",
        "configure",
        "install",
        "implement",
        "authentication",
        "guide",
        "example",
        "code",
        "programming",
        "api",
        "framework",
        "library",
    ]

    # Research patterns - deep explanation, architecture
    research_patterns = [
        "explain",
        "research",
        "architecture",
        "analysis",
        "study",
        "overview",
        "history",
        "theory",
        "principles",
        "fundamentals",
    ]

    # Check for definition patterns first
    for pattern in definition_patterns:
        if pattern in query_lower:
            # If it's a simple "what is" without complex terms, treat as definition
            if len(query.split()) <= 5:  # Short queries are likely definitions
                return "definition"

    # Check for technical patterns
    for pattern in technical_patterns:
        if pattern in query_lower:
            return "technical"

    # Check for research patterns
    for pattern in research_patterns:
        if pattern in query_lower:
            return "research"

    # Default: classify based on query length and complexity
    if len(query.split()) <= 4:
        return "definition"
    elif len(query.split()) <= 6:
        return "technical"
    else:
        return "research"


def get_validation_thresholds(query_type: str) -> Dict[str, float]:
    """Get validation thresholds based on query type.

    Args:
        query_type: Query category ("definition", "technical", "research")

    Returns:
        Dictionary with thresholds:
        - min_sources: Minimum number of sources required
        - min_similarity: Minimum semantic similarity threshold
        - min_confidence: Minimum confidence score threshold
        - min_relevance: Minimum relevance score threshold
    """
    if query_type == "definition":
        # Definition queries: allow single authoritative sources, lower thresholds
        return {
            "min_sources": 1,
            "min_similarity": 0.35,
            "min_confidence": 0.35,
            "min_relevance": 0.40,
        }
    elif query_type == "technical":
        # Technical queries: require multiple sources, moderate thresholds
        return {
            "min_sources": 2,
            "min_similarity": 0.40,
            "min_confidence": 0.40,
            "min_relevance": 0.45,
        }
    else:  # research
        # Research queries: strict validation, high thresholds
        return {
            "min_sources": 2,
            "min_similarity": 0.45,
            "min_confidence": 0.50,
            "min_relevance": 0.50,
        }


def get_hybrid_scoring_weights(query_type: str) -> Dict[str, float]:
    """Get hybrid scoring weights based on query type.

    Args:
        query_type: Query category ("definition", "technical", "research")

    Returns:
        Dictionary with scoring weights:
        - semantic: Semantic similarity weight
        - quality: Source quality weight
        - reliability: Source reliability weight
        - freshness: Freshness weight
        - diversity: Diversity weight
    """
    if query_type == "definition":
        # Definition: prioritize quality and reliability over semantic match
        return {
            "semantic": 0.30,
            "quality": 0.35,
            "reliability": 0.25,
            "freshness": 0.05,
            "diversity": 0.05,
        }
    elif query_type == "technical":
        # Technical: balanced approach
        return {
            "semantic": 0.40,
            "quality": 0.25,
            "reliability": 0.20,
            "freshness": 0.10,
            "diversity": 0.05,
        }
    else:  # research
        # Research: prioritize semantic similarity and freshness
        return {
            "semantic": 0.45,
            "quality": 0.20,
            "reliability": 0.20,
            "freshness": 0.10,
            "diversity": 0.05,
        }


def get_preferred_domains(query_type: str) -> list[str]:
    """Get preferred domains based on query type.

    Args:
        query_type: Query category ("definition", "technical", "research")

    Returns:
        List of preferred domain patterns
    """
    if query_type == "definition":
        # Definition: prefer Wikipedia, official docs, educational
        return [
            "wikipedia.org",
            ".edu",
            ".gov",
            "docs.",
            "official",
        ]
    elif query_type == "technical":
        # Technical: prefer GitHub, official docs, Stack Overflow
        return [
            "github.com",
            "docs.",
            "stackoverflow.com",
            "dev.to",
            "medium.com",
            "official",
        ]
    else:  # research
        # Research: prefer academic, arXiv, research institutions
        return [
            "arxiv.org",
            ".edu",
            "researchgate.net",
            "scholar.google.com",
            "nature.com",
            "ieee.org",
            "acm.org",
        ]
