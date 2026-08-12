"""Embedding manager for sentence-transformers model.

This module provides a singleton pattern for managing the sentence-transformers
model with thread-safe loading and performance tracking.
"""

import threading
import time
from typing import Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from scipy.spatial.distance import cosine

from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingManager:
    """Singleton manager for sentence-transformers model.

    This class ensures only one model instance is loaded and provides
    thread-safe access to embedding generation with performance tracking.
    """

    _instance: Optional['EmbeddingManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the embedding manager."""
        if hasattr(self, '_initialized'):
            return

        self._model: Optional[SentenceTransformer] = None
        self._model_loaded = False
        self._model_load_time: Optional[float] = None
        self._embedding_generation_times = []
        self._lock = threading.Lock()
        self._initialized = True

        logger.info("Embedding manager initialized (model not loaded yet)")

    def load_model(self) -> None:
        """Load the sentence-transformers model.

        This method is thread-safe and will only load the model once.
        """
        with self._lock:
            if self._model_loaded:
                logger.debug("Model already loaded, skipping")
                return

            logger.info(f"Loading sentence-transformers model: {_MODEL_NAME}")
            start_time = time.time()

            try:
                self._model = SentenceTransformer(_MODEL_NAME)
                self._model_loaded = True
                self._model_load_time = time.time() - start_time

                logger.info(
                    f"Model loaded successfully: {_MODEL_NAME}",
                    extra={
                        "model_name": _MODEL_NAME,
                        "load_time_ms": self._model_load_time * 1000,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to load model: {str(e)}")
                raise

    def ensure_model_loaded(self) -> None:
        """Ensure the model is loaded, loading it if necessary."""
        if not self._model_loaded:
            self.load_model()

    def encode(
        self,
        text: str,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: Text to encode
            convert_to_numpy: Whether to return numpy array

        Returns:
            Embedding vector
        """
        self.ensure_model_loaded()

        start_time = time.time()
        embedding = self._model.encode(text, convert_to_numpy=convert_to_numpy)
        generation_time = time.time() - start_time

        self._embedding_generation_times.append(generation_time)

        # Keep only last 100 generation times
        if len(self._embedding_generation_times) > 100:
            self._embedding_generation_times = self._embedding_generation_times[-100:]

        return embedding

    def encode_batch(
        self,
        texts: list[str],
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to encode
            convert_to_numpy: Whether to return numpy array

        Returns:
            Array of embedding vectors
        """
        self.ensure_model_loaded()

        start_time = time.time()
        embeddings = self._model.encode(texts, convert_to_numpy=convert_to_numpy)
        generation_time = time.time() - start_time

        self._embedding_generation_times.append(generation_time)

        # Keep only last 100 generation times
        if len(self._embedding_generation_times) > 100:
            self._embedding_generation_times = self._embedding_generation_times[-100:]

        return embeddings

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score between 0 and 1
        """
        similarity = 1 - cosine(embedding1, embedding2)
        return float(similarity)

    def get_metrics(self) -> dict:
        """Get performance metrics for the embedding manager.

        Returns:
            Dictionary with metrics:
            - model_loaded: Whether model is loaded
            - model_load_time_ms: Time to load model
            - avg_embedding_time_ms: Average embedding generation time
            - total_embeddings: Total number of embeddings generated
        """
        avg_time = (
            sum(self._embedding_generation_times) / len(self._embedding_generation_times)
            if self._embedding_generation_times
            else 0
        )

        return {
            "model_loaded": self._model_loaded,
            "model_load_time_ms": self._model_load_time * 1000 if self._model_load_time else None,
            "avg_embedding_time_ms": avg_time * 1000,
            "total_embeddings": len(self._embedding_generation_times),
        }


# Global singleton instance
_embedding_manager: Optional[EmbeddingManager] = None
_manager_lock = threading.Lock()


def get_embedding_manager() -> EmbeddingManager:
    """Get the global embedding manager singleton.

    Returns:
        EmbeddingManager instance
    """
    global _embedding_manager
    if _embedding_manager is None:
        with _manager_lock:
            if _embedding_manager is None:
                _embedding_manager = EmbeddingManager()
    return _embedding_manager


def load_model_on_startup() -> None:
    """Load the model during application startup.

    This function should be called during application initialization
    to avoid first-request latency.
    """
    manager = get_embedding_manager()
    manager.load_model()
    logger.info("Model pre-loaded on startup")


def compute_semantic_similarity(
    text1: str,
    text2: str,
) -> float:
    """Compute semantic similarity between two texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Cosine similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0

    try:
        manager = get_embedding_manager()
        embedding1 = manager.encode(text1)
        embedding2 = manager.encode(text2)
        similarity = manager.compute_similarity(embedding1, embedding2)
        return similarity
    except Exception as e:
        logger.error(f"Failed to compute semantic similarity: {str(e)}")
        return 0.0


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
        manager = get_embedding_manager()
        query_embedding = manager.encode(query)
        source_embeddings = manager.encode_batch(source_texts)

        similarities = []
        for source_embedding in source_embeddings:
            similarity = manager.compute_similarity(query_embedding, source_embedding)
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
