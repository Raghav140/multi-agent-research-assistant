"""Ollama LLM provider implementation.

This module implements the LLMProvider interface using the local Ollama server.
It provides asynchronous text generation and chat completion capabilities.
"""

import time
from typing import Any, AsyncGenerator

import ollama
from ollama import AsyncClient

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
        disable_reasoning: bool | None = None,
        stream: bool | None = None,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            host: Ollama server host URL (defaults to settings)
            model: Ollama model name (defaults to settings)
            timeout: Request timeout in seconds (defaults to settings)
            disable_reasoning: Disable reasoning/thinking mode (defaults to settings)
            stream: Enable streaming responses (defaults to settings)
        """
        # Lazy import to avoid circular dependency
        from backend.config.config import settings

        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.disable_reasoning = (
            disable_reasoning if disable_reasoning is not None
            else settings.ollama_disable_reasoning
        )
        self.stream = stream if stream is not None else settings.ollama_stream
        self.client = AsyncClient(host=self.host, timeout=self.timeout)

        logger.info(
            f"Ollama provider initialized",
            extra={
                "host": self.host,
                "model": self.model,
                "timeout": self.timeout,
                "disable_reasoning": self.disable_reasoning,
                "stream": self.stream,
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
        function_name = kwargs.get("function_name", "generate")

        logger.info(
            f"Ollama generate request",
            extra={
                "model": self.model,
                "function_name": function_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_id": request_id,
                "prompt_length": len(prompt),
            },
        )

        try:
            # Build options for Ollama API (optimized for speed)
            options = {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_k": 10,  # Reduced from 20 for faster sampling
                "top_p": 0.9,  # Increased from 0.8 for more focused sampling
                "repeat_penalty": 1.15,  # Increased from 1.1 to reduce repetition
            }

            # Disable reasoning mode for Qwen3 if configured
            if self.disable_reasoning:
                options["reasoning_mode"] = False

            # Log the exact payload being sent (excluding prompt text)
            logger.info(
                "Ollama API request payload",
                extra={
                    "model": self.model,
                    "function_name": function_name,
                    "request_id": request_id,
                    "options": options,
                    "stream": False,
                    "keep_alive": "10m",
                    "think": False,
                    "disable_reasoning": self.disable_reasoning,
                    "prompt_length_chars": len(prompt),
                    "prompt_length_words": len(prompt.split()),
                },
            )

            # Wrap with timeout
            import asyncio
            think_parameter_used = True
            try:
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=self.model,
                        prompt=prompt,
                        options=options,
                        stream=False,  # Ensure streaming is disabled
                        keep_alive="10m",  # Keep model loaded for 10 minutes
                        think=False,  # Disable thinking mode
                    ),
                    timeout=self.timeout,
                )
            except TypeError:
                # Fallback if think parameter is not supported
                logger.warning(
                    "Ollama think parameter not supported, using fallback",
                    extra={
                        "model": self.model,
                        "function_name": function_name,
                        "request_id": request_id,
                    },
                )
                response = await asyncio.wait_for(
                    self.client.generate(
                        model=self.model,
                        prompt=prompt,
                        options=options,
                        stream=False,  # Ensure streaming is disabled
                        keep_alive="10m",  # Keep model loaded for 10 minutes
                    ),
                    timeout=self.timeout,
                )
                think_parameter_used = False

            execution_time = time.time() - start_time
            
            # Extract response - never return internal reasoning as the answer
            generated_text = response.get("response", "")
            if not generated_text:
                logger.error(
                    f"Ollama returned empty response",
                    extra={
                        "model": self.model,
                        "request_id": request_id,
                        "has_thinking": bool(response.get("thinking")),
                    },
                )
                raise ExternalServiceException(
                    message="Ollama returned empty response",
                    details={"model": self.model, "has_thinking": bool(response.get("thinking"))},
                )

            # Extract detailed metrics
            eval_count = response.get("eval_count", 0)
            prompt_eval_count = response.get("prompt_eval_count", 0)
            prompt_eval_duration = response.get("prompt_eval_duration", 0)
            eval_duration = response.get("eval_duration", 0)
            load_duration = response.get("load_duration", 0)
            total_duration = response.get("total_duration", 0)
            
            # Estimate prompt tokens (rough approximation: 4 chars per token)
            estimated_prompt_tokens = len(prompt) // 4

            # Detect runaway reasoning
            if eval_count > max_tokens * 0.8:
                logger.warning(
                    f"Large completion detected",
                    extra={
                        "model": self.model,
                        "request_id": request_id,
                        "eval_count": eval_count,
                        "max_tokens": max_tokens,
                        "threshold": max_tokens * 0.8,
                    },
                )

            # Calculate tokens per second and average ms per token
            tokens_per_second = eval_count / execution_time if execution_time > 0 else 0
            avg_ms_per_token = (execution_time * 1000) / eval_count if eval_count > 0 else 0

            # Determine bottleneck type
            if load_duration > eval_duration:
                bottleneck_type = "model_load"
            elif prompt_eval_duration > eval_duration:
                bottleneck_type = "prompt_processing"
            else:
                bottleneck_type = "token_generation"

            logger.info(
                f"Ollama generate completed",
                extra={
                    "model": self.model,
                    "function_name": function_name,
                    "execution_time": execution_time,
                    "execution_time_ms": execution_time * 1000,
                    "request_id": request_id,
                    "response_length": len(generated_text),
                    "disable_reasoning": self.disable_reasoning,
                    "reasoning_mode": self.disable_reasoning,
                    "requested_tokens": max_tokens,
                    "returned_tokens": eval_count,
                    "prompt_length": len(prompt),
                    "prompt_length_chars": len(prompt),
                    "prompt_length_words": len(prompt.split()),
                    "estimated_prompt_tokens": estimated_prompt_tokens,
                    "prompt_eval_count": prompt_eval_count,
                    "prompt_eval_duration_ms": prompt_eval_duration / 1_000_000,
                    "eval_duration_ms": eval_duration / 1_000_000,
                    "load_duration_ms": load_duration / 1_000_000,
                    "total_duration_ms": total_duration / 1_000_000,
                    "tokens_per_second": tokens_per_second,
                    "avg_ms_per_token": avg_ms_per_token,
                    "bottleneck_type": bottleneck_type,
                    "think_parameter_used": think_parameter_used,
                    "keep_alive": "10m",
                },
            )

            return generated_text

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama generate timeout after {execution_time:.2f}s",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "timeout": self.timeout,
                },
            )
            raise ExternalServiceException(
                f"LLM generation timeout after {self.timeout}s",
                details={"error": "TimeoutError", "timeout": self.timeout},
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
        function_name = kwargs.get("function_name", "chat")

        logger.info(
            f"Ollama chat request",
            extra={
                "model": self.model,
                "function_name": function_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "request_id": request_id,
                "num_messages": len(messages),
            },
        )

        try:
            # Build options for Ollama API
            options = {
                "temperature": temperature,
                "num_predict": max_tokens,
            }

            # Disable reasoning mode for Qwen3 if configured
            if self.disable_reasoning:
                options["reasoning_mode"] = False

            # Wrap with timeout
            import asyncio
            response = await asyncio.wait_for(
                self.client.chat(
                    model=self.model,
                    messages=messages,
                    options=options,
                    stream=False,  # Ensure streaming is disabled
                ),
                timeout=self.timeout,
            )

            execution_time = time.time() - start_time
            message = response.get("message", {})
            content = message.get("content", "")

            logger.info(
                f"Ollama chat completed",
                extra={
                    "model": self.model,
                    "function_name": function_name,
                    "execution_time": execution_time,
                    "execution_time_ms": execution_time * 1000,
                    "request_id": request_id,
                    "response_length": len(content),
                    "disable_reasoning": self.disable_reasoning,
                    "requested_tokens": max_tokens,
                    "returned_tokens": response.get("eval_count", 0),
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

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"Ollama chat timeout after {execution_time:.2f}s",
                extra={
                    "model": self.model,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "timeout": self.timeout,
                },
            )
            raise ExternalServiceException(
                message=f"LLM chat timeout after {self.timeout}s",
                details={"error": "TimeoutError", "timeout": self.timeout},
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
