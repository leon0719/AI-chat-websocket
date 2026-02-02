"""Core schemas shared across applications."""

from ninja import Schema
from pydantic import Field


class ErrorSchema(Schema):
    """Schema for error response."""

    error: str = Field(min_length=1, max_length=500)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Z_]+$")
