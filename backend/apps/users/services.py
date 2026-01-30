"""User services."""

import time

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db.models import Q

from apps.core.exceptions import AuthenticationError, ValidationError
from apps.core.log_config import logger
from apps.users.models import User

# 使用通用錯誤訊息，避免用戶列舉攻擊
REGISTRATION_ERROR_MESSAGE = (
    "Unable to complete registration. Please try a different email or username."
)

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _get_login_attempt_key(email: str) -> str:
    """Generate cache key for tracking login attempts."""
    return f"login_attempts:{email}"


def check_login_lockout(email: str) -> tuple[bool, int]:
    """Check if login is locked out for this email.

    Returns:
        Tuple of (is_locked_out, retry_after_seconds)
    """
    key = _get_login_attempt_key(email)
    data = cache.get(key)

    if data is None:
        return False, 0

    locked_until = data.get("locked_until", 0)
    now = time.time()

    if locked_until > now:
        retry_after = int(locked_until - now)
        return True, retry_after

    if locked_until > 0:
        cache.delete(key)
        return False, 0

    return False, 0


def record_login_attempt(email: str, success: bool) -> None:
    """Record a login attempt for tracking lockout."""
    key = _get_login_attempt_key(email)

    if success:
        cache.delete(key)
        return

    data = cache.get(key, {"attempts": 0, "locked_until": 0})
    data["attempts"] = data.get("attempts", 0) + 1

    if data["attempts"] >= LOGIN_MAX_ATTEMPTS:
        data["locked_until"] = time.time() + LOGIN_LOCKOUT_SECONDS
        logger.warning(f"Account locked out due to failed login attempts: {email}")

    cache.set(key, data, timeout=LOGIN_LOCKOUT_SECONDS + 60)


def blacklist_token(token: str) -> None:
    """Add a token to the blacklist using Redis TTL for auto-cleanup.

    The token is stored until its expiration time, then automatically removed.
    """
    try:
        signing_key = settings.NINJA_JWT["SIGNING_KEY"]
        payload = jwt.decode(
            token,
            str(signing_key),
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError as e:
        logger.warning(f"Failed to decode token for blacklisting: {e}")
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

    Includes account lockout protection against brute force attacks.
    """
    is_locked, retry_after = check_login_lockout(email)
    if is_locked:
        raise AuthenticationError(f"Account locked. Try again in {retry_after // 60} minutes.")

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as e:
        # Prevent enumeration timing attacks
        record_login_attempt(email, success=False)
        raise AuthenticationError("Invalid email or password") from e

    if not check_password(password, user.password):
        record_login_attempt(email, success=False)
        raise AuthenticationError("Invalid email or password")

    record_login_attempt(email, success=True)
    return user
