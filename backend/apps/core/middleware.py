"""Custom middleware for the application."""

import uuid

from django.conf import settings

from apps.core.log_config import request_id_var, user_id_var


class ContentSecurityPolicyMiddleware:
    """Middleware to add Content-Security-Policy header for API responses.

    Enforces strict CSP for API-only applications to prevent XSS attacks
    on any accidental HTML responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not settings.DEBUG:
            response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        return response


class RequestContextMiddleware:
    """Middleware to add request context for structured logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_token = request_id_var.set(request_id)

        if hasattr(request, "user") and request.user.is_authenticated:
            user_id_token = user_id_var.set(str(request.user.id))
        else:
            user_id_token = user_id_var.set("-")

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            # Prevent context leakage in async environments
            request_id_var.reset(request_id_token)
            user_id_var.reset(user_id_token)
