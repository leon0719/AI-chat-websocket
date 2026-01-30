"""JWT authentication utilities for WebSocket connections."""

from typing import Literal

import jwt
from django.conf import settings

from apps.users.models import User


def get_user_from_token(
    token: str,
    token_type: Literal["access", "refresh"] = "access",  # noqa: S107
) -> User | None:
    """Get user from a JWT token.

    This function is used for WebSocket authentication where we need to
    manually validate tokens from query parameters.

    Args:
        token: The JWT token string.
        token_type: Expected token type ("access" or "refresh"). Defaults to "access".

    Returns:
        User if token is valid and of correct type, None otherwise.
    """
    try:
        signing_key = settings.NINJA_JWT["SIGNING_KEY"]
        payload = jwt.decode(
            token,
            str(signing_key),
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.PyJWTError:
        return None

    # Check token type
    actual_token_type = payload.get("token_type")
    if actual_token_type != token_type:
        return None

    user_id = payload.get("user_id")
    if user_id is None:
        return None

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None
