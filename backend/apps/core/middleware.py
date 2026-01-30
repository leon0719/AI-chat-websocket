"""Custom middleware for the application."""

import uuid

from django.http import JsonResponse

from apps.core.exceptions import AppError
from apps.core.log_config import logger, request_id_var, user_id_var


class RequestContextMiddleware:
    """Middleware to add request context for structured logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

        # Set context variables and keep tokens for reset
        request_id_token = request_id_var.set(request_id)

        # Set user ID if authenticated (after AuthenticationMiddleware)
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id_token = user_id_var.set(str(request.user.id))
        else:
            user_id_token = user_id_var.set("-")

        try:
            response = self.get_response(request)
            # Add request ID to response headers
            response["X-Request-ID"] = request_id
            return response
        finally:
            # Reset context variables to prevent leakage in async environments
            request_id_var.reset(request_id_token)
            user_id_var.reset(user_id_token)


class ExceptionMiddleware:
    """Middleware to handle application exceptions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        """Handle exceptions raised during request processing."""
        if isinstance(exception, AppError):
            return JsonResponse(
                {"error": exception.message, "code": exception.code},
                status=self._get_status_code(exception.code),
            )

        logger.exception("Unhandled exception")
        return JsonResponse(
            {"error": "Internal server error", "code": "INTERNAL_ERROR"},
            status=500,
        )

    def _get_status_code(self, code: str) -> int:
        """Map error codes to HTTP status codes."""
        status_map = {
            "AUTH_ERROR": 401,
            "FORBIDDEN": 403,
            "NOT_FOUND": 404,
            "VALIDATION_ERROR": 400,
            "AI_ERROR": 503,
        }
        return status_map.get(code, 500)
