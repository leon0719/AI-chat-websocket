"""Chat services."""

from datetime import UTC, datetime
from uuid import UUID

from apps.chat.ai.tokenizer import (
    count_messages_tokens,
    get_token_limit,
)
from apps.chat.models import Conversation, Message
from apps.chat.schemas import ConversationCreateSchema, ConversationUpdateSchema
from apps.core.exceptions import NotFoundError


def get_user_conversations(user_id: UUID, include_archived: bool = False):
    """Get all conversations for a user.

    Uses select_related to prevent N+1 queries when accessing user data.
    Ordered by updated_at descending (most recent first).
    """
    qs = Conversation.objects.select_related("user").filter(user_id=user_id)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs.order_by("-updated_at")


def get_conversation(conversation_id: UUID, user_id: UUID) -> Conversation:
    """Get a conversation by ID.

    Uses select_related to prevent N+1 queries when accessing user data.
    """
    try:
        return Conversation.objects.select_related("user").get(id=conversation_id, user_id=user_id)
    except Conversation.DoesNotExist as e:
        raise NotFoundError("Conversation not found") from e


def create_conversation(user_id: UUID, data: ConversationCreateSchema) -> Conversation:
    """Create a new conversation."""
    return Conversation.objects.create(
        user_id=user_id,
        title=data.title,
        model=data.model,
        system_prompt=data.system_prompt,
        temperature=data.temperature,
    )


def update_conversation(
    conversation_id: UUID, user_id: UUID, data: ConversationUpdateSchema
) -> Conversation:
    """Update a conversation."""
    conversation = get_conversation(conversation_id, user_id)

    if data.title is not None:
        conversation.title = data.title
    if data.model is not None:
        conversation.model = data.model
    if data.system_prompt is not None:
        conversation.system_prompt = data.system_prompt
    if data.temperature is not None:
        conversation.temperature = data.temperature
    if data.is_archived is not None:
        conversation.is_archived = data.is_archived

    conversation.save()
    return conversation


def delete_conversation(conversation_id: UUID, user_id: UUID) -> None:
    """Delete a conversation."""
    conversation = get_conversation(conversation_id, user_id)
    conversation.delete()


def get_conversation_messages(
    conversation_id: UUID, user_id: UUID, page: int = 1, page_size: int = 50
):
    """Get messages for a conversation with pagination.

    Validates ownership through conversation join (2 queries total).
    """
    qs = Message.objects.filter(
        conversation_id=conversation_id,
        conversation__user_id=user_id,
    )

    total = qs.count()

    # Distinguish "no messages" from "conversation not found"
    if total == 0:
        if not Conversation.objects.filter(id=conversation_id, user_id=user_id).exists():
            raise NotFoundError("Conversation not found")

    offset = (page - 1) * page_size
    messages = qs[offset : offset + page_size]

    return messages, total


def create_message(
    conversation_id: UUID,
    role: str,
    content: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    model_used: str = "",
) -> Message:
    """Create a new message."""
    return Message.objects.create(
        conversation_id=conversation_id,
        role=role,
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model_used=model_used,
    )


def get_conversation_history_with_token_limit(
    conversation_id: UUID,
    model: str = "gpt-4o",
    max_tokens: int | None = None,
    system_prompt: str = "",
    summary: str = "",
) -> tuple[list[dict], int]:
    """
    獲取對話歷史，根據 token 限制動態調整。

    從最新訊息開始，逐條加入直到達到 token 上限。

    Args:
        conversation_id: 對話 ID
        model: 使用的模型
        max_tokens: 最大 token 數，None 則使用模型預設上限
        system_prompt: 系統提示詞（用於計算保留空間）
        summary: 對話摘要（用於計算保留空間）

    Returns:
        (訊息列表, 總 token 數)
    """
    if max_tokens is None:
        max_tokens = get_token_limit(model)

    reserved_messages = []
    if system_prompt:
        reserved_messages.append({"role": "system", "content": system_prompt})
    if summary:
        reserved_messages.append({"role": "system", "content": f"對話摘要：{summary}"})

    reserved_tokens = count_messages_tokens(reserved_messages, model) if reserved_messages else 0
    available_tokens = max_tokens - reserved_tokens

    # Use .values() to reduce ORM overhead
    messages = (
        Message.objects.filter(conversation_id=conversation_id)
        .order_by("-created_at")
        .values("role", "content")
    )

    selected_messages: list[dict] = []
    current_tokens = 0

    for msg in messages:
        msg_dict = {"role": msg["role"], "content": msg["content"]}
        msg_tokens = count_messages_tokens([msg_dict], model)

        if current_tokens + msg_tokens > available_tokens:
            break

        selected_messages.insert(0, msg_dict)
        current_tokens += msg_tokens

    total_tokens = reserved_tokens + current_tokens
    return selected_messages, total_tokens


def update_conversation_summary(
    conversation: Conversation,
    summary: str,
    token_count: int,
) -> Conversation:
    """更新對話摘要。

    Args:
        conversation: 對話物件（避免額外查詢）
        summary: 摘要內容
        token_count: Token 數量
    """
    conversation.summary = summary
    conversation.summary_token_count = token_count
    conversation.last_summarized_at = datetime.now(UTC)
    conversation.save(update_fields=["summary", "summary_token_count", "last_summarized_at"])
    return conversation


SUMMARY_PROMPT = """請將以下對話歷史摘要成 200 字以內的重點：
- 保留關鍵資訊和用戶偏好
- 保留重要的上下文
- 使用繁體中文

對話歷史：
{conversation_history}

請直接輸出摘要內容，不需要其他說明。"""


def build_summary_messages(messages: list[dict]) -> list[dict]:
    """建構摘要請求的訊息。"""
    history_text = "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)
    return [{"role": "user", "content": SUMMARY_PROMPT.format(conversation_history=history_text)}]
