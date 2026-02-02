"""Chat services."""

from datetime import UTC, datetime
from uuid import UUID

from apps.chat.ai.tokenizer import (
    count_messages_tokens,
    get_token_limit,
)
from apps.chat.models import Conversation, Message
from apps.core.exceptions import NotFoundError


def get_user_conversations(
    user_id: UUID,
    include_archived: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Conversation], int, bool]:
    """Get conversations for a user with pagination.

    Uses optimized single-query approach: fetches page_size + 1 items to detect
    if there are more pages, avoiding expensive COUNT queries on large datasets.

    Returns:
        tuple: (conversations, total, has_more)
        - total is exact count only for first page with fewer items than page_size
        - total is -1 when exact count is unknown (use has_more for pagination)
    """
    qs = Conversation.objects.select_related("user").filter(user_id=user_id)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    qs = qs.order_by("-updated_at")

    offset = (page - 1) * page_size
    conversations = list(qs[offset : offset + page_size + 1])

    has_more = len(conversations) > page_size
    conversations = conversations[:page_size]

    if page == 1 and not has_more:
        total = len(conversations)
    else:
        total = -1

    return conversations, total, has_more


def get_conversation(conversation_id: UUID, user_id: UUID) -> Conversation:
    """Get a conversation by ID."""
    try:
        return Conversation.objects.get(id=conversation_id, user_id=user_id)
    except Conversation.DoesNotExist as e:
        raise NotFoundError("Conversation not found") from e


def create_conversation(
    user_id: UUID,
    title: str,
    model: str,
    system_prompt: str,
    temperature: float,
) -> Conversation:
    """Create a new conversation."""
    return Conversation.objects.create(
        user_id=user_id,
        title=title,
        model=model,
        system_prompt=system_prompt,
        temperature=temperature,
    )


def update_conversation(
    conversation_id: UUID,
    user_id: UUID,
    title: str | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float | None = None,
    is_archived: bool | None = None,
) -> Conversation:
    """Update a conversation."""
    conversation = get_conversation(conversation_id, user_id)

    update_fields = []
    if title is not None:
        conversation.title = title
        update_fields.append("title")
    if model is not None:
        conversation.model = model
        update_fields.append("model")
    if system_prompt is not None:
        conversation.system_prompt = system_prompt
        update_fields.append("system_prompt")
    if temperature is not None:
        conversation.temperature = temperature
        update_fields.append("temperature")
    if is_archived is not None:
        conversation.is_archived = is_archived
        update_fields.append("is_archived")

    if update_fields:
        conversation.save(update_fields=update_fields)
    return conversation


def delete_conversation(conversation_id: UUID, user_id: UUID) -> None:
    """Delete a conversation."""
    conversation = get_conversation(conversation_id, user_id)
    conversation.delete()


def get_conversation_messages(
    conversation_id: UUID, user_id: UUID, page: int = 1, page_size: int = 50
) -> tuple[list[Message], int, bool]:
    """Get messages for a conversation with pagination.

    Validates ownership via join. Uses optimized single-query approach,
    avoiding expensive COUNT queries on large datasets.

    Returns:
        tuple: (messages, total, has_more)
        - total is exact count only for first page with fewer items than page_size
        - total is -1 when exact count is unknown (use has_more for pagination)
    """
    if not Conversation.objects.filter(id=conversation_id, user_id=user_id).exists():
        raise NotFoundError("Conversation not found")

    qs = Message.objects.filter(conversation_id=conversation_id).order_by("created_at")

    offset = (page - 1) * page_size
    messages = list(qs[offset : offset + page_size + 1])

    has_more = len(messages) > page_size
    messages = messages[:page_size]

    if page == 1 and not has_more:
        total = len(messages)
    else:
        total = -1

    return messages, total, has_more


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
    """Get conversation history within token limit, starting from newest messages."""
    if max_tokens is None:
        max_tokens = get_token_limit(model)

    reserved_messages = []
    if system_prompt:
        reserved_messages.append({"role": "system", "content": system_prompt})
    if summary:
        reserved_messages.append({"role": "system", "content": f"對話摘要：{summary}"})

    reserved_tokens = count_messages_tokens(reserved_messages, model) if reserved_messages else 0
    available_tokens = max_tokens - reserved_tokens

    all_messages = list(
        Message.objects.filter(conversation_id=conversation_id)
        .order_by("-created_at")
        .values("role", "content")
    )

    all_msg_dicts = [{"role": msg["role"], "content": msg["content"]} for msg in all_messages]

    selected_messages: list[dict] = []
    current_tokens = 0

    for msg_dict in all_msg_dicts:
        msg_tokens = count_messages_tokens([msg_dict], model)

        if current_tokens + msg_tokens > available_tokens:
            break

        selected_messages.append(msg_dict)
        current_tokens += msg_tokens

    selected_messages.reverse()

    total_tokens = reserved_tokens + current_tokens
    return selected_messages, total_tokens


def update_conversation_summary(
    conversation: Conversation,
    summary: str,
    token_count: int,
) -> Conversation:
    """Update conversation summary."""
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
