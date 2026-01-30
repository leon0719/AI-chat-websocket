"""User services."""

import time

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db.models import Q

from apps.core.exceptions import AuthenticationError, ValidationError
from apps.core.log_config import logger
from apps.users.jwt_utils import decode_jwt_token
from apps.users.models import User

# 使用通用錯誤訊息，避免用戶列舉攻擊
REGISTRATION_ERROR_MESSAGE = (
    "Unable to complete registration. Please try a different email or username."
)


def blacklist_token(token: str) -> None:
    """Add a token to the blacklist using Redis TTL for auto-cleanup.

    The token is stored until its expiration time, then automatically removed.
    """
    payload = decode_jwt_token(token, verify_exp=False)
    if payload is None:
        logger.warning("Failed to decode token for blacklisting")
        return

    jti = payload.get("jti")
    if not jti:
        logger.warning("Token has no jti claim, cannot blacklist")
        return

    exp = payload.get("exp", 0)
    ttl = max(int(exp - time.time()), 0)

    if ttl > 0:
        cache.set(f"token_blacklist:{jti}", True, timeout=ttl)
        logger.info(f"Token blacklisted: jti={jti}, ttl={ttl}s")


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token is blacklisted by its jti claim."""
    return bool(cache.get(f"token_blacklist:{jti}", False))


def register_user(email: str, username: str, password: str) -> User:
    """Register a new user.

    Uses generic error messages to prevent user enumeration attacks.
    """
    # 使用單一查詢檢查 email 和 username，避免洩露哪個已存在
    if User.objects.filter(Q(email=email) | Q(username=username)).exists():
        raise ValidationError(REGISTRATION_ERROR_MESSAGE)

    user = User.objects.create(
        email=email,
        username=username,
        password=make_password(password),
    )
    return user


def authenticate_user(email: str, password: str) -> User:
    """Authenticate a user with email and password.

    Brute force protection is handled by django-axes.
    """
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as e:
        raise AuthenticationError("Invalid email or password") from e

    if not check_password(password, user.password):
        raise AuthenticationError("Invalid email or password")

    return user
