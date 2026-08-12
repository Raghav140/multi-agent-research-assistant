"""SQLite-based storage for evaluation metrics.

This module provides persistent storage for retrieval and answer quality metrics.
"""

import sqlite3
import json
import time
from typing import Any, Dict, Optional
from pathlib import Path
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

# Database schema
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS evaluation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    request_id TEXT,
    query TEXT NOT NULL,
    query_type TEXT NOT NULL,

    -- Retrieval metrics
    providers_used TEXT,
    sources_found INTEGER,
    sources_selected INTEGER,
    selection_rate REAL,
    source_quality_score REAL,
    evidence_diversity REAL,
    confidence_score REAL,
    execution_time_ms REAL,

    -- Answer metrics
    structure_score REAL,
    leakage_score REAL,
    hallucination_risk REAL,
    citation_score REAL,

    -- Additional metadata
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON evaluation_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_type ON evaluation_metrics(query_type);
CREATE INDEX IF NOT EXISTS idx_request_id ON evaluation_metrics(request_id);
"""


class MetricsStorage:
    """SQLite-based storage for evaluation metrics.

    This class provides persistent storage for retrieval and answer quality metrics.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the metrics storage.

        Args:
            db_path: Path to SQLite database file (default: ./evaluation_metrics.db)
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "evaluation_metrics.db")

        self.db_path = db_path
        self._initialize_database()

        logger.info(
            f"Metrics storage initialized",
            extra={"db_path": db_path},
        )

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Execute schema creation
            cursor.executescript(CREATE_TABLE_SQL)

            conn.commit()
            conn.close()

            logger.info("Metrics database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize metrics database: {str(e)}")
            raise

    def store_metrics(
        self,
        query: str,
        query_type: str,
        request_id: Optional[str] = None,
        retrieval_metrics: Optional[Dict[str, Any]] = None,
        answer_metrics: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Store evaluation metrics.

        Args:
            query: Search query
            query_type: Query category
            request_id: Request identifier
            retrieval_metrics: Retrieval quality metrics
            answer_metrics: Answer quality metrics
            metadata: Additional metadata

        Returns:
            Record ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Serialize complex fields
            providers_used = json.dumps(retrieval_metrics.get("providers_used", [])) if retrieval_metrics else "[]"
            metadata_json = json.dumps(metadata) if metadata else "{}"

            # Insert record
            cursor.execute(
                """
                INSERT INTO evaluation_metrics
                (timestamp, request_id, query, query_type, providers_used, sources_found, sources_selected,
                 selection_rate, source_quality_score, evidence_diversity, confidence_score, execution_time_ms,
                 structure_score, leakage_score, hallucination_risk, citation_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    request_id,
                    query,
                    query_type,
                    providers_used,
                    retrieval_metrics.get("sources_found", 0) if retrieval_metrics else 0,
                    retrieval_metrics.get("sources_selected", 0) if retrieval_metrics else 0,
                    retrieval_metrics.get("selection_rate", 0.0) if retrieval_metrics else 0.0,
                    retrieval_metrics.get("source_quality_score", 0.0) if retrieval_metrics else 0.0,
                    retrieval_metrics.get("evidence_diversity", 0.0) if retrieval_metrics else 0.0,
                    retrieval_metrics.get("confidence_score", 0.0) if retrieval_metrics else 0.0,
                    retrieval_metrics.get("execution_time_ms", 0.0) if retrieval_metrics else 0.0,
                    answer_metrics.get("structure_score", 0.0) if answer_metrics else 0.0,
                    answer_metrics.get("leakage_score", 0.0) if answer_metrics else 0.0,
                    answer_metrics.get("hallucination_risk", 0.0) if answer_metrics else 0.0,
                    answer_metrics.get("citation_score", 0.0) if answer_metrics else 0.0,
                    metadata_json,
                ),
            )

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(
                f"Metrics stored in database",
                extra={
                    "record_id": record_id,
                    "query": query,
                    "query_type": query_type,
                    "request_id": request_id,
                },
            )

            return record_id

        except Exception as e:
            logger.error(f"Failed to store metrics: {str(e)}")
            raise

    def get_metrics(
        self,
        query_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Dict[str, Any]]:
        """Get stored metrics.

        Args:
            query_type: Optional query type filter
            limit: Maximum number of records to return
            offset: Offset for pagination

        Returns:
            List of metric records
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if query_type:
                cursor.execute(
                    """
                    SELECT id, timestamp, request_id, query, query_type, providers_used, sources_found,
                           sources_selected, selection_rate, source_quality_score, evidence_diversity,
                           confidence_score, execution_time_ms, structure_score, leakage_score,
                           hallucination_risk, citation_score, metadata
                    FROM evaluation_metrics
                    WHERE query_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (query_type, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, timestamp, request_id, query, query_type, providers_used, sources_found,
                           sources_selected, selection_rate, source_quality_score, evidence_diversity,
                           confidence_score, execution_time_ms, structure_score, leakage_score,
                           hallucination_risk, citation_score, metadata
                    FROM evaluation_metrics
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            records = cursor.fetchall()
            conn.close()

            results = []
            for record in records:
                (record_id, timestamp, request_id, query, qtype, providers_json,
                 sources_found, sources_selected, selection_rate, source_quality,
                 diversity, confidence, exec_time, structure, leakage,
                 hallucination, citation, metadata_json) = record

                results.append({
                    "id": record_id,
                    "timestamp": timestamp,
                    "request_id": request_id,
                    "query": query,
                    "query_type": qtype,
                    "providers_used": json.loads(providers_json) if providers_json else [],
                    "sources_found": sources_found,
                    "sources_selected": sources_selected,
                    "selection_rate": selection_rate,
                    "source_quality_score": source_quality,
                    "evidence_diversity": diversity,
                    "confidence_score": confidence,
                    "execution_time_ms": exec_time,
                    "structure_score": structure,
                    "leakage_score": leakage,
                    "hallucination_risk": hallucination,
                    "citation_score": citation,
                    "metadata": json.loads(metadata_json) if metadata_json else {},
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get metrics: {str(e)}")
            return []

    def get_aggregated_metrics(
        self,
        query_type: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get aggregated metrics over time period.

        Args:
            query_type: Optional query type filter
            days: Number of days to aggregate

        Returns:
            Dictionary with aggregated metrics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_time = time.time() - (days * 24 * 60 * 60)

            if query_type:
                cursor.execute(
                    """
                    SELECT COUNT(*), AVG(source_quality_score), AVG(evidence_diversity),
                           AVG(confidence_score), AVG(execution_time_ms), AVG(citation_score)
                    FROM evaluation_metrics
                    WHERE query_type = ? AND timestamp >= ?
                    """,
                    (query_type, cutoff_time),
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*), AVG(source_quality_score), AVG(evidence_diversity),
                           AVG(confidence_score), AVG(execution_time_ms), AVG(citation_score)
                    FROM evaluation_metrics
                    WHERE timestamp >= ?
                    """,
                    (cutoff_time,),
                )

            record = cursor.fetchone()
            conn.close()

            if not record:
                return {}

            return {
                "count": record[0],
                "avg_source_quality": record[1] or 0.0,
                "avg_evidence_diversity": record[2] or 0.0,
                "avg_confidence": record[3] or 0.0,
                "avg_execution_time_ms": record[4] or 0.0,
                "avg_citation_score": record[5] or 0.0,
            }

        except Exception as e:
            logger.error(f"Failed to get aggregated metrics: {str(e)}")
            return {}

    def clear_old_metrics(self, days: int = 30) -> int:
        """Clear metrics older than specified days.

        Args:
            days: Number of days to keep metrics

        Returns:
            Number of records deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_time = time.time() - (days * 24 * 60 * 60)

            cursor.execute(
                """
                DELETE FROM evaluation_metrics
                WHERE timestamp < ?
                """,
                (cutoff_time,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(
                f"Cleared old metrics",
                extra={
                    "days": days,
                    "deleted_count": deleted_count,
                },
            )

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to clear old metrics: {str(e)}")
            return 0


# Global singleton instance
_metrics_storage: Optional[MetricsStorage] = None


def get_metrics_storage(db_path: Optional[str] = None) -> MetricsStorage:
    """Get the global metrics storage singleton.

    Args:
        db_path: Optional database path

    Returns:
        MetricsStorage instance
    """
    global _metrics_storage
    if _metrics_storage is None:
        _metrics_storage = MetricsStorage(db_path)
    return _metrics_storage
