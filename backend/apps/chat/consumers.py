"""WebSocket consumers for chat."""

import asyncio
from uuid import UUID

import bleach
import orjson
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.chat.ai.client import get_openai_client
from apps.chat.ai.tokenizer import should_summarize
from apps.chat.models import Conversation, Message, MessageRole
from apps.chat.services import (
    build_summary_messages,
    create_message,
    get_conversation,
    get_conversation_history_with_token_limit,
    update_conversation_summary,
)
from apps.core.exceptions import AIServiceError, NotFoundError
from apps.core.log_config import logger
from apps.core.ratelimit import check_ws_rate_limit

MAX_MESSAGE_LENGTH = 10000
AI_STREAM_TIMEOUT = 120  # seconds
HEARTBEAT_INTERVAL = 30  # seconds
TASK_CANCEL_TIMEOUT = 5  # seconds
WS_MESSAGE_RATE_LIMIT = 20  # messages per minute
WS_RATE_LIMIT_WINDOW = 60  # seconds


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for chat functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_id: UUID | None = None
        self.conversation: Conversation | None = None
        self.ai_client = get_openai_client()
        self._heartbeat_task: asyncio.Task | None = None
        self._processing_lock = asyncio.Lock()
        self._summary_task: asyncio.Task | None = None

    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope.get("user")

        if not user:
            await self.close(code=4001)
            return

        conversation_id_str = self.scope["url_route"]["kwargs"]["conversation_id"]

        try:
            self.conversation_id = UUID(conversation_id_str)
        except ValueError:
            await self.close(code=4002)
            return

        try:
            self.conversation = await self._get_conversation(self.conversation_id, user.id)
        except NotFoundError:
            await self.close(code=4004)
            return

        await self.accept()
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        logger.info(f"WebSocket connected: conversation={self.conversation_id}, user={user.id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # 取消心跳任務（帶超時保護）
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                async with asyncio.timeout(TASK_CANCEL_TIMEOUT):
                    await self._heartbeat_task
            except (asyncio.CancelledError, TimeoutError):
                pass

        # 取消摘要任務（帶超時保護）
        if self._summary_task and not self._summary_task.done():
            self._summary_task.cancel()
            try:
                async with asyncio.timeout(TASK_CANCEL_TIMEOUT):
                    await self._summary_task
            except (asyncio.CancelledError, TimeoutError):
                pass

        logger.info(
            f"WebSocket disconnected: conversation={self.conversation_id}, code={close_code}"
        )

    async def _heartbeat(self):
        """Send periodic heartbeat to detect dead connections."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.send(text_data=orjson.dumps({"type": "ping"}).decode())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Heartbeat error for conversation={self.conversation_id}: {e}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = orjson.loads(text_data)
        except (ValueError, TypeError, orjson.JSONDecodeError):
            await self._send_error("Invalid JSON", "INVALID_JSON")
            return

        msg_type = data.get("type")

        if msg_type == "chat.message":
            await self._handle_chat_message(data)
        elif msg_type == "pong":
            pass  # Client heartbeat response, no action needed
        else:
            await self._send_error(f"Unknown message type: {msg_type}", "UNKNOWN_TYPE")

    async def _handle_chat_message(self, data: dict):
        """Handle incoming chat message and stream AI response."""
        if self.conversation is None or self.conversation_id is None:
            await self._send_error("No active conversation", "NO_CONVERSATION")
            return

        # Check rate limit
        user = self.scope.get("user")
        if user:
            is_allowed, retry_after = check_ws_rate_limit(
                identifier=str(user.id),
                action="message",
                max_requests=WS_MESSAGE_RATE_LIMIT,
                window_seconds=WS_RATE_LIMIT_WINDOW,
            )
            if not is_allowed:
                await self._send_error(
                    f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "RATE_LIMIT_EXCEEDED",
                )
                return

        # Check if already processing - in asyncio single-threaded context,
        # the check and acquire are atomic as long as there's no await between them
        if self._processing_lock.locked():
            await self._send_error("Already processing a message", "ALREADY_PROCESSING")
            return

        async with self._processing_lock:
            await self._process_chat_message(data)

    async def _process_chat_message(self, data: dict):
        """Process the chat message within the lock context.

        Called only from _handle_chat_message which validates conversation existence.
        """
        # Defensive check - should never happen as _handle_chat_message validates these
        if self.conversation is None or self.conversation_id is None:
            logger.error("_process_chat_message called without valid conversation state")
            await self._send_error("Invalid conversation state", "INTERNAL_ERROR")
            return

        try:
            raw_content = data.get("content", "").strip()

            if not raw_content:
                await self._send_error("Message content is required", "EMPTY_CONTENT")
                return

            if len(raw_content) > MAX_MESSAGE_LENGTH:
                await self._send_error(
                    f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH}", "MESSAGE_TOO_LONG"
                )
                return

            # 清理輸入內容，移除潛在的 XSS 攻擊向量
            content = bleach.clean(raw_content, tags=[], strip=True)

            if len(content) > MAX_MESSAGE_LENGTH:
                await self._send_error(
                    f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH}", "MESSAGE_TOO_LONG"
                )
                return

            await self._save_message(
                conversation_id=self.conversation_id,
                role=MessageRole.USER,
                content=content,
            )

            # 獲取歷史記錄（含 token 計數）
            history, total_tokens = await self._get_history_with_token_limit(
                self.conversation_id,
                self.conversation.model,
                self.conversation.system_prompt,
                self.conversation.summary,
            )

            # 組裝訊息
            messages = [{"role": "system", "content": self.conversation.system_prompt}]

            # 如果有摘要，加入 system message
            if self.conversation.summary:
                messages.append(
                    {
                        "role": "system",
                        "content": f"對話摘要：{self.conversation.summary}",
                    }
                )

            messages.extend(history)

            full_response = ""
            prompt_tokens = 0
            completion_tokens = 0

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
                        prompt_tokens = chunk.get("prompt_tokens", 0)
                        completion_tokens = chunk.get("completion_tokens", 0)

            assistant_message = await self._save_message(
                conversation_id=self.conversation_id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_used=self.conversation.model,
            )

            await self._send_stream("", done=True, message_id=str(assistant_message.id))

            # 使用 API 返回的 completion_tokens 計算更新後的總 token 數
            # 避免重複呼叫 count_messages_tokens
            updated_total_tokens = total_tokens + completion_tokens

            # 檢查是否需要生成摘要（token > 70%）- 背景執行不阻塞回應
            if should_summarize(updated_total_tokens, self.conversation.model):
                # 包含最新的 AI 回應在摘要中
                history_with_response = [
                    *history,
                    {"role": "assistant", "content": full_response},
                ]
                self._summary_task = asyncio.create_task(
                    self._generate_summary(history_with_response, updated_total_tokens)
                )

        except TimeoutError:
            logger.error(f"AI stream timeout after {AI_STREAM_TIMEOUT}s")
            await self._send_error("AI response timed out", "AI_TIMEOUT")
        except AIServiceError as e:
            logger.error(f"AI service error: {e}")
            await self._send_error(str(e), "AI_ERROR")
        except Exception as e:
            logger.exception(f"Unexpected error during chat: {e}")
            await self._send_error("An unexpected error occurred", "INTERNAL_ERROR")

    async def _send_stream(self, content: str, done: bool, message_id: str | None = None):
        """Send streaming response chunk."""
        payload = {
            "type": "chat.stream",
            "content": content,
            "done": done,
        }
        if message_id:
            payload["message_id"] = message_id

        await self.send(text_data=orjson.dumps(payload).decode())

    async def _send_error(self, error: str, code: str):
        """Send error message."""
        await self.send(
            text_data=orjson.dumps(
                {
                    "type": "chat.error",
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
    def _get_history_with_token_limit(
        self,
        conversation_id: UUID,
        model: str,
        system_prompt: str,
        summary: str,
    ) -> tuple[list[dict], int]:
        """Get conversation history with token limit."""
        return get_conversation_history_with_token_limit(
            conversation_id=conversation_id,
            model=model,
            system_prompt=system_prompt,
            summary=summary,
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
                # 更新本地實例的摘要
                self.conversation.summary = summary
                self.conversation.summary_token_count = token_count
                logger.info(
                    f"Generated summary for conversation {self.conversation_id}, "
                    f"token_count={token_count}"
                )
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
