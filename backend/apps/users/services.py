"""User services."""

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Q

from apps.core.exceptions import AuthenticationError, ValidationError
from apps.users.models import User

# 使用通用錯誤訊息，避免用戶列舉攻擊
REGISTRATION_ERROR_MESSAGE = (
    "Unable to complete registration. Please try a different email or username."
)


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
    """Authenticate a user with email and password."""
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist as e:
        raise AuthenticationError("Invalid email or password") from e

    if not check_password(password, user.password):
        raise AuthenticationError("Invalid email or password")

    return user
