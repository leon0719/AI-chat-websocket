"""Chat app configuration."""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Chat application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chat"
