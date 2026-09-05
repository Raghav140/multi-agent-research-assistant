"""Tests for production startup configuration.

This module tests production startup behavior including debug mode,
API docs availability, and configuration validation.
"""

import pytest
from fastapi.testclient import TestClient

from backend.config.main import app
from backend.config.config import settings


class TestProductionStartup:
    """Test production startup configuration."""

    def test_app_entrypoint_exists(self):
        """Test that the application entrypoint exists and is callable."""
        # Verify the FastAPI app exists
        assert app is not None
        assert hasattr(app, 'routes')
        assert len(app.routes) > 0

    def test_debug_mode_configuration(self):
        """Test that debug mode is configured from settings."""
        # Debug should be a boolean
        assert isinstance(settings.debug, bool)
        # Debug mode controls docs availability
        # This is tested by checking the app configuration

    def test_docs_url_configuration(self):
        """Test that docs URL is configured based on debug mode."""
        # In production (debug=False), docs_url should be None
        # In development (debug=True), docs_url should be "/docs"
        if settings.debug:
            assert app.docs_url == "/docs"
            assert app.redoc_url == "/redoc"
        else:
            assert app.docs_url is None
            assert app.redoc_url is None

    def test_root_endpoint_accessible(self):
        """Test that root endpoint is always accessible."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()

    def test_health_endpoint_accessible(self):
        """Test that health endpoint is accessible regardless of debug mode."""
        client = TestClient(app)
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_cors_middleware_configured(self):
        """Test that CORS middleware is configured."""
        # Check that CORS middleware is present
        cors_found = False
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware.cls):
                cors_found = True
                break
        assert cors_found, "CORS middleware should be configured"

    def test_lifespan_manager_configured(self):
        """Test that lifespan manager is configured."""
        # Check that lifespan is configured
        assert app.router.lifespan_context is not None

    def test_exception_handlers_registered(self):
        """Test that exception handlers are registered."""
        # Check that exception handlers are registered
        assert len(app.exception_handlers) > 0

    def test_routes_registered(self):
        """Test that API routes are registered."""
        # Check that the app has routes (including routers)
        assert len(app.routes) > 0

    def test_production_environment_set(self):
        """Test that production environment is set correctly."""
        # Environment should be one of the valid values
        assert settings.app_env in ["development", "staging", "production"]

    def test_server_configuration_valid(self):
        """Test that server configuration values are valid."""
        # Server configuration should be valid
        assert isinstance(settings.host, str)
        assert isinstance(settings.port, int)
        assert 1 <= settings.port <= 65535
