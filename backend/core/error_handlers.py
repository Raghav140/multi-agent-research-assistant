"""Global exception handlers for FastAPI application.

This module provides centralized exception handling with consistent error responses,
logging, and appropriate HTTP status codes.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.config.config import settings
from backend.core.exceptions import (
    AgentException,
    AuthenticationException,
    AuthorizationException,
    BaseAppException,
    ExternalServiceException,
    NotFoundException,
    ValidationException,
)
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class ErrorResponse(BaseModel):
    """Standard error response model.

    Attributes:
        success: Always false for error responses
        error: Error details including code, message, details, timestamp, and request_id
    """

    success: bool = False
    error: dict[str, Any]


def get_request_id(request: Request) -> str:
    """Get or generate request ID.

    Args:
        request: FastAPI request object

    Returns:
        Request ID string
    """
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())
    return request_id


def format_error_response(
    code: str,
    message: str,
    details: str | dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Format standard error response.

    Args:
        code: Error code
        message: Error message
        details: Additional error details
        request_id: Request identifier

    Returns:
        Formatted error response dictionary
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
        },
    }


async def base_app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """Handle BaseAppException and its subclasses.

    Args:
        request: FastAPI request object
        exc: BaseAppException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)
    error_code = f"{exc.__class__.__name__.upper()}_ERROR"

    # Log the exception
    logger.error(
        f"Application error: {exc.message}",
        extra={
            "request_id": request_id,
            "exception_type": exc.__class__.__name__,
            "status_code": exc.status_code,
            "details": exc.details,
        },
    )

    # Hide internal details in production
    if settings.app_env == "production":
        details = {"error": "An internal error occurred"}
    else:
        details = exc.details

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code=error_code,
            message=exc.message,
            details=details,
            request_id=request_id,
        ),
    )


async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """Handle ValidationException.

    Args:
        request: FastAPI request object
        exc: ValidationException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.warning(
        f"Validation error: {exc.message}",
        extra={
            "request_id": request_id,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="VALIDATION_ERROR",
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def not_found_exception_handler(request: Request, exc: NotFoundException) -> JSONResponse:
    """Handle NotFoundException.

    Args:
        request: FastAPI request object
        exc: NotFoundException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.warning(
        f"Not found error: {exc.message}",
        extra={
            "request_id": request_id,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="NOT_FOUND_ERROR",
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def authentication_exception_handler(
    request: Request, exc: AuthenticationException
) -> JSONResponse:
    """Handle AuthenticationException.

    Args:
        request: FastAPI request object
        exc: AuthenticationException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.warning(
        f"Authentication error: {exc.message}",
        extra={
            "request_id": request_id,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="AUTHENTICATION_ERROR",
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def authorization_exception_handler(
    request: Request, exc: AuthorizationException
) -> JSONResponse:
    """Handle AuthorizationException.

    Args:
        request: FastAPI request object
        exc: AuthorizationException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.warning(
        f"Authorization error: {exc.message}",
        extra={
            "request_id": request_id,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="AUTHORIZATION_ERROR",
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def external_service_exception_handler(
    request: Request, exc: ExternalServiceException
) -> JSONResponse:
    """Handle ExternalServiceException.

    Args:
        request: FastAPI request object
        exc: ExternalServiceException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.error(
        f"External service error: {exc.message}",
        extra={
            "request_id": request_id,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="EXTERNAL_SERVICE_ERROR",
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def agent_exception_handler(request: Request, exc: AgentException) -> JSONResponse:
    """Handle AgentException.

    Args:
        request: FastAPI request object
        exc: AgentException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.error(
        f"Agent execution error: {exc.message}",
        extra={
            "request_id": request_id,
            "details": exc.details,
        },
    )

    # Hide internal details in production
    if settings.app_env == "production":
        details = {"error": "Agent execution failed"}
    else:
        details = exc.details

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="AGENT_ERROR",
            message=exc.message,
            details=details,
            request_id=request_id,
        ),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException.

    Args:
        request: FastAPI request object
        exc: HTTPException instance

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.warning(
        f"HTTP error: {exc.detail}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={},
            request_id=request_id,
        ),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all uncaught exceptions.

    Args:
        request: FastAPI request object
        exc: Uncaught exception

    Returns:
        JSONResponse with formatted error
    """
    request_id = get_request_id(request)

    logger.exception(
        f"Unhandled exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "exception_type": exc.__class__.__name__,
        },
    )

    # Hide stack traces in production
    if settings.app_env == "production":
        message = "An internal server error occurred"
        details = {}
    else:
        message = str(exc)
        details = {"exception_type": exc.__class__.__name__}

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=format_error_response(
            code="INTERNAL_SERVER_ERROR",
            message=message,
            details=details,
            request_id=request_id,
        ),
    )
