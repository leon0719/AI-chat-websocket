"""User API endpoints."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse
from ninja import Router
from ninja.throttling import AnonRateThrottle
from ninja_jwt.tokens import RefreshToken

from apps.core.exceptions import AuthenticationError
from apps.core.log_config import logger
from apps.core.schemas import ErrorSchema
from apps.users.auth import JWTAuth
from apps.users.jwt_utils import TokenType, decode_jwt_token
from apps.users.models import User
from apps.users.schemas import (
    LoginSchema,
    LogoutResponseSchema,
    LogoutSchema,
    TokenResponseSchema,
    UserRegisterSchema,
    UserSchema,
)
from apps.users.services import blacklist_token, is_token_blacklisted, register_user

router = Router()

REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/auth/"
REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60  # 7 days


def _set_refresh_token_cookie(response: HttpResponse, refresh_token: str) -> None:
    """Set refresh token as HttpOnly cookie."""
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_MAX_AGE,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path=REFRESH_TOKEN_COOKIE_PATH,
    )


def _clear_refresh_token_cookie(response: HttpResponse) -> None:
    """Clear refresh token cookie."""
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
        samesite="Lax",
    )


@router.post(
    "/register",
    response={201: UserSchema, 400: ErrorSchema, 500: ErrorSchema},
    throttle=[AnonRateThrottle("5/5m")],  # 5 requests per 5 minutes
)
def register(request, payload: UserRegisterSchema):
    """Register a new user."""
    user = register_user(
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    return 201, user


@router.post(
    "/token/pair",
    response={200: TokenResponseSchema, 401: ErrorSchema},
    throttle=[AnonRateThrottle("10/m")],
)
def login(request, payload: LoginSchema, response: HttpResponse):
    """Login and return access token, set refresh token as HttpOnly cookie."""
    user = authenticate(request, email=payload.email, password=payload.password)

    if user is None:
        logger.warning(f"Login failed: invalid credentials for {payload.email}")
        raise AuthenticationError("Invalid email or password")

    refresh: RefreshToken = RefreshToken.for_user(user)  # type: ignore[assignment]
    access_token = str(refresh.access_token)
    refresh_token_str = str(refresh)

    _set_refresh_token_cookie(response, refresh_token_str)

    logger.info(f"User logged in: user_id={user.id}")
    return 200, {"access": access_token}


@router.post(
    "/token/refresh",
    response={200: TokenResponseSchema, 401: ErrorSchema},
    throttle=[AnonRateThrottle("30/m")],
)
def refresh_token(request, response: HttpResponse):
    """Refresh access token using HttpOnly cookie with token rotation."""
    refresh_token_str = request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME)

    if not refresh_token_str:
        raise AuthenticationError("No refresh token provided")

    payload = decode_jwt_token(refresh_token_str, verify_exp=True)
    if payload is None:
        raise AuthenticationError("Invalid or expired refresh token")

    token_type = payload.get("token_type")
    if token_type != TokenType.REFRESH:
        raise AuthenticationError("Invalid token type")

    jti = payload.get("jti")
    if jti and is_token_blacklisted(jti):
        raise AuthenticationError("Token has been revoked")

    user_id = payload.get("user_id")
    if not user_id:
        raise AuthenticationError("Invalid refresh token")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise AuthenticationError("User not found") from None

    try:
        old_refresh = RefreshToken(refresh_token_str)
        access_token = str(old_refresh.access_token)

        blacklist_token(refresh_token_str)

        new_refresh: RefreshToken = RefreshToken.for_user(user)  # type: ignore[assignment]
        new_refresh_token_str = str(new_refresh)

        _set_refresh_token_cookie(response, new_refresh_token_str)
    except Exception:
        raise AuthenticationError("Invalid refresh token") from None

    return 200, {"access": access_token}


@router.get("/me", response={200: UserSchema, 401: ErrorSchema}, auth=JWTAuth())
def me(request):
    """Get current user info."""
    return 200, request.auth


@router.post(
    "/logout",
    response={200: LogoutResponseSchema, 401: ErrorSchema},
    auth=JWTAuth(),
)
def logout(request, response: HttpResponse, payload: LogoutSchema | None = None):
    """Logout and invalidate access and refresh tokens, clear cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        blacklist_token(token)

    refresh_token_str = request.COOKIES.get(REFRESH_TOKEN_COOKIE_NAME)
    if refresh_token_str:
        blacklist_token(refresh_token_str)

    if payload and payload.refresh_token:
        blacklist_token(payload.refresh_token)

    _clear_refresh_token_cookie(response)

    logger.info(f"User logged out: user_id={request.auth.id}")
    return 200, {"message": "Successfully logged out"}
