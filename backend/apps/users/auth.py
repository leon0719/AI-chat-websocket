"""JWT authentication utilities for WebSocket and REST API."""

from typing import Any, Literal

import jwt
from django.conf import settings
from django.http import HttpRequest
from ninja_jwt.authentication import JWTAuth as BaseJWTAuth
from ninja_jwt.exceptions import AuthenticationFailed

from apps.users.models import User
from apps.users.services import is_token_blacklisted
from config.settings.base import settings as app_settings


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
        algorithm = app_settings.JWT_ALGORITHM
        payload = jwt.decode(
            token,
            str(signing_key),
            algorithms=[algorithm],
            options={"verify_exp": True},
        )
    except jwt.PyJWTError:
        return None

    actual_token_type = payload.get("token_type")
    if actual_token_type != token_type:
        return None

    jti = payload.get("jti")
    if jti and is_token_blacklisted(jti):
        return None

    user_id = payload.get("user_id")
    if user_id is None:
        return None

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


class JWTAuth(BaseJWTAuth):
    """Custom JWT authentication with blacklist support.

    Extends ninja_jwt's JWTAuth to check if tokens have been blacklisted
    (e.g., after logout).
    """

    def authenticate(self, request: HttpRequest, token: str) -> Any:
        """Authenticate request with blacklist check."""
        try:
            signing_key = settings.NINJA_JWT["SIGNING_KEY"]
            algorithm = app_settings.JWT_ALGORITHM
            payload = jwt.decode(
                token,
                str(signing_key),
                algorithms=[algorithm],
                options={"verify_exp": True},
            )
        except jwt.PyJWTError:
            return super().authenticate(request, token)

        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            raise AuthenticationFailed("Token has been revoked")

        return super().authenticate(request, token)
