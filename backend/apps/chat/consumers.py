"""WebSocket consumers for chat."""

import asyncio
from enum import StrEnum
from uuid import UUID

import nh3
import orjson
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import DatabaseError, OperationalError

from apps.chat.ai.client import get_openai_client
from apps.chat.ai.tokenizer import should_summarize
from apps.chat.config import (
    AI_STREAM_TIMEOUT,
    AUTH_TIMEOUT,
    HEARTBEAT_INTERVAL,
    TASK_CANCEL_TIMEOUT,
    WS_MESSAGE_RATE_LIMIT,
    WS_RATE_LIMIT_WINDOW,
)
from apps.chat.models import MAX_USER_MESSAGE_LENGTH, Conversation, Message, MessageRole
from apps.chat.services import (
    build_summary_messages,
    create_message,
    get_conversation,
    get_conversation_history_with_token_limit,
    update_conversation_summary,
)
from apps.core.exceptions import AIServiceError, InvalidStateError, NotFoundError
from apps.core.log_config import logger
from apps.core.ratelimit import check_ws_rate_limit


class WSMessageType(StrEnum):
    """WebSocket message types."""

    AUTH = "auth"
    AUTH_SUCCESS = "auth.success"
    CHAT_MESSAGE = "chat.message"
    CHAT_STREAM = "chat.stream"
    CHAT_ERROR = "chat.error"
    PING = "ping"
    PONG = "pong"


class WSErrorCode(StrEnum):
    """WebSocket error codes."""

    INVALID_JSON = "INVALID_JSON"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_FAILED = "AUTH_FAILED"
    AUTH_TIMEOUT = "AUTH_TIMEOUT"
    NO_CONVERSATION = "NO_CONVERSATION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    ALREADY_PROCESSING = "ALREADY_PROCESSING"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    EMPTY_CONTENT = "EMPTY_CONTENT"
    MESSAGE_TOO_LONG = "MESSAGE_TOO_LONG"
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_ERROR = "AI_ERROR"


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for chat functionality with in-band JWT authentication.

    Authentication flow:
    1. Client connects to WebSocket (no token in URL)
    2. Server accepts connection and starts auth timeout
    3. Client sends: {"type": "auth", "token": "<jwt>"}
    4. Server validates token and loads conversation
    5. Server sends: {"type": "auth.success", "conversation_id": "..."}
    6. Client can now send chat messages

    This is more secure than query param auth as tokens won't appear in logs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_id: UUID | None = None
        self.conversation: Conversation | None = None
        self.user = None
        self.is_authenticated = False
        self.ai_client = get_openai_client()
        self._heartbeat_task: asyncio.Task | None = None
        self._auth_timeout_task: asyncio.Task | None = None
        self._processing_lock = asyncio.Lock()
        self._summary_task: asyncio.Task | None = None

    async def connect(self):
        """Handle WebSocket connection - accept and wait for in-band auth."""
        conversation_id_str = self.scope["url_route"]["kwargs"]["conversation_id"]

        try:
            self.conversation_id = UUID(conversation_id_str)
        except ValueError:
            await self.close(code=4002)
            return

        await self.accept()
        self._auth_timeout_task = asyncio.create_task(self._auth_timeout())
        logger.debug(f"WebSocket accepted, waiting for auth: conversation={self.conversation_id}")

    async def _auth_timeout(self):
        """Close connection if not authenticated within timeout."""
        try:
            await asyncio.sleep(AUTH_TIMEOUT)
            if not self.is_authenticated:
                logger.warning(f"WebSocket auth timeout: conversation={self.conversation_id}")
                await self._send_error("Authentication timeout", WSErrorCode.AUTH_TIMEOUT)
                await self.close(code=4001)
        except asyncio.CancelledError:
            pass

    async def _handle_auth(self, data: dict) -> None:
        """Handle in-band authentication message."""
        if self.is_authenticated:
            return

        token = data.get("token", "")
        if not token:
            await self._send_error("Token is required", WSErrorCode.AUTH_FAILED)
            await self.close(code=4001)
            return

        auth_helper = self.scope.get("auth_helper")
        if not auth_helper:
            logger.error("auth_helper not found in scope")
            await self._send_error("Internal error", WSErrorCode.INTERNAL_ERROR)
            await self.close(code=4001)
            return

        user = await auth_helper(token)
        if user is None:
            logger.warning("WebSocket auth failed: invalid token")
            await self._send_error("Invalid or expired token", WSErrorCode.AUTH_FAILED)
            await self.close(code=4001)
            return

        try:
            self.conversation = await self._get_conversation(self.conversation_id, user.id)
        except NotFoundError:
            await self._send_error("Conversation not found", WSErrorCode.NO_CONVERSATION)
            await self.close(code=4004)
            return

        self.user = user
        self.is_authenticated = True
        self.scope["user"] = user

        await self._cancel_task(self._auth_timeout_task)
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

        await self.send(
            text_data=orjson.dumps(
                {
                    "type": WSMessageType.AUTH_SUCCESS,
                    "conversation_id": str(self.conversation_id),
                }
            ).decode()
        )
        logger.info(f"WebSocket authenticated: conversation={self.conversation_id}, user={user.id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self._cancel_task(self._auth_timeout_task)
        await self._cancel_task(self._heartbeat_task)
        await self._cancel_task(self._summary_task)
        logger.info(
            f"WebSocket disconnected: conversation={self.conversation_id}, code={close_code}"
        )

    async def _cancel_task(self, task: asyncio.Task | None) -> None:
        """Cancel and cleanup an async task."""
        if not task or task.done():
            return
        task.cancel()
        try:
            async with asyncio.timeout(TASK_CANCEL_TIMEOUT):
                await task
        except (asyncio.CancelledError, TimeoutError):
            pass

    async def _heartbeat(self):
        """Send periodic heartbeat to detect dead connections."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.send(text_data=orjson.dumps({"type": WSMessageType.PING}).decode())
        except asyncio.CancelledError:
            pass
        except (ConnectionError, OSError) as e:
            logger.warning(
                f"Heartbeat connection error for conversation={self.conversation_id}: {e}"
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = orjson.loads(text_data)
        except (ValueError, TypeError, orjson.JSONDecodeError):
            await self._send_error("Invalid JSON", WSErrorCode.INVALID_JSON)
            return

        msg_type = data.get("type")

        if msg_type == WSMessageType.AUTH:
            await self._handle_auth(data)
        elif msg_type == WSMessageType.PONG:
            pass
        elif not self.is_authenticated:
            await self._send_error("Authentication required", WSErrorCode.AUTH_REQUIRED)
        elif msg_type == WSMessageType.CHAT_MESSAGE:
            await self._handle_chat_message(data)
        else:
            await self._send_error("Unknown message type", WSErrorCode.UNKNOWN_TYPE)

    async def _handle_chat_message(self, data: dict):
        """Handle incoming chat message and stream AI response."""
        if self.conversation is None or self.conversation_id is None or self.user is None:
            await self._send_error("No active conversation", WSErrorCode.NO_CONVERSATION)
            return

        is_allowed, retry_after = check_ws_rate_limit(
            identifier=str(self.user.id),
            action="message",
            max_requests=WS_MESSAGE_RATE_LIMIT,
            window_seconds=WS_RATE_LIMIT_WINDOW,
        )
        if not is_allowed:
            await self._send_error(
                f"Rate limit exceeded. Try again in {retry_after} seconds.",
                WSErrorCode.RATE_LIMIT_EXCEEDED,
            )
            return

        if self._processing_lock.locked():
            await self._send_error("Already processing a message", WSErrorCode.ALREADY_PROCESSING)
            return

        async with self._processing_lock:
            await self._process_chat_message(data)

    async def _process_chat_message(self, data: dict):
        """Process the chat message within the lock context."""
        if self.conversation is None or self.conversation_id is None:
            logger.error("_process_chat_message called without valid conversation state")
            await self._send_error("Invalid conversation state", WSErrorCode.INTERNAL_ERROR)
            return

        try:
            content = await self._validate_message_content(data)
            if content is None:
                return

            await self._save_message(
                conversation_id=self.conversation_id,
                role=MessageRole.USER,
                content=content,
            )

            history, total_tokens = await self._get_history_with_token_limit()

            messages = self._build_chat_messages(history)
            full_response, usage = await self._stream_ai_response(messages)

            await self._save_and_finalize_response(full_response, usage, history, total_tokens)

        except TimeoutError:
            logger.error(f"AI stream timeout after {AI_STREAM_TIMEOUT}s")
            await self._send_error("AI response timed out", WSErrorCode.AI_TIMEOUT)
        except AIServiceError as e:
            logger.error(f"AI service error: {e}")
            await self._send_error(str(e), WSErrorCode.AI_ERROR)
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Database error during chat: {e}")
            await self._send_error("Database error occurred", WSErrorCode.INTERNAL_ERROR)
        except (ConnectionError, OSError) as e:
            logger.error(f"Connection error during chat: {e}")
            await self._send_error("Connection error occurred", WSErrorCode.INTERNAL_ERROR)
        except InvalidStateError as e:
            logger.error(f"Invalid state during chat: {e}")
            await self._send_error("Invalid conversation state", WSErrorCode.INTERNAL_ERROR)

    async def _validate_message_content(self, data: dict) -> str | None:
        """Validate and sanitize message content. Returns None if invalid."""
        raw_content = data.get("content", "").strip()

        if not raw_content:
            await self._send_error("Message content is required", WSErrorCode.EMPTY_CONTENT)
            return None

        content = nh3.clean(raw_content, tags=set())

        if len(content) > MAX_USER_MESSAGE_LENGTH:
            await self._send_error(
                f"Message exceeds maximum length of {MAX_USER_MESSAGE_LENGTH}",
                WSErrorCode.MESSAGE_TOO_LONG,
            )
            return None

        return content

    def _build_chat_messages(self, history: list[dict]) -> list[dict]:
        """Build the message list for AI API call."""
        if self.conversation is None:
            raise InvalidStateError("Conversation required for building messages")
        messages = [{"role": "system", "content": self.conversation.system_prompt}]

        if self.conversation.summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"對話摘要：{self.conversation.summary}",
                }
            )

        messages.extend(history)
        return messages

    async def _stream_ai_response(self, messages: list[dict]) -> tuple[str, dict]:
        """Stream AI response and return full response with usage stats."""
        if self.conversation is None:
            raise InvalidStateError("Conversation required for streaming AI response")
        full_response = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0}

        async with asyncio.timeout(AI_STREAM_TIMEOUT):
            async for chunk in self.ai_client.stream_chat(
                messages=messages,
                model=self.conversation.model,
                temperature=self.conversation.temperature,
            ):
                if chunk.get("type") == "content":
                    content_delta = chunk.get("content", "")
                    full_response += content_delta
                    await self._send_stream(content_delta, done=False)
                elif chunk.get("type") == "usage":
                    usage["prompt_tokens"] = chunk.get("prompt_tokens", 0)
                    usage["completion_tokens"] = chunk.get("completion_tokens", 0)

        return full_response, usage

    async def _save_and_finalize_response(
        self,
        full_response: str,
        usage: dict,
        history: list[dict],
        total_tokens: int,
    ) -> None:
        """Save assistant message and trigger summary if needed."""
        if self.conversation is None or self.conversation_id is None:
            raise InvalidStateError("Conversation required for saving response")
        assistant_message = await self._save_message(
            conversation_id=self.conversation_id,
            role=MessageRole.ASSISTANT,
            content=full_response,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            model_used=self.conversation.model,
        )

        await self._send_stream("", done=True, message_id=str(assistant_message.id))

        updated_total_tokens = total_tokens + usage["completion_tokens"]

        if should_summarize(updated_total_tokens, self.conversation.model):
            history_with_response = [
                *history,
                {"role": "assistant", "content": full_response},
            ]
            self._summary_task = asyncio.create_task(
                self._generate_summary(history_with_response, updated_total_tokens)
            )

    async def _send_stream(self, content: str, done: bool, message_id: str | None = None):
        """Send streaming response chunk."""
        payload: dict = {
            "type": WSMessageType.CHAT_STREAM,
            "content": content,
            "done": done,
        }
        if message_id:
            payload["message_id"] = message_id

        await self.send(text_data=orjson.dumps(payload).decode())

    async def _send_error(self, error: str, code: WSErrorCode):
        """Send error message."""
        await self.send(
            text_data=orjson.dumps(
                {
                    "type": WSMessageType.CHAT_ERROR,
                    "error": error,
                    "code": code,
                }
            ).decode()
        )

    @database_sync_to_async
    def _get_conversation(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        """Get conversation from database."""
        return get_conversation(conversation_id, user_id)

    @database_sync_to_async
    def _save_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        model_used: str = "",
    ) -> Message:
        """Save message to database."""
        return create_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model_used=model_used,
        )

    @database_sync_to_async
    def _get_history_with_token_limit(self) -> tuple[list[dict], int]:
        """Get conversation history with token limit."""
        if self.conversation_id is None or self.conversation is None:
            raise InvalidStateError("Conversation required for getting history")
        return get_conversation_history_with_token_limit(
            conversation_id=self.conversation_id,
            model=self.conversation.model,
            system_prompt=self.conversation.system_prompt,
            summary=self.conversation.summary,
        )

    @database_sync_to_async
    def _update_summary(
        self,
        conversation: Conversation,
        summary: str,
        token_count: int,
    ) -> None:
        """Update conversation summary."""
        update_conversation_summary(conversation, summary, token_count)

    async def _generate_summary(self, messages: list[dict], token_count: int) -> None:
        """Generate and save conversation summary."""
        if self.conversation is None or self.conversation_id is None:
            return

        try:
            summary_messages = build_summary_messages(messages)
            response = await self.ai_client.chat(
                messages=summary_messages,
                model=self.conversation.model,
                temperature=0.3,
                max_tokens=500,
            )

            summary = response.get("content", "")
            if summary:
                await self._update_summary(self.conversation, summary, token_count)
                self.conversation.summary = summary
                self.conversation.summary_token_count = token_count
                logger.info(
                    f"Generated summary for conversation {self.conversation_id}, "
                    f"token_count={token_count}"
                )
        except AIServiceError as e:
            logger.error(f"AI service error during summary generation: {e}")
