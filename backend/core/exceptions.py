"""Custom exception classes for the application.

This module defines a hierarchy of custom exceptions for handling different
types of application errors with appropriate HTTP status codes.
"""

from typing import Any


class BaseAppException(Exception):
    """Base exception for all application errors.

    All custom exceptions should inherit from this class to ensure
    consistent error handling and response formatting.

    Attributes:
        message: Human-readable error message
        details: Additional error details
        status_code: HTTP status code to return
    """

    def __init__(
        self,
        message: str,
        details: str | dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        """Initialize the base application exception.

        Args:
            message: Human-readable error message
            details: Additional error details (string or dictionary)
            status_code: HTTP status code to return
        """
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class ValidationException(BaseAppException):
    """Exception raised for validation errors.

    Used when input data fails validation rules.

    Attributes:
        message: Human-readable error message
        details: Validation error details
    """

    def __init__(
        self,
        message: str = "Validation error",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize validation exception.

        Args:
            message: Human-readable error message
            details: Validation error details
        """
        super().__init__(message=message, details=details, status_code=422)


class NotFoundException(BaseAppException):
    """Exception raised when a resource is not found.

    Used when requested resources cannot be located.

    Attributes:
        message: Human-readable error message
        details: Additional details about the missing resource
    """

    def __init__(
        self,
        message: str = "Resource not found",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize not found exception.

        Args:
            message: Human-readable error message
            details: Additional details about the missing resource
        """
        super().__init__(message=message, details=details, status_code=404)


class AuthenticationException(BaseAppException):
    """Exception raised for authentication failures.

    Used when user authentication fails or credentials are invalid.

    Attributes:
        message: Human-readable error message
        details: Additional authentication details
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize authentication exception.

        Args:
            message: Human-readable error message
            details: Additional authentication details
        """
        super().__init__(message=message, details=details, status_code=401)


class AuthorizationException(BaseAppException):
    """Exception raised for authorization failures.

    Used when authenticated user lacks permission for an action.

    Attributes:
        message: Human-readable error message
        details: Additional authorization details
    """

    def __init__(
        self,
        message: str = "Authorization failed",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize authorization exception.

        Args:
            message: Human-readable error message
            details: Additional authorization details
        """
        super().__init__(message=message, details=details, status_code=403)


class ExternalServiceException(BaseAppException):
    """Exception raised for external service failures.

    Used when external APIs or services fail to respond.

    Attributes:
        message: Human-readable error message
        details: Service-specific error details
    """

    def __init__(
        self,
        message: str = "External service error",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize external service exception.

        Args:
            message: Human-readable error message
            details: Service-specific error details
        """
        super().__init__(message=message, details=details, status_code=502)


class AgentException(BaseAppException):
    """Exception raised for AI agent failures.

    Used when AI agents fail to execute tasks or encounter errors.

    Attributes:
        message: Human-readable error message
        details: Agent-specific error details
    """

    def __init__(
        self,
        message: str = "Agent execution error",
        details: str | dict[str, Any] | None = None,
    ) -> None:
        """Initialize agent exception.

        Args:
            message: Human-readable error message
            details: Agent-specific error details
        """
        super().__init__(message=message, details=details, status_code=500)
