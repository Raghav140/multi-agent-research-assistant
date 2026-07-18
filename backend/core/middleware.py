"""Middleware for FastAPI application.

This module provides middleware for request ID generation and other
cross-cutting concerns.
"""

import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and attach request IDs to all requests.

    This middleware generates a unique request ID for each incoming request
    and attaches it to the request state for use in logging and error handling.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the request ID middleware.

        Args:
            app: ASGI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> dict:
        """Process request and attach request ID.

        Args:
            request: Incoming request
            call_next: Next middleware or route handler

        Returns:
            Response from the next middleware/route handler
        """
        # Check if request ID is already present in headers
        request_id = request.headers.get("X-Request-ID")

        # Generate new request ID if not present
        if not request_id:
            request_id = str(uuid.uuid4())

        # Attach request ID to request state
        request.state.request_id = request_id

        # Add request ID to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Log request with request ID
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None,
            },
        )

        return response
