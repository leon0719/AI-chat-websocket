"""Chat schemas for API."""

from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field, field_validator, model_validator

from apps.chat.models import MAX_CONTENT_LENGTH, SUPPORTED_MODELS, MessageRole


def _validate_supported_model(v: str | None) -> str | None:
    """Validate model is in SUPPORTED_MODELS list."""
    if v is not None and v not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported model. Choose from: {SUPPORTED_MODELS}")
    return v


class ConversationCreateSchema(Schema):
    """Schema for creating a conversation."""

    title: str = Field("New Conversation", min_length=1, max_length=255)
    model: str = "gpt-4o"
    system_prompt: str = Field(
        "You are a helpful assistant. Always respond in Traditional Chinese (繁體中文).",
        min_length=1,
        max_length=10000,
    )
    temperature: float = Field(0.7, ge=0.0, le=2.0)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        return _validate_supported_model(v)  # type: ignore[return-value]


class ConversationUpdateSchema(Schema):
    """Schema for updating a conversation."""

    title: str | None = Field(None, min_length=1, max_length=255)
    model: str | None = None
    system_prompt: str | None = Field(None, min_length=1, max_length=10000)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    is_archived: bool | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        return _validate_supported_model(v)

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ConversationUpdateSchema":
        if all(
            getattr(self, field) is None
            for field in ["title", "model", "system_prompt", "temperature", "is_archived"]
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class ConversationSchema(Schema):
    """Schema for conversation response."""

    id: UUID
    title: str = Field(max_length=255)
    model: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(min_length=1, max_length=10000)
    temperature: float = Field(ge=0.0, le=2.0)
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ConversationListSchema(Schema):
    """Schema for conversation list response."""

    id: UUID
    title: str = Field(max_length=255)
    model: str = Field(min_length=1, max_length=50)
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class MessageSchema(Schema):
    """Schema for message response."""

    id: UUID
    role: MessageRole
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    prompt_tokens: int | None = Field(None, ge=0)
    completion_tokens: int | None = Field(None, ge=0)
    model_used: str = Field(default="", max_length=50)
    created_at: datetime


class PaginatedMessagesSchema(Schema):
    """Schema for paginated messages response."""

    messages: list[MessageSchema]
    total: int = Field(ge=-1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool = Field(default=False)


class PaginatedConversationsSchema(Schema):
    """Schema for paginated conversations response."""

    conversations: list[ConversationListSchema]
    total: int = Field(ge=-1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool = Field(default=False)
