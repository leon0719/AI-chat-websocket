"""OpenAI client wrapper for streaming chat completions with retry support."""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAIError, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from apps.core.exceptions import AIServiceError
from apps.core.log_config import logger
from config.settings.base import get_settings

_tenacity_logger = logging.getLogger(__name__)  # tenacity requires stdlib Logger

# Thread-safe singleton for OpenAI client
_openai_client: "OpenAIClient | None" = None
_client_lock = threading.Lock()

RETRYABLE_EXCEPTIONS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)


@asynccontextmanager
async def handle_openai_errors():
    """Async context manager for unified OpenAI error handling."""
    try:
        yield
    except RETRYABLE_EXCEPTIONS as e:
        logger.error(f"OpenAI API error after retries: {e}")
        raise AIServiceError(f"OpenAI API temporarily unavailable: {e}") from e
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise AIServiceError(f"OpenAI API error: {e}") from e


class OpenAIClient:
    """Async OpenAI client for streaming chat completions with retry support."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(_tenacity_logger, logging.WARNING),
    )
    async def _call_openai(self, **kwargs):
        """Call OpenAI API with retry support."""
        return await self.client.chat.completions.create(**kwargs)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream chat completion responses with retry support."""
        async with handle_openai_errors():
            stream = await self._call_openai(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield {"type": "content", "content": delta.content}

                if chunk.usage:
                    yield {
                        "type": "usage",
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                    }

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Non-streaming chat completion with retry support."""
        async with handle_openai_errors():
            response = await self._call_openai(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            message = response.choices[0].message if response.choices else None
            return {
                "content": message.content if message else "",
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }


def get_openai_client() -> OpenAIClient:
    """Get thread-safe singleton OpenAI client instance.

    Uses double-checked locking pattern to ensure thread safety
    while minimizing lock contention after initialization.
    """
    global _openai_client
    if _openai_client is None:
        with _client_lock:
            if _openai_client is None:
                _openai_client = OpenAIClient()
    return _openai_client


def reset_openai_client() -> None:
    """Reset singleton client instance. For testing purposes only."""
    global _openai_client
    with _client_lock:
        _openai_client = None
