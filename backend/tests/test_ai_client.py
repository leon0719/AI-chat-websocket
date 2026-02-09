"""Tests for OpenAI client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError, APITimeoutError, OpenAIError, RateLimitError

from apps.chat.ai import client as client_module
from apps.chat.ai.client import (
    OpenAIClient,
    get_openai_client,
    handle_openai_errors,
    reset_openai_client,
)
from apps.core.exceptions import AIServiceError


class TestHandleOpenaiErrors:
    """Test handle_openai_errors context manager."""

    @pytest.mark.asyncio
    async def test_no_error(self):
        async with handle_openai_errors():
            pass

    @pytest.mark.asyncio
    async def test_api_connection_error(self):
        with pytest.raises(AIServiceError, match="temporarily unavailable"):
            async with handle_openai_errors():
                raise APIConnectionError(request=MagicMock())

    @pytest.mark.asyncio
    async def test_api_timeout_error(self):
        with pytest.raises(AIServiceError, match="temporarily unavailable"):
            async with handle_openai_errors():
                raise APITimeoutError(request=MagicMock())

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        with pytest.raises(AIServiceError, match="temporarily unavailable"):
            async with handle_openai_errors():
                response = MagicMock()
                response.status_code = 429
                response.headers = {}
                raise RateLimitError(
                    message="rate limited",
                    response=response,
                    body=None,
                )

    @pytest.mark.asyncio
    async def test_generic_openai_error(self):
        with pytest.raises(AIServiceError, match="OpenAI API error"):
            async with handle_openai_errors():
                raise OpenAIError("something went wrong")

    @pytest.mark.asyncio
    async def test_preserves_exception_chain(self):
        with pytest.raises(AIServiceError) as exc_info:
            async with handle_openai_errors():
                raise OpenAIError("original error")
        assert exc_info.value.__cause__ is not None


class TestOpenAIClientStreamChat:
    """Test OpenAIClient.stream_chat()."""

    @pytest.mark.asyncio
    @patch("apps.chat.ai.client.get_settings")
    async def test_stream_content_chunks(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        client = OpenAIClient()

        content_chunk = MagicMock()
        content_chunk.choices = [MagicMock()]
        content_chunk.choices[0].delta.content = "Hello"
        content_chunk.usage = None

        usage_chunk = MagicMock()
        usage_chunk.choices = []
        usage_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        async def mock_stream():
            yield content_chunk
            yield usage_chunk

        client._call_openai = AsyncMock(return_value=mock_stream())

        results = []
        async for chunk in client.stream_chat(messages=[{"role": "user", "content": "Hi"}]):
            results.append(chunk)

        assert results[0] == {"type": "content", "content": "Hello"}
        assert results[1] == {"type": "usage", "prompt_tokens": 10, "completion_tokens": 5}

    @pytest.mark.asyncio
    @patch("apps.chat.ai.client.get_settings")
    async def test_stream_empty_delta(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        client = OpenAIClient()

        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = None
        chunk.usage = None

        async def mock_stream():
            yield chunk

        client._call_openai = AsyncMock(return_value=mock_stream())

        results = []
        async for item in client.stream_chat(messages=[{"role": "user", "content": "Hi"}]):
            results.append(item)

        assert results == []


class TestOpenAIClientChat:
    """Test OpenAIClient.chat()."""

    @pytest.mark.asyncio
    @patch("apps.chat.ai.client.get_settings")
    async def test_chat_response(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        client = OpenAIClient()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello there!"
        mock_response.usage = MagicMock(prompt_tokens=5, completion_tokens=3)

        client._call_openai = AsyncMock(return_value=mock_response)

        result = await client.chat(messages=[{"role": "user", "content": "Hi"}])
        assert result["content"] == "Hello there!"
        assert result["prompt_tokens"] == 5
        assert result["completion_tokens"] == 3

    @pytest.mark.asyncio
    @patch("apps.chat.ai.client.get_settings")
    async def test_chat_empty_choices(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        client = OpenAIClient()

        mock_response = MagicMock()
        mock_response.choices = []
        mock_response.usage = None

        client._call_openai = AsyncMock(return_value=mock_response)

        result = await client.chat(messages=[{"role": "user", "content": "Hi"}])
        assert result["content"] == ""
        assert result["prompt_tokens"] == 0
        assert result["completion_tokens"] == 0


class TestSingletonClient:
    """Test get_openai_client / reset_openai_client singleton behavior."""

    @patch("apps.chat.ai.client.get_settings")
    def test_singleton_returns_same_instance(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        reset_openai_client()

        client1 = get_openai_client()
        client2 = get_openai_client()
        assert client1 is client2

        reset_openai_client()

    @patch("apps.chat.ai.client.get_settings")
    def test_reset_clears_instance(self, mock_settings):
        mock_settings.return_value = MagicMock(OPENAI_API_KEY="test-key")
        reset_openai_client()

        client1 = get_openai_client()
        reset_openai_client()
        client2 = get_openai_client()
        assert client1 is not client2

        reset_openai_client()

    def test_reset_when_none(self):
        # Ensure module-level _openai_client is None
        client_module._openai_client = None
        reset_openai_client()
        assert client_module._openai_client is None
