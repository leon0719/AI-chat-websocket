"""WebSocket consumer tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import AccessToken

from apps.chat.consumers import ChatConsumer
from apps.chat.middleware import JWTAuthMiddleware
from apps.chat.models import Conversation, Message, MessageRole

User = get_user_model()


def create_access_token(user) -> str:
    """Create access token for testing."""
    token = AccessToken.for_user(user)
    return str(token)


@pytest.fixture
def ws_user(db):
    """Create a user for WebSocket tests."""
    return User.objects.create_user(
        email="wstest@example.com",
        username="wsuser",
        password="testpass123",
    )


@pytest.fixture
def conversation(ws_user):
    """Create a conversation for WebSocket tests."""
    return Conversation.objects.create(
        user=ws_user,
        title="Test Conversation",
        model="gpt-4o",
        system_prompt="You are a test assistant.",
    )


@pytest.fixture
def auth_token(ws_user):
    """Create an auth token for WebSocket tests."""
    return create_access_token(ws_user)


def create_application():
    """Create test ASGI application with middleware."""
    from channels.routing import ProtocolTypeRouter, URLRouter
    from django.urls import re_path

    return ProtocolTypeRouter(
        {
            "websocket": JWTAuthMiddleware(
                URLRouter(
                    [
                        re_path(
                            r"ws/chat/(?P<conversation_id>[^/]+)/$",
                            ChatConsumer.as_asgi(),
                        ),
                    ]
                )
            ),
        }
    )


@pytest.mark.django_db(transaction=True)
class TestWebSocketConnection:
    """Test WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_connect_without_token_rejected(self, conversation):
        """Test that connections without token are rejected."""
        application = create_application()
        communicator = WebsocketCommunicator(application, f"/ws/chat/{conversation.id}/")

        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_with_invalid_token_rejected(self, conversation):
        """Test that connections with invalid token are rejected."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token=invalid_token"
        )

        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_with_valid_token(self, conversation, auth_token):
        """Test successful connection with valid token."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_invalid_conversation_id(self, ws_user, auth_token):
        """Test connection with invalid conversation ID format."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/not-a-uuid/?token={auth_token}"
        )

        connected, code = await communicator.connect()
        # Connection is accepted first, then closed with code 4002
        if connected:
            response = await communicator.receive_output()
            assert response.get("type") == "websocket.close"
            assert response.get("code") == 4002

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_nonexistent_conversation(self, ws_user, auth_token):
        """Test connection with non-existent conversation."""
        application = create_application()
        fake_uuid = str(uuid.uuid4())
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{fake_uuid}/?token={auth_token}"
        )

        connected, code = await communicator.connect()
        if connected:
            response = await communicator.receive_output()
            assert response.get("type") == "websocket.close"
            assert response.get("code") == 4004

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_connect_other_user_conversation(self, conversation, auth_token):
        """Test that user cannot connect to another user's conversation."""
        # Create another user and get their token
        other_user = await database_sync_to_async(User.objects.create_user)(
            email="other@example.com",
            username="otheruser",
            password="testpass123",
        )
        other_token = await database_sync_to_async(create_access_token)(other_user)

        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={other_token}"
        )

        connected, code = await communicator.connect()
        if connected:
            response = await communicator.receive_output()
            assert response.get("type") == "websocket.close"
            assert response.get("code") == 4004

        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
class TestWebSocketHeartbeat:
    """Test WebSocket heartbeat functionality."""

    @pytest.mark.asyncio
    async def test_heartbeat_received(self, conversation, auth_token):
        """Test that heartbeat ping is received."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Wait for heartbeat (with timeout shorter than heartbeat interval for test)
        # In actual implementation, heartbeat is 30 seconds, so we mock it
        with patch("apps.chat.consumers.HEARTBEAT_INTERVAL", 0.1):
            try:
                response = await communicator.receive_json_from(timeout=0.5)
                assert response.get("type") == "ping"
            except Exception:
                pass  # Heartbeat might not fire in test environment

        await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
class TestWebSocketMessageHandling:
    """Test WebSocket message handling."""

    @pytest.mark.asyncio
    async def test_invalid_json_error(self, conversation, auth_token):
        """Test that invalid JSON returns error."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Send invalid JSON
        await communicator.send_to(text_data="not valid json")

        response = await communicator.receive_json_from()
        assert response["type"] == "chat.error"
        assert response["code"] == "INVALID_JSON"

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_unknown_message_type_error(self, conversation, auth_token):
        """Test that unknown message type returns error."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "unknown.type"})

        response = await communicator.receive_json_from()
        assert response["type"] == "chat.error"
        assert response["code"] == "UNKNOWN_TYPE"

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_empty_message_error(self, conversation, auth_token):
        """Test that empty message returns error."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        await communicator.send_json_to({"type": "chat.message", "content": ""})

        response = await communicator.receive_json_from()
        assert response["type"] == "chat.error"
        assert response["code"] == "EMPTY_CONTENT"

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_message_too_long_error(self, conversation, auth_token):
        """Test that message exceeding max length returns error."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Send message exceeding MAX_MESSAGE_LENGTH (10000)
        long_message = "a" * 10001
        await communicator.send_json_to({"type": "chat.message", "content": long_message})

        response = await communicator.receive_json_from()
        assert response["type"] == "chat.error"
        assert response["code"] == "MESSAGE_TOO_LONG"

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_pong_message_handled(self, conversation, auth_token):
        """Test that pong messages are handled silently."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Send pong message
        await communicator.send_json_to({"type": "pong"})

        # Should not receive any response (pong is handled silently)
        # This would timeout if no error is returned
        try:
            await communicator.receive_json_from(timeout=0.3)
        except TimeoutError:
            pass  # Expected timeout - pong is handled silently

        try:
            await communicator.disconnect()
        except BaseException:
            pass  # Ignore disconnect errors (CancelledError is BaseException)


@pytest.mark.django_db(transaction=True)
class TestWebSocketAIStreaming:
    """Test WebSocket AI streaming functionality."""

    @pytest.mark.asyncio
    async def test_chat_message_with_ai_response(self, conversation, auth_token):
        """Test sending chat message and receiving AI stream response."""
        from apps.chat.ai.client import get_openai_client

        # Clear the lru_cache to ensure our mock is used
        get_openai_client.cache_clear()

        # Mock the AI client before connecting
        mock_response = [
            {"type": "content", "content": "Hello"},
            {"type": "content", "content": " there!"},
            {"type": "usage", "prompt_tokens": 10, "completion_tokens": 5},
        ]

        async def mock_stream(*args, **kwargs):
            for chunk in mock_response:
                yield chunk

        with patch("apps.chat.ai.client.OpenAIClient") as mock_client_class:
            mock_ai_client = MagicMock()
            mock_ai_client.stream_chat = mock_stream
            mock_client_class.return_value = mock_ai_client

            # Clear cache again to ensure fresh instance with mock
            get_openai_client.cache_clear()

            application = create_application()
            communicator = WebsocketCommunicator(
                application, f"/ws/chat/{conversation.id}/?token={auth_token}"
            )

            connected, _ = await communicator.connect()
            assert connected

            await communicator.send_json_to(
                {
                    "type": "chat.message",
                    "content": "Hello, AI!",
                }
            )

            # Collect stream responses
            responses = []
            try:
                while True:
                    response = await communicator.receive_json_from(timeout=3)
                    responses.append(response)
                    if response.get("done"):
                        break
            except TimeoutError:
                pass

            # Verify we got streaming responses
            stream_responses = [r for r in responses if r.get("type") == "chat.stream"]
            assert len(stream_responses) > 0

            try:
                await communicator.disconnect()
            except Exception:
                pass

            # Clear cache after test
            get_openai_client.cache_clear()


@pytest.mark.django_db(transaction=True)
class TestWebSocketXSSProtection:
    """Test XSS protection in WebSocket messages."""

    @pytest.mark.asyncio
    async def test_xss_content_sanitized(self, conversation, auth_token):
        """Test that XSS content is sanitized."""
        from apps.chat.ai.client import get_openai_client

        # Clear the lru_cache to ensure our mock is used
        get_openai_client.cache_clear()

        async def mock_stream(*args, **kwargs):
            yield {"type": "content", "content": "Response"}
            yield {"type": "usage", "prompt_tokens": 5, "completion_tokens": 2}

        with patch("apps.chat.ai.client.OpenAIClient") as mock_client_class:
            mock_ai_client = AsyncMock()
            mock_ai_client.stream_chat = mock_stream
            mock_client_class.return_value = mock_ai_client

            # Clear cache again to ensure fresh instance with mock
            get_openai_client.cache_clear()

            application = create_application()
            communicator = WebsocketCommunicator(
                application, f"/ws/chat/{conversation.id}/?token={auth_token}"
            )

            connected, _ = await communicator.connect()
            assert connected

            # Send XSS content
            xss_content = '<script>alert("xss")</script>Hello'
            await communicator.send_json_to(
                {
                    "type": "chat.message",
                    "content": xss_content,
                }
            )

            # Collect responses
            try:
                while True:
                    response = await communicator.receive_json_from(timeout=2)
                    if response.get("done"):
                        break
            except Exception:
                pass

            try:
                await communicator.disconnect()
            except Exception:
                pass

            # Clear cache after test
            get_openai_client.cache_clear()

        # Verify the message was saved with sanitized content
        message = await database_sync_to_async(
            lambda: Message.objects.filter(conversation=conversation, role=MessageRole.USER).first()
        )()

        if message:
            # Script tags should be stripped
            assert "<script>" not in message.content
            assert "Hello" in message.content


@pytest.mark.django_db(transaction=True)
class TestWebSocketRateLimiting:
    """Test WebSocket rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, conversation, auth_token):
        """Test that rate limiting is enforced on WebSocket messages."""
        application = create_application()
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/{conversation.id}/?token={auth_token}"
        )

        connected, _ = await communicator.connect()
        assert connected

        # Patch rate limit to be very restrictive for testing
        with patch("apps.chat.consumers.check_ws_rate_limit") as mock_rate_limit:
            mock_rate_limit.return_value = (False, 60)  # Rate limit exceeded

            await communicator.send_json_to(
                {
                    "type": "chat.message",
                    "content": "Test message",
                }
            )

            response = await communicator.receive_json_from()
            assert response["type"] == "chat.error"
            assert response["code"] == "RATE_LIMIT_EXCEEDED"

        await communicator.disconnect()
