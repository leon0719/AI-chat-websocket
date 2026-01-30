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

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# Use SMTP email backend in production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
