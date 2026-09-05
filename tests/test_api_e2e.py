"""End-to-end API tests for the research workflow."""

import pytest
from fastapi.testclient import TestClient

from backend.config.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_api_research_endpoint_schema_validation(client):
    """Test API research endpoint validates input schema."""
    # Missing query field
    response = client.post(
        "/api/v1/research",
        json={}
    )

    assert response.status_code == 422  # Validation error


def test_api_research_endpoint_empty_query(client):
    """Test API research endpoint handles empty query."""
    response = client.post(
        "/api/v1/research",
        json={"query": ""}
    )

    # Should handle gracefully may return error or fallback
    assert response.status_code in [200, 400, 422]


def test_api_research_endpoint_method_not_allowed(client):
    """Test API research endpoint rejects invalid methods."""
    response = client.get("/api/v1/research")
    assert response.status_code == 405

    response = client.put("/api/v1/research", json={"query": "test"})
    assert response.status_code == 405

    response = client.delete("/api/v1/research")
    assert response.status_code == 405


def test_api_health_endpoint(client):
    """Test API health endpoint."""
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    data = response.json()

    # Verify health check structure
    assert "status" in data
    assert "providers" in data
    assert "cache" in data
    assert "memory" in data


def test_api_metrics_endpoint(client):
    """Test API metrics endpoint."""
    response = client.get("/api/v1/system/metrics")

    assert response.status_code == 200
    data = response.json()

    # Verify metrics structure
    assert "averages" in data
    assert "by_provider" in data


def test_api_metrics_summary_endpoint(client):
    """Test API metrics summary endpoint."""
    response = client.get("/api/v1/system/metrics/summary")

    assert response.status_code == 200
    data = response.json()

    # Verify summary structure
    assert "request_count" in data
    assert "cache_hit_rate" in data
    assert "average_confidence" in data


def test_api_providers_health_endpoint(client):
    """Test API providers health endpoint."""
    response = client.get("/api/v1/system/providers/health")

    assert response.status_code == 200
    data = response.json()

    # Verify providers structure
    assert "providers" in data
    assert isinstance(data["providers"], list)


def test_api_cache_stats_endpoint(client):
    """Test API cache stats endpoint."""
    response = client.get("/api/v1/system/cache/stats")

    assert response.status_code == 200
    data = response.json()

    # Verify cache stats structure
    assert isinstance(data, dict)


def test_api_memory_history_endpoint(client):
    """Test API memory history endpoint."""
    response = client.get("/api/v1/system/memory/history")

    assert response.status_code == 200
    data = response.json()

    # Verify memory history structure
    assert "records" in data
    assert "stats" in data
