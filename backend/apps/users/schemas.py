"""User schemas for API."""

import re
from uuid import UUID

from ninja import Schema
from pydantic import EmailStr, Field, field_validator


class UserRegisterSchema(Schema):
    """Schema for user registration."""

    email: EmailStr = Field(max_length=255)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate password contains uppercase, lowercase, digit, and special char."""
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'`~]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserSchema(Schema):
    """Schema for user response."""

    id: UUID
    email: str = Field(max_length=255)
    username: str = Field(max_length=50)


class ErrorSchema(Schema):
    """Schema for error response."""

    error: str = Field(min_length=1, max_length=500)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z_]+$")


class LogoutSchema(Schema):
    """Schema for logout request."""

    refresh_token: str | None = Field(None, min_length=10, max_length=1000)


class LogoutResponseSchema(Schema):
    """Schema for logout response."""

    message: str = Field(min_length=1, max_length=200)
