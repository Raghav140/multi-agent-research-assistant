"""Tests for SQLite database path configuration.

This module tests the configurable SQLite database paths for research memory
and evaluation metrics storage.
"""

import os
import tempfile
from pathlib import Path
import pytest
import sqlite3

from backend.memory.research_memory import ResearchMemory, get_research_memory
from backend.utils.metrics_storage import MetricsStorage, get_metrics_storage


class TestSQLitePathConfiguration:
    """Test SQLite database path configuration."""

    def test_default_research_memory_path(self):
        """Test that research memory uses default path when not configured."""
        # Reset singleton
        import backend.memory.research_memory as rm_module
        rm_module._research_memory = None

        # Create with default path
        memory = ResearchMemory()
        assert memory.db_path.endswith("research_memory.db")

    def test_custom_research_memory_path(self):
        """Test that research memory uses custom path when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom_memory.db")
            memory = ResearchMemory(db_path=custom_path)
            assert memory.db_path == custom_path

    def test_research_memory_directory_creation(self):
        """Test that research memory creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "nested", "dir")
            custom_path = os.path.join(nested_dir, "memory.db")

            # Directory should not exist yet
            assert not os.path.exists(nested_dir)

            # Create memory - should create directory
            memory = ResearchMemory(db_path=custom_path)

            # Directory should now exist
            assert os.path.exists(nested_dir)
            assert os.path.exists(custom_path)

    def test_research_memory_stores_data(self):
        """Test that research memory can store data with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "test_memory.db")
            memory = ResearchMemory(db_path=custom_path)

            # Store some data
            record_id = memory.store_research(
                query="test query",
                query_type="definition",
                sources_used=[],
                final_summary="test summary",
                confidence_score=0.9,
            )

            assert record_id > 0

            # Verify data was stored in the correct location
            assert os.path.exists(custom_path)

            # Verify we can retrieve it
            retrieved = memory.get_research_by_id(record_id)
            assert retrieved is not None
            assert retrieved["query"] == "test query"

    def test_default_metrics_storage_path(self):
        """Test that metrics storage uses default path when not configured."""
        # Reset singleton
        import backend.utils.metrics_storage as ms_module
        ms_module._metrics_storage = None

        # Create with default path
        storage = MetricsStorage()
        assert storage.db_path.endswith("evaluation_metrics.db")

    def test_custom_metrics_storage_path(self):
        """Test that metrics storage uses custom path when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom_metrics.db")
            storage = MetricsStorage(db_path=custom_path)
            assert storage.db_path == custom_path

    def test_metrics_storage_directory_creation(self):
        """Test that metrics storage creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "nested", "metrics")
            custom_path = os.path.join(nested_dir, "metrics.db")

            # Directory should not exist yet
            assert not os.path.exists(nested_dir)

            # Create storage - should create directory
            storage = MetricsStorage(db_path=custom_path)

            # Directory should now exist
            assert os.path.exists(nested_dir)
            assert os.path.exists(custom_path)

    def test_metrics_storage_stores_data(self):
        """Test that metrics storage can store data with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "test_metrics.db")
            storage = MetricsStorage(db_path=custom_path)

            # Store some metrics
            record_id = storage.store_metrics(
                query="test query",
                query_type="definition",
                retrieval_metrics={
                    "sources_found": 5,
                    "sources_selected": 3,
                    "selection_rate": 0.6,
                },
                answer_metrics={
                    "structure_score": 0.8,
                    "citation_score": 0.9,
                },
            )

            assert record_id > 0

            # Verify data was stored in the correct location
            assert os.path.exists(custom_path)

            # Verify we can retrieve it
            metrics = storage.get_metrics(limit=1)
            assert len(metrics) > 0
            assert metrics[0]["query"] == "test query"

    def test_no_data_loss_on_path_change(self):
        """Test that existing data is not lost when using a custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create memory with one path
            path1 = os.path.join(tmpdir, "memory1.db")
            memory1 = ResearchMemory(db_path=path1)

            record_id = memory1.store_research(
                query="test query",
                query_type="definition",
                sources_used=[],
                final_summary="test summary",
                confidence_score=0.9,
            )

            # Create memory with different path
            path2 = os.path.join(tmpdir, "memory2.db")
            memory2 = ResearchMemory(db_path=path2)

            # First database should still exist and have data
            assert os.path.exists(path1)
            retrieved = memory1.get_research_by_id(record_id)
            assert retrieved is not None

            # Second database should be empty
            assert os.path.exists(path2)
            empty_retrieved = memory2.get_research_by_id(record_id)
            assert empty_retrieved is None

    def test_relative_path_handling(self):
        """Test that relative paths are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_dir = os.getcwd()
            os.chdir(tmpdir)

            try:
                # Use relative path
                memory = ResearchMemory(db_path="./relative_memory.db")

                # Should create file in current directory
                assert os.path.exists("relative_memory.db")
                assert memory.db_path == "./relative_memory.db"

            finally:
                os.chdir(original_dir)

    def test_absolute_path_handling(self):
        """Test that absolute paths are handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "absolute_memory.db")
            memory = ResearchMemory(db_path=custom_path)

            assert memory.db_path == custom_path
            assert os.path.exists(custom_path)
