"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.research import research_router
from backend.api.routes import router
from backend.config.config import settings
from backend.config import dependencies  # Initialize singleton providers
from backend.core.error_handlers import (
    agent_exception_handler,
    authentication_exception_handler,
    authorization_exception_handler,
    external_service_exception_handler,
    general_exception_handler,
    http_exception_handler,
    not_found_exception_handler,
    validation_exception_handler,
)
from backend.core.exceptions import (
    AgentException,
    AuthenticationException,
    AuthorizationException,
    ExternalServiceException,
    NotFoundException,
    ValidationException,
)
from backend.core.middleware import RequestIDMiddleware
from backend.utils.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        environment=settings.app_env,
    )
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A production-ready multi-agent AI research assistant",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Request ID middleware
app.add_middleware(RequestIDMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(ValidationException, validation_exception_handler)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(AuthenticationException, authentication_exception_handler)
app.add_exception_handler(AuthorizationException, authorization_exception_handler)
app.add_exception_handler(ExternalServiceException, external_service_exception_handler)
app.add_exception_handler(AgentException, agent_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(router, prefix="/api/v1")
app.include_router(research_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Multi-Agent Research Assistant API",
        "version": settings.app_version,
    }
