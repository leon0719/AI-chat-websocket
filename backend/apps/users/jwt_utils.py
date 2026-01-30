"""JWT utility functions.

This module contains pure JWT utilities without dependencies on auth or services,
avoiding circular imports.
"""

from enum import StrEnum
from typing import Any

import jwt
from django.conf import settings

from config.settings.base import settings as app_settings


class TokenType(StrEnum):
    """JWT token types to prevent type confusion attacks."""

    ACCESS = "access"
    REFRESH = "refresh"


def decode_jwt_token(token: str, verify_exp: bool = True) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string.
        verify_exp: Whether to verify token expiration. Defaults to True.

    Returns:
        Token payload dict if valid, None otherwise.
    """
    try:
        signing_key = settings.NINJA_JWT["SIGNING_KEY"]
        algorithm = app_settings.JWT_ALGORITHM
        return jwt.decode(
            token,
            str(signing_key),
            algorithms=[algorithm],
            options={"verify_exp": verify_exp},
        )
    except jwt.PyJWTError:
        return None
