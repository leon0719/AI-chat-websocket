"""User models."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from uuid6 import uuid7


class User(AbstractUser):
    """Custom user model with UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    email = models.EmailField(unique=True)

    # Use email as the username field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        verbose_name = "user"
        verbose_name_plural = "users"
        indexes = [
            models.Index(fields=["email"], name="users_email_idx"),
        ]

    def __str__(self) -> str:
        return self.email
