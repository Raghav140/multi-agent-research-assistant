"""Application configuration using Pydantic Settings.

This module provides a production-ready configuration system with organized
settings classes, validation, and comprehensive documentation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-level settings.

    Attributes:
        app_name: Name of the application
        app_version: Current version of the application
        app_env: Environment (development, staging, production)
        debug: Enable debug mode
    """

    app_name: str = Field(
        default="multi-agent-research-assistant",
        description="Name of the application",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Current version of the application",
    )
    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Application environment",
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode",
    )

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ServerSettings(BaseSettings):
    """Server configuration settings.

    Attributes:
        host: Server host address
        port: Server port number (1-65535)
        workers: Number of worker processes
    """

    host: str = Field(
        default="0.0.0.0",
        description="Server host address",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number (1-65535)",
    )
    workers: int = Field(
        default=4,
        ge=1,
        le=64,
        description="Number of worker processes",
    )

    model_config = SettingsConfigDict(
        env_prefix="SERVER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings.

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log output format (json or text)
    """

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format",
    )

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class DatabaseSettings(BaseSettings):
    """Database configuration settings.

    Attributes:
        database_url: PostgreSQL connection URL
        database_pool_size: Connection pool size
        database_max_overflow: Maximum pool overflow
    """

    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/multi_agent_db",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Connection pool size",
    )
    database_max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum pool overflow",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must start with postgresql:// or postgresql+asyncpg://")
        return v

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class RedisSettings(BaseSettings):
    """Redis configuration settings.

    Attributes:
        redis_url: Redis connection URL
        redis_cache_ttl: Cache time-to-live in seconds
    """

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_cache_ttl: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache time-to-live in seconds",
    )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must start with redis://")
        return v

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class LLMSettings(BaseSettings):
    """LLM (Large Language Model) configuration settings.

    Attributes:
        openai_api_key: OpenAI API key
        openai_model: OpenAI model name
        openai_temperature: Sampling temperature (0.0-2.0)
        openai_max_tokens: Maximum tokens to generate
        ollama_host: Ollama server host URL
        ollama_model: Ollama model name
        ollama_timeout: Request timeout in seconds
    """

    openai_api_key: SecretStr = Field(
        default="",
        description="OpenAI API key",
    )
    openai_model: str = Field(
        default="gpt-4",
        description="OpenAI model name",
    )
    openai_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0)",
    )
    openai_max_tokens: int = Field(
        default=2000,
        ge=1,
        le=128000,
        description="Maximum tokens to generate",
    )

    model_config = SettingsConfigDict(
        env_prefix="OPENAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class OllamaSettings(BaseSettings):
    """Ollama configuration settings.

    Attributes:
        ollama_host: Ollama server host URL
        ollama_model: Ollama model name
        ollama_timeout: Request timeout in seconds
        ollama_disable_reasoning: Disable reasoning/thinking mode for models like Qwen3
        ollama_stream: Enable streaming responses (disabled by default for Qwen3)
    """

    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server host URL",
    )
    ollama_model: str = Field(
        default="qwen3:4b",
        description="Ollama model name",
    )
    ollama_timeout: int = Field(
        default=120,
        ge=1,
        le=600,
        description="Request timeout in seconds",
    )
    ollama_disable_reasoning: bool = Field(
        default=True,
        description="Disable reasoning/thinking mode for models like Qwen3",
    )
    ollama_stream: bool = Field(
        default=False,
        description="Enable streaming responses (disabled by default for Qwen3)",
    )

    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class RAGSettings(BaseSettings):
    """RAG (Retrieval-Augmented Generation) configuration settings.

    Attributes:
        chunk_size: Document chunk size in characters
        chunk_overlap: Chunk overlap in characters
        top_k_results: Number of top results to retrieve
    """

    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Document chunk size in characters",
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=5000,
        description="Chunk overlap in characters",
    )
    top_k_results: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of top results to retrieve",
    )

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class SecuritySettings(BaseSettings):
    """Security configuration settings.

    Attributes:
        secret_key: Secret key for JWT token signing
        algorithm: JWT algorithm
        access_token_expire_minutes: Access token expiration time
        cors_origins: Allowed CORS origins
        rate_limit_per_minute: Rate limit per minute
    """

    secret_key: SecretStr = Field(
        default="",
        description="Secret key for JWT token signing",
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT algorithm",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Access token expiration time in minutes",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Rate limit per minute",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class Settings:
    """Main settings class combining all configuration sections.

    This class aggregates all individual settings classes into a single
    configuration object for easy access throughout the application.
    """

    def __init__(
        self,
        app: AppSettings | None = None,
        server: ServerSettings | None = None,
        logging: LoggingSettings | None = None,
        database: DatabaseSettings | None = None,
        redis: RedisSettings | None = None,
        llm: LLMSettings | None = None,
        ollama: OllamaSettings | None = None,
        rag: RAGSettings | None = None,
        security: SecuritySettings | None = None,
    ) -> None:
        """Initialize settings with all configuration sections."""
        self.app = app or AppSettings()
        self.server = server or ServerSettings()
        self.logging = logging or LoggingSettings()
        self.database = database or DatabaseSettings()
        self.redis = redis or RedisSettings()
        self.llm = llm or LLMSettings()
        self.ollama = ollama or OllamaSettings()
        self.rag = rag or RAGSettings()
        self.security = security or SecuritySettings()

    # Convenience properties for backward compatibility
    @property
    def app_name(self) -> str:
        """Get application name."""
        return self.app.app_name

    @property
    def app_version(self) -> str:
        """Get application version."""
        return self.app.app_version

    @property
    def app_env(self) -> str:
        """Get application environment."""
        return self.app.app_env

    @property
    def debug(self) -> bool:
        """Get debug mode."""
        return self.app.debug

    @property
    def host(self) -> str:
        """Get server host."""
        return self.server.host

    @property
    def port(self) -> int:
        """Get server port."""
        return self.server.port

    @property
    def workers(self) -> int:
        """Get number of workers."""
        return self.server.workers

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self.logging.log_level

    @property
    def log_format(self) -> str:
        """Get log format."""
        return self.logging.log_format

    @property
    def database_url(self) -> str:
        """Get database URL."""
        return self.database.database_url

    @property
    def database_pool_size(self) -> int:
        """Get database pool size."""
        return self.database.database_pool_size

    @property
    def database_max_overflow(self) -> int:
        """Get database max overflow."""
        return self.database.database_max_overflow

    @property
    def redis_url(self) -> str:
        """Get Redis URL."""
        return self.redis.redis_url

    @property
    def redis_cache_ttl(self) -> int:
        """Get Redis cache TTL."""
        return self.redis.redis_cache_ttl

    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key."""
        return self.llm.openai_api_key.get_secret_value()

    @property
    def openai_model(self) -> str:
        """Get OpenAI model."""
        return self.llm.openai_model

    @property
    def openai_temperature(self) -> float:
        """Get OpenAI temperature."""
        return self.llm.openai_temperature

    @property
    def openai_max_tokens(self) -> int:
        """Get OpenAI max tokens."""
        return self.llm.openai_max_tokens

    @property
    def ollama_host(self) -> str:
        """Get Ollama host."""
        return self.ollama.ollama_host

    @property
    def ollama_model(self) -> str:
        """Get Ollama model."""
        return self.ollama.ollama_model

    @property
    def ollama_timeout(self) -> int:
        """Get Ollama timeout."""
        return self.ollama.ollama_timeout

    @property
    def ollama_disable_reasoning(self) -> bool:
        """Get Ollama disable reasoning setting."""
        return self.ollama.ollama_disable_reasoning

    @property
    def ollama_stream(self) -> bool:
        """Get Ollama stream setting."""
        return self.ollama.ollama_stream

    @property
    def chunk_size(self) -> int:
        """Get chunk size."""
        return self.rag.chunk_size

    @property
    def chunk_overlap(self) -> int:
        """Get chunk overlap."""
        return self.rag.chunk_overlap

    @property
    def top_k_results(self) -> int:
        """Get top K results."""
        return self.rag.top_k_results

    @property
    def secret_key(self) -> str:
        """Get secret key."""
        return self.security.secret_key.get_secret_value()

    @property
    def algorithm(self) -> str:
        """Get algorithm."""
        return self.security.algorithm

    @property
    def access_token_expire_minutes(self) -> int:
        """Get access token expire minutes."""
        return self.security.access_token_expire_minutes

    @property
    def cors_origins(self) -> list[str]:
        """Get CORS origins."""
        return self.security.cors_origins

    @property
    def rate_limit_per_minute(self) -> int:
        """Get rate limit per minute."""
        return self.security.rate_limit_per_minute


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings: Cached settings instance
    """
    return Settings()


settings = get_settings()
