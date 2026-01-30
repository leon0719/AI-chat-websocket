"""Chat schemas for API."""

from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field, field_validator, model_validator

from apps.chat.models import SUPPORTED_MODELS


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
        if v not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model. Choose from: {SUPPORTED_MODELS}")
        return v


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
        if v is not None and v not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model. Choose from: {SUPPORTED_MODELS}")
        return v

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
    title: str
    model: str
    system_prompt: str
    temperature: float
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ConversationListSchema(Schema):
    """Schema for conversation list response."""

    id: UUID
    title: str
    model: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class MessageSchema(Schema):
    """Schema for message response."""

    id: UUID
    role: str
    content: str
    prompt_tokens: int | None
    completion_tokens: int | None
    model_used: str
    created_at: datetime


class PaginatedMessagesSchema(Schema):
    """Schema for paginated messages response."""

    messages: list[MessageSchema]
    total: int
    page: int
    page_size: int
