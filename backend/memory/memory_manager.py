"""Memory manager for research memory operations.

This module provides a high-level interface for managing research memory,
including lookup, insertion, and cleanup operations.
"""

from typing import Any, Dict, List, Optional
from backend.memory.research_memory import ResearchMemory, get_research_memory
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """High-level manager for research memory operations.

    This class provides a convenient interface for checking memory before
    retrieval and storing results after successful research.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the memory manager.

        Args:
            db_path: Optional database path
        """
        self.memory = get_research_memory(db_path)
        logger.info("Memory manager initialized")

    def check_memory(
        self,
        query: str,
        query_type: str,
        similarity_threshold: float = 0.75,
        max_results: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """Check memory for similar queries before retrieval.

        Args:
            query: Current query
            query_type: Query category
            similarity_threshold: Minimum similarity threshold
            max_results: Maximum similar results to consider

        Returns:
            Best matching research record if found, None otherwise
        """
        similar_queries = self.memory.find_similar_queries(
            query=query,
            query_type=query_type,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
        )

        if not similar_queries:
            logger.info(
                "No similar queries found in memory",
                extra={
                    "query": query,
                    "query_type": query_type,
                    "similarity_threshold": similarity_threshold,
                },
            )
            return None

        # Select the best match (highest similarity)
        best_match = similar_queries[0]

        logger.info(
            "Found similar query in memory",
            extra={
                "query": query,
                "query_type": query_type,
                "similar_query": best_match["query"],
                "similarity": best_match["similarity"],
                "confidence_score": best_match["confidence_score"],
            },
        )

        return best_match

    def store_research(
        self,
        query: str,
        query_type: str,
        sources_used: List[Dict[str, Any]],
        final_summary: str,
        confidence_score: float,
        citation_quality_score: float = 0.0,
        query_embedding: Optional[str] = None,
    ) -> int:
        """Store research results in memory.

        Args:
            query: Research query
            query_type: Query category
            sources_used: List of sources used
            final_summary: Final summary/answer
            confidence_score: Confidence score
            citation_quality_score: Citation quality score
            query_embedding: Optional query embedding

        Returns:
            Record ID
        """
        record_id = self.memory.store_research(
            query=query,
            query_type=query_type,
            sources_used=sources_used,
            final_summary=final_summary,
            confidence_score=confidence_score,
            query_embedding=query_embedding,
        )

        logger.info(
            "Research stored in memory",
            extra={
                "record_id": record_id,
                "query": query,
                "query_type": query_type,
                "confidence_score": confidence_score,
                "citation_quality_score": citation_quality_score,
            },
        )

        return record_id

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with memory statistics
        """
        return self.memory.get_memory_stats()

    def cleanup_old_records(self, days: int = 30) -> int:
        """Clean up old records from memory.

        Args:
            days: Number of days to keep records

        Returns:
            Number of records deleted
        """
        return self.memory.clear_old_records(days)


# Global singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(db_path: Optional[str] = None) -> MemoryManager:
    """Get the global memory manager singleton.

    Args:
        db_path: Optional database path

    Returns:
        MemoryManager instance
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(db_path)
    return _memory_manager
