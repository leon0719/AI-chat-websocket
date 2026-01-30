"""User schemas for API."""

from uuid import UUID

from ninja import Schema
from pydantic import EmailStr, Field


class UserRegisterSchema(Schema):
    """Schema for user registration."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=12, max_length=128)


class UserSchema(Schema):
    """Schema for user response."""

    id: UUID
    email: str
    username: str


class ErrorSchema(Schema):
    """Schema for error response."""

    error: str
    code: str


class LogoutSchema(Schema):
    """Schema for logout request."""

    refresh_token: str | None = None


class LogoutResponseSchema(Schema):
    """Schema for logout response."""

    message: str
