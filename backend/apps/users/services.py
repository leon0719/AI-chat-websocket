"""User services."""

import time

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db.models import Q

from apps.core.exceptions import ValidationError
from apps.core.log_config import logger
from apps.users.jwt_utils import decode_jwt_token
from apps.users.models import User

REGISTRATION_ERROR_MESSAGE = (
    "Unable to complete registration. Please try a different email or username."
)


def blacklist_token(token: str) -> None:
    """Add a token to the blacklist using Redis TTL for auto-cleanup."""
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
        logger.debug(f"Token blacklisted: jti={jti}, ttl={ttl}s")


def is_token_blacklisted(jti: str) -> bool:
    """Check if a token is blacklisted by its jti claim."""
    return bool(cache.get(f"token_blacklist:{jti}", False))


def register_user(email: str, username: str, password: str) -> User:
    """Register a new user."""
    if User.objects.filter(Q(email=email) | Q(username=username)).exists():
        logger.warning(f"Registration failed: duplicate email or username attempt for {email}")
        raise ValidationError(REGISTRATION_ERROR_MESSAGE)

    user = User.objects.create(
        email=email,
        username=username,
        password=make_password(password),
    )
    logger.info(f"New user registered: user_id={user.id}, email={email}")
    return user
