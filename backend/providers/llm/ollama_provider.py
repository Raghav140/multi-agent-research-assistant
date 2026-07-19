"""Ollama LLM provider implementation.

This module implements the LLMProvider interface using the local Ollama server.
It provides asynchronous text generation and chat completion capabilities.
"""

import time
from typing import Any, AsyncGenerator

import ollama
from ollama import AsyncClient

from backend.config.config import settings
from backend.core.exceptions import ExternalServiceException
from backend.core.interfaces import LLMProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation.

    This class implements the LLMProvider interface using the local Ollama
    server for text generation and chat completion.

    Attributes:
        host: Ollama server host URL
        model: Ollama model name
        timeout: Request timeout in seconds
        client: Async Ollama client
    """

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            host: Ollama server host URL (defaults to settings)
            model: Ollama model name (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
        """
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.client = AsyncClient(host=self.host, timeout=self.timeout)

        logger.info(
            f"Ollama provider initialized",
            extra={
                "host": self.host,
                "model": self.model,
                "timeout": self.timeout,
            },
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """Generate text completion for a given prompt.

        Args:
            prompt: Input prompt for text generation
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text completion

        Raises:
            ExternalServiceException: If generation fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"Ollama generate request",
            extra={
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_id": request_id,
                "prompt_length": len(prompt),
            },
        )

        try:
            response = await self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            execution_time = time.time() - start_time
            generated_text = response.get("response", "")

            logger.info(
                f"Ollama generate completed",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "response_length": len(generated_text),
                },
            )

            return generated_text

        except ollama.ResponseError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama response error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ResponseError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama response error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.RequestError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama request error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "RequestError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama request error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.ConnectionError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama connection error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectionError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama connection refused: {str(e)}",
                details={"error": str(e), "host": self.host},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Unexpected Ollama error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Unexpected Ollama error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate chat completion for a conversation.

        Args:
            messages: List of message dictionaries with role and content
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Dictionary containing response and metadata

        Raises:
            ExternalServiceException: If chat completion fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"Ollama chat request",
            extra={
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_id": request_id,
                "num_messages": len(messages),
            },
        )

        try:
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            execution_time = time.time() - start_time
            message = response.get("message", {})
            content = message.get("content", "")

            logger.info(
                f"Ollama chat completed",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "response_length": len(content),
                },
            )

            return {
                "content": content,
                "model": self.model,
                "finish_reason": response.get("done_reason", "stop"),
                "usage": {
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                    "total_tokens": response.get("prompt_eval_count", 0)
                    + response.get("eval_count", 0),
                },
            }

        except ollama.ResponseError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama response error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ResponseError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama response error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.RequestError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama request error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "RequestError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama request error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.ConnectionError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama connection error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectionError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama connection refused: {str(e)}",
                details={"error": str(e), "host": self.host},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Unexpected Ollama error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Unexpected Ollama error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

    async def stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text completion for a given prompt.

        Args:
            prompt: Input prompt for text generation
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            Generated text chunks

        Raises:
            ExternalServiceException: If streaming fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"Ollama stream request",
            extra={
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_id": request_id,
                "prompt_length": len(prompt),
            },
        )

        try:
            stream = await self.client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
                stream=True,
            )

            async for chunk in stream:
                if chunk.get("response"):
                    yield chunk["response"]

            execution_time = time.time() - start_time
            logger.info(
                f"Ollama stream completed",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                },
            )

        except ollama.ResponseError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama response error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ResponseError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama response error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.RequestError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama request error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "RequestError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama request error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )

        except ollama.ConnectionError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama connection error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectionError",
                },
            )
            raise ExternalServiceException(
                message=f"Ollama connection refused: {str(e)}",
                details={"error": str(e), "host": self.host},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Unexpected Ollama error: {str(e)}",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Unexpected Ollama error: {str(e)}",
                details={"error": str(e), "model": self.model},
            )
