"""User API endpoints."""

from ninja import Router
from ninja.throttling import AnonRateThrottle

from apps.users.auth import JWTAuth
from apps.users.schemas import (
    ErrorSchema,
    LogoutResponseSchema,
    LogoutSchema,
    UserRegisterSchema,
    UserSchema,
)
from apps.users.services import blacklist_token, register_user

router = Router()


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


@router.get("/me", response={200: UserSchema, 401: ErrorSchema}, auth=JWTAuth())
def me(request):
    """Get current user info."""
    return 200, request.auth


@router.post(
    "/logout",
    response={200: LogoutResponseSchema, 401: ErrorSchema},
    auth=JWTAuth(),
)
def logout(request, payload: LogoutSchema = None):
    """Logout and invalidate access and refresh tokens."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        blacklist_token(token)

    if payload and payload.refresh_token:
        blacklist_token(payload.refresh_token)

    return 200, {"message": "Successfully logged out"}
