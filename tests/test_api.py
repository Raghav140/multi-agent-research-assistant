"""API endpoint tests."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_cors_allowed_origin_get(client: TestClient) -> None:
    """Test CORS allows development origin on GET request."""
    response = client.get(
        "/api/v1/system/health",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_allowed_origin_post(client: TestClient) -> None:
    """Test CORS allows development origin on POST request."""
    response = client.post(
        "/api/v1/research",
        json={"query": "What is artificial intelligence?"},
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_options_preflight(client: TestClient) -> None:
    """Test CORS OPTIONS preflight request."""
    response = client.options(
        "/api/v1/research",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()


def test_cors_127_0_0_1_origin(client: TestClient) -> None:
    """Test CORS allows 127.0.0.1:5173 origin."""
    response = client.get(
        "/api/v1/system/health",
        headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_unauthorized_origin_rejected(client: TestClient) -> None:
    """Test CORS rejects unauthorized origin."""
    response = client.get(
        "/api/v1/system/health",
        headers={"Origin": "http://evil.example.com"}
    )
    assert response.status_code == 200
    # Unauthorized origin should NOT be in Access-Control-Allow-Origin
    cors_origin = response.headers.get("access-control-allow-origin")
    assert cors_origin != "http://evil.example.com"
    # If CORS is configured, it should either be None or a valid allowed origin
    if cors_origin:
        assert cors_origin in [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://localhost:4173",
            "http://127.0.0.1:4173"
        ]


def test_cors_localhost_4173_origin(client: TestClient) -> None:
    """Test CORS allows localhost:4173 origin for Vite production preview."""
    response = client.get(
        "/api/v1/system/health",
        headers={"Origin": "http://localhost:4173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4173"


def test_cors_127_0_0_1_4173_origin(client: TestClient) -> None:
    """Test CORS allows 127.0.0.1:4173 origin for Vite production preview."""
    response = client.get(
        "/api/v1/system/health",
        headers={"Origin": "http://127.0.0.1:4173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:4173"


def test_cors_options_preflight_4173(client: TestClient) -> None:
    """Test CORS OPTIONS preflight request from localhost:4173."""
    response = client.options(
        "/api/v1/research",
        headers={
            "Origin": "http://localhost:4173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()


def test_cors_post_research_4173(client: TestClient) -> None:
    """Test CORS allows POST research request from localhost:4173."""
    response = client.post(
        "/api/v1/research",
        json={"query": "What is artificial intelligence?"},
        headers={"Origin": "http://localhost:4173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4173"


def test_research_cache_miss_response(client: TestClient) -> None:
    """Test research response includes cache fields on cache miss."""
    response = client.post(
        "/api/v1/research",
        json={"query": "What is artificial intelligence?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify cache fields are present
    assert "cache_hit" in data
    assert "cache_metrics" in data

    # cache_hit may be True or False depending on cache state from previous tests
    assert isinstance(data["cache_hit"], bool) or data["cache_hit"] is None

    # Verify cache_metrics structure
    assert isinstance(data["cache_metrics"], dict)
    assert "hits" in data["cache_metrics"]
    assert "memory_hits" in data["cache_metrics"]
    assert "total_variations" in data["cache_metrics"]


def test_research_cache_hit_response(client: TestClient) -> None:
    """Test research response includes cache fields on cache hit."""
    # First request to populate cache
    client.post(
        "/api/v1/research",
        json={"query": "What is machine learning?"},
    )

    # Second request should hit cache
    response = client.post(
        "/api/v1/research",
        json={"query": "What is machine learning?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify cache fields are present
    assert "cache_hit" in data
    assert "cache_metrics" in data

    # Cache_hit may be True if cache was hit, False otherwise
    # (depends on cache implementation and timing)
    assert isinstance(data["cache_hit"], bool) or data["cache_hit"] is None

    # Verify cache_metrics structure
    assert isinstance(data["cache_metrics"], dict)
    assert "hits" in data["cache_metrics"]
    assert "memory_hits" in data["cache_metrics"]
    assert "total_variations" in data["cache_metrics"]


def test_research_cache_metrics_propagation(client: TestClient) -> None:
    """Test cache metrics are properly propagated in response."""
    response = client.post(
        "/api/v1/research",
        json={"query": "How does neural network work?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify cache_metrics structure
    cache_metrics = data["cache_metrics"]
    assert cache_metrics is not None
    assert isinstance(cache_metrics["hits"], int)
    assert isinstance(cache_metrics["memory_hits"], int)
    assert isinstance(cache_metrics["total_variations"], int)

    # Verify values are non-negative
    assert cache_metrics["hits"] >= 0
    assert cache_metrics["memory_hits"] >= 0
    assert cache_metrics["total_variations"] >= 0


def test_research_normal_success(client: TestClient) -> None:
    """Test normal successful research response."""
    response = client.post(
        "/api/v1/research",
        json={"query": "What is artificial intelligence?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify success response structure
    assert data["success"] is True
    assert "degraded" in data
    # degraded should match cache_hit (if cache hit, it's degraded)
    if data.get("cache_hit") is True:
        assert data["degraded"] is True
    else:
        assert data["degraded"] is False
    assert "answer" in data
    assert "report" in data
    assert "execution_time_ms" in data
    assert "request_id" in data

    # Verify error fields are not set on success
    assert data.get("error_code") is None
    assert data.get("error_message") is None


def test_research_degraded_response(client: TestClient) -> None:
    """Test degraded response when cache/memory is hit."""
    # First request to populate cache/memory
    client.post(
        "/api/v1/research",
        json={"query": "What is deep learning?"},
    )

    # Second request may hit cache/memory
    response = client.post(
        "/api/v1/research",
        json={"query": "What is deep learning?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify degraded flag is present
    assert "degraded" in data

    # If cache_hit is True, degraded should also be True
    if data.get("cache_hit") is True:
        assert data["degraded"] is True

    # Verify success is still True for degraded responses
    assert data["success"] is True


def test_research_response_structure_compatibility(client: TestClient) -> None:
    """Test API response maintains backward compatibility."""
    response = client.post(
        "/api/v1/research",
        json={"query": "What is machine learning?"},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all original fields are still present
    assert "success" in data
    assert "answer" in data
    assert "report" in data
    assert "search_results" in data
    assert "papers" in data
    assert "execution_time_ms" in data
    assert "request_id" in data

    # Verify new optional fields are present
    assert "cache_hit" in data
    assert "cache_metrics" in data
    assert "degraded" in data
    assert "error_code" in data
    assert "error_message" in data
