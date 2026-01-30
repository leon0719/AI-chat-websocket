"""Chat admin configuration."""

from django.contrib import admin

from apps.chat.models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Conversation admin."""

    list_display = ["title", "user", "model", "is_archived", "created_at", "updated_at"]
    list_filter = ["model", "is_archived", "created_at"]
    search_fields = ["title", "user__email", "user__username"]
    ordering = ["-updated_at"]
    raw_id_fields = ["user"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Message admin."""

    list_display = ["short_content", "conversation", "role", "model_used", "created_at"]
    list_filter = ["role", "model_used", "created_at"]
    search_fields = ["content", "conversation__title", "conversation__user__email"]
    ordering = ["-created_at"]
    raw_id_fields = ["conversation"]

    @admin.display(description="Content")
    def short_content(self, obj):
        """Display truncated content."""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
