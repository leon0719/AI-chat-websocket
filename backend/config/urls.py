"""URL configuration for the project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import DatabaseError
from django.http import HttpRequest
from django.urls import path
from ninja.throttling import AnonRateThrottle, AuthRateThrottle
from ninja_extra import NinjaExtraAPI
from ninja_jwt.controller import NinjaJWTDefaultController

from apps.chat.api import router as chat_router
from apps.core.api import router as core_router
from apps.core.exceptions import NotFoundError, ValidationError
from apps.core.log_config import logger
from apps.users.api import router as users_router

api = NinjaExtraAPI(
    title="Chatbot API",
    version="1.0.0",
    description="Django Ninja WebSocket Chatbot API",
    # Global rate limiting
    throttle=[
        AnonRateThrottle("60/m"),  # Anonymous: 60 requests/minute
        AuthRateThrottle("120/m"),  # Authenticated: 120 requests/minute
    ],
)


@api.exception_handler(NotFoundError)
def handle_not_found(request: HttpRequest, exc: NotFoundError):
    """Handle NotFoundError globally."""
    return api.create_response(request, {"error": exc.message, "code": exc.code}, status=404)


@api.exception_handler(ValidationError)
def handle_validation_error(request: HttpRequest, exc: ValidationError):
    """Handle ValidationError globally."""
    return api.create_response(request, {"error": exc.message, "code": exc.code}, status=400)


@api.exception_handler(DatabaseError)
def handle_database_error(request: HttpRequest, exc: DatabaseError):
    """Handle DatabaseError globally."""
    logger.exception(f"Database error: {exc}")
    return api.create_response(
        request, {"error": "Database error occurred", "code": "DATABASE_ERROR"}, status=500
    )


# Register JWT controller (provides /token/pair, /token/refresh, /token/verify)
api.register_controllers(NinjaJWTDefaultController)

api.add_router("", core_router, tags=["health"])
# Auth endpoints have stricter rate limits (applied at endpoint level)
api.add_router("/auth", users_router, tags=["auth"])
api.add_router("/conversations", chat_router, tags=["conversations"])

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    *static(settings.STATIC_URL, document_root=settings.STATIC_ROOT),
]
