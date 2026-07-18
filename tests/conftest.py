"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from backend.config.main import app


@pytest.fixture
def client():
    """Get test client."""
    return TestClient(app)
