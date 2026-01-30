"""Local development settings."""

from config.settings.base import *  # noqa: F403

DEBUG = True

# Restrict to specific development hosts
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"]

# CORS - Restrict to specific development origins
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite default port
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# Use console email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
