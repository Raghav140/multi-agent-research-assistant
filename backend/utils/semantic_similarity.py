"""Semantic similarity computation using sentence-transformers.

This module provides semantic similarity scoring using the all-MiniLM-L6-v2 model
for computing cosine similarity between queries and sources.
"""

from typing import Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from scipy.spatial.distance import cosine

from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

# Global model instance (lazy loaded)
_model: Optional[SentenceTransformer] = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    """Lazy load the sentence-transformers model.

    Returns:
        SentenceTransformer model instance
    """
    global _model
    if _model is None:
        logger.info(f"Loading sentence-transformers model: {_MODEL_NAME}")
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info(f"Model loaded successfully: {_MODEL_NAME}")
    return _model


def compute_semantic_similarity(
    text1: str,
    text2: str,
) -> float:
    """Compute semantic similarity between two texts using cosine similarity.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Cosine similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0

    try:
        model = _get_model()

        # Generate embeddings
        embedding1 = model.encode(text1, convert_to_numpy=True)
        embedding2 = model.encode(text2, convert_to_numpy=True)

        # Compute cosine similarity (1 - cosine distance)
        similarity = 1 - cosine(embedding1, embedding2)

        return float(similarity)

    except Exception as e:
        logger.error(f"Failed to compute semantic similarity: {str(e)}")
        return 0.0


def compute_query_source_similarity(
    query: str,
    source_text: str,
) -> float:
    """Compute semantic similarity between query and source.

    Args:
        query: User query
        source_text: Source text (title, snippet, or abstract)

    Returns:
        Cosine similarity score between 0 and 1
    """
    return compute_semantic_similarity(query, source_text)


def batch_compute_similarity(
    query: str,
    source_texts: list[str],
) -> list[float]:
    """Compute semantic similarity between query and multiple sources.

    Args:
        query: User query
        source_texts: List of source texts

    Returns:
        List of cosine similarity scores
    """
    if not query or not source_texts:
        return [0.0] * len(source_texts)

    try:
        model = _get_model()

        # Generate query embedding once
        query_embedding = model.encode(query, convert_to_numpy=True)

        # Generate source embeddings
        source_embeddings = model.encode(source_texts, convert_to_numpy=True)

        # Compute cosine similarities
        similarities = []
        for source_embedding in source_embeddings:
            similarity = 1 - cosine(query_embedding, source_embedding)
            similarities.append(float(similarity))

        return similarities

    except Exception as e:
        logger.error(f"Failed to compute batch similarity: {str(e)}")
        return [0.0] * len(source_texts)


def compute_source_agreement(
    source1_text: str,
    source2_text: str,
) -> float:
    """Compute semantic agreement between two sources.

    Args:
        source1_text: First source text
        source2_text: Second source text

    Returns:
        Agreement score between 0 and 1
    """
    return compute_semantic_similarity(source1_text, source2_text)
