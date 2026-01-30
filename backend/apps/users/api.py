"""User API endpoints."""

from django.db import DatabaseError, IntegrityError
from ninja import Router
from ninja.throttling import AnonRateThrottle
from ninja_jwt.authentication import JWTAuth

from apps.core.exceptions import ValidationError
from apps.core.log_config import logger
from apps.users.schemas import (
    ErrorSchema,
    UserRegisterSchema,
    UserSchema,
)
from apps.users.services import register_user

router = Router()


@router.post(
    "/register",
    response={201: UserSchema, 400: ErrorSchema, 500: ErrorSchema},
    throttle=[AnonRateThrottle("5/5m")],  # 5 requests per 5 minutes
)
def register(request, payload: UserRegisterSchema):
    """Register a new user."""
    try:
        user = register_user(
            email=payload.email,
            username=payload.username,
            password=payload.password,
        )
        return 201, user
    except ValidationError as e:
        return 400, {"error": e.message, "code": e.code}
    except IntegrityError as e:
        # Database constraint violation (e.g., duplicate email/username)
        logger.warning(f"Registration integrity error: {e}")
        return 400, {"error": "Email or username already exists", "code": "VALIDATION_ERROR"}
    except DatabaseError as e:
        # Database connection or query errors
        logger.exception(f"Database error during registration: {e}")
        return 500, {"error": "Database error occurred", "code": "DATABASE_ERROR"}
    except Exception as e:
        logger.exception(f"Unexpected error during registration: {e}")
        return 500, {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}


@router.get("/me", response={200: UserSchema, 401: ErrorSchema}, auth=JWTAuth())
def me(request):
    """Get current user info."""
    return 200, request.auth
