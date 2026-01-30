"""Chat models."""

import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models

# Supported models
SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

# User message content limit (validated before saving)
MAX_USER_MESSAGE_LENGTH = 10000

# Max content length for AI responses (larger than user input)
MAX_CONTENT_LENGTH = 100000


class MessageRole(models.TextChoices):
    """Message role choices."""

    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class Conversation(models.Model):
    """Conversation model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    model = models.CharField(max_length=50, default="gpt-4o")
    system_prompt = models.TextField(
        blank=True,
        default="You are a helpful assistant. Always respond in Traditional Chinese (繁體中文).",
        validators=[MaxLengthValidator(10000)],
    )
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
    )
    is_archived = models.BooleanField(default=False)
    # 對話摘要相關欄位
    summary = models.TextField(
        blank=True, default="", help_text="AI-generated conversation summary"
    )
    summary_token_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Token count at time of summary generation",
    )
    last_summarized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]
        verbose_name = "conversation"
        verbose_name_plural = "conversations"
        indexes = [
            models.Index(fields=["user", "-updated_at"], name="conv_user_updated_idx"),
            models.Index(fields=["user", "is_archived"], name="conv_user_archived_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title or 'Untitled'} ({self.id})"


class Message(models.Model):
    """Message model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField(validators=[MaxLengthValidator(MAX_CONTENT_LENGTH)])
    prompt_tokens = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    completion_tokens = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    model_used = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Model used for this message (may differ from conversation default)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        verbose_name = "message"
        verbose_name_plural = "messages"
        indexes = [
            models.Index(fields=["conversation", "created_at"], name="msg_conv_created_idx"),
            models.Index(fields=["conversation", "-created_at"], name="msg_conv_created_desc_idx"),
            models.Index(fields=["-created_at"], name="msg_created_desc_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:50]}..."
