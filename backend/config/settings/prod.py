"""Production settings."""

from config.settings.base import *  # noqa: F403
from config.settings.base import settings

DEBUG = False

ALLOWED_HOSTS = settings.get_allowed_hosts()

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Cross-Origin policies
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# CSRF trusted origins (same as CORS origins)
CSRF_TRUSTED_ORIGINS = settings.get_cors_allowed_origins()

# Use SMTP email backend in production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Rate limiting - fail closed (deny requests when Redis is unavailable)
RATELIMIT_FAIL_CLOSED = True
