"""Research memory system with SQLite storage and similar query detection.

This module provides persistent storage for previous research queries,
enabling knowledge reuse and similar query detection.
"""

import sqlite3
import json
import time
from typing import Any, Dict, List, Optional
from pathlib import Path
from backend.utils.logging_config import get_logger
from backend.utils.semantic_similarity import compute_semantic_similarity

logger = get_logger(__name__)

# Database schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS research_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    query_type TEXT NOT NULL,
    query_embedding TEXT,
    sources_used TEXT,
    final_summary TEXT,
    confidence_score REAL,
    timestamp REAL NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query ON research_memory(query);
CREATE INDEX IF NOT EXISTS idx_query_type ON research_memory(query_type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON research_memory(timestamp);
"""


class ResearchMemory:
    """Research memory system with SQLite storage.

    This class provides persistent storage for research queries and
    enables similar query detection using semantic similarity.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the research memory system.

        Args:
            db_path: Path to SQLite database file (default: ./research_memory.db)
        """
        if db_path is None:
            # Try to get from settings, otherwise use default
            try:
                from backend.config.config import settings
                db_path = settings.research_memory_db_path
            except Exception:
                db_path = str(Path(__file__).parent.parent.parent / "research_memory.db")

        self.db_path = db_path
        self._ensure_directory_exists()
        self._initialize_database()

        logger.info(
            f"Research memory initialized",
            extra={"db_path": db_path},
        )

    def _ensure_directory_exists(self) -> None:
        """Ensure the directory for the database file exists."""
        db_file_path = Path(self.db_path)
        db_dir = db_file_path.parent
        if db_dir != Path(".") and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Execute schema creation
            cursor.executescript(CREATE_TABLE_SQL)

            conn.commit()
            conn.close()

            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    def store_research(
        self,
        query: str,
        query_type: str,
        sources_used: List[Dict[str, Any]],
        final_summary: str,
        confidence_score: float,
        query_embedding: Optional[str] = None,
    ) -> int:
        """Store a research query and its results.

        Args:
            query: Research query
            query_type: Query category (definition, technical, research)
            sources_used: List of sources used
            final_summary: Final summary/answer
            confidence_score: Confidence score of the answer
            query_embedding: Optional query embedding for similarity search

        Returns:
            ID of the stored record
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Serialize sources to JSON
            sources_json = json.dumps(sources_used)

            # Insert record
            cursor.execute(
                """
                INSERT INTO research_memory
                (query, query_type, query_embedding, sources_used, final_summary, confidence_score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (query, query_type, query_embedding, sources_json, final_summary, confidence_score, time.time()),
            )

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(
                f"Research stored in memory",
                extra={
                    "record_id": record_id,
                    "query": query,
                    "query_type": query_type,
                    "confidence_score": confidence_score,
                },
            )

            return record_id

        except Exception as e:
            logger.error(f"Failed to store research: {str(e)}")
            raise

    def find_similar_queries(
        self,
        query: str,
        query_type: str,
        similarity_threshold: float = 0.75,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find similar queries in memory.

        Args:
            query: Current query
            query_type: Query category
            similarity_threshold: Minimum similarity threshold
            max_results: Maximum number of results to return

        Returns:
            List of similar research records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get queries of the same type
            cursor.execute(
                """
                SELECT id, query, query_type, query_embedding, sources_used, final_summary, confidence_score, timestamp
                FROM research_memory
                WHERE query_type = ?
                ORDER BY timestamp DESC
                LIMIT 50
                """,
                (query_type,),
            )

            records = cursor.fetchall()
            conn.close()

            if not records:
                return []

            # Calculate similarity for each record
            similar_records = []
            for record in records:
                record_id, stored_query, stored_type, embedding_json, sources_json, summary, confidence, timestamp = record

                # Calculate semantic similarity
                similarity = compute_semantic_similarity(query, stored_query)

                if similarity >= similarity_threshold:
                    similar_records.append({
                        "id": record_id,
                        "query": stored_query,
                        "query_type": stored_type,
                        "sources_used": json.loads(sources_json) if sources_json else [],
                        "final_summary": summary,
                        "confidence_score": confidence,
                        "timestamp": timestamp,
                        "similarity": similarity,
                    })

            # Sort by similarity and limit results
            similar_records.sort(key=lambda x: x["similarity"], reverse=True)
            similar_records = similar_records[:max_results]

            logger.info(
                f"Found similar queries",
                extra={
                    "query": query,
                    "query_type": query_type,
                    "similar_count": len(similar_records),
                    "similarity_threshold": similarity_threshold,
                },
            )

            return similar_records

        except Exception as e:
            logger.error(f"Failed to find similar queries: {str(e)}")
            return []

    def get_research_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a research record by ID.

        Args:
            record_id: Record ID

        Returns:
            Research record or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, query, query_type, query_embedding, sources_used, final_summary, confidence_score, timestamp
                FROM research_memory
                WHERE id = ?
                """,
                (record_id,),
            )

            record = cursor.fetchone()
            conn.close()

            if not record:
                return None

            record_id, query, query_type, embedding_json, sources_json, summary, confidence, timestamp = record

            return {
                "id": record_id,
                "query": query,
                "query_type": query_type,
                "sources_used": json.loads(sources_json) if sources_json else [],
                "final_summary": summary,
                "confidence_score": confidence,
                "timestamp": timestamp,
            }

        except Exception as e:
            logger.error(f"Failed to get research by ID: {str(e)}")
            return None

    def get_recent_research(
        self,
        query_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent research records.

        Args:
            query_type: Optional query type filter
            limit: Maximum number of records to return

        Returns:
            List of recent research records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if query_type:
                cursor.execute(
                    """
                    SELECT id, query, query_type, sources_used, final_summary, confidence_score, timestamp
                    FROM research_memory
                    WHERE query_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (query_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, query, query_type, sources_used, final_summary, confidence_score, timestamp
                    FROM research_memory
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            records = cursor.fetchall()
            conn.close()

            results = []
            for record in records:
                record_id, query, stored_type, sources_json, summary, confidence, timestamp = record
                results.append({
                    "id": record_id,
                    "query": query,
                    "query_type": stored_type,
                    "sources_used": json.loads(sources_json) if sources_json else [],
                    "final_summary": summary,
                    "confidence_score": confidence,
                    "timestamp": timestamp,
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get recent research: {str(e)}")
            return []

    def clear_old_records(self, days: int = 30) -> int:
        """Clear records older than specified days.

        Args:
            days: Number of days to keep records

        Returns:
            Number of records deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_time = time.time() - (days * 24 * 60 * 60)

            cursor.execute(
                """
                DELETE FROM research_memory
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(
                f"Cleared old research records",
                extra={
                    "days": days,
                    "deleted_count": deleted_count,
                },
            )

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear old records: {str(e)}")
            return 0

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with memory statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Total records
            cursor.execute("SELECT COUNT(*) FROM research_memory")
            total_records = cursor.fetchone()[0]

            # Records by type
            cursor.execute("""
                SELECT query_type, COUNT(*)
                FROM research_memory
                GROUP BY query_type
            """)
            by_type = dict(cursor.fetchall())

            # Average confidence
            cursor.execute("SELECT AVG(confidence_score) FROM research_memory")
            avg_confidence = cursor.fetchone()[0] or 0.0

            # Oldest and newest timestamps
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM research_memory")
            min_ts, max_ts = cursor.fetchone()

            conn.close()

            return {
                "total_records": total_records,
                "records_by_type": by_type,
                "average_confidence": avg_confidence,
                "oldest_timestamp": min_ts,
                "newest_timestamp": max_ts,
            }

        except Exception as e:
            logger.error(f"Failed to get memory stats: {str(e)}")
            return {}


# Global singleton instance
_research_memory: Optional[ResearchMemory] = None


def get_research_memory(db_path: Optional[str] = None) -> ResearchMemory:
    """Get the global research memory singleton.

    Args:
        db_path: Optional database path

    Returns:
        ResearchMemory instance
    """
    global _research_memory
    if _research_memory is None:
        _research_memory = ResearchMemory(db_path)
    return _research_memory
