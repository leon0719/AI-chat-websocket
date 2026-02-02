"""Django base settings."""

import os
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import dj_database_url
from pydantic_settings import BaseSettings, SettingsConfigDict

# 根據 ENV 環境變數決定讀取哪個 .env 檔案
# ENV=local -> .env.local (預設)
# ENV=prod  -> .env.prod
_env = os.getenv("ENV", "local")
_env_file = f".env.{_env}"


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Required - must be set in .env
    SECRET_KEY: str
    DATABASE_URL: str
    REDIS_URL: str
    OPENAI_API_KEY: str
    JWT_SECRET_KEY: str

    # Optional - have sensible defaults
    DEBUG: bool = False
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    def _parse_comma_separated(self, value: str) -> list[str]:
        """Parse comma-separated string into list, stripping whitespace."""
        return [v.strip() for v in value.split(",") if v.strip()]

    def get_allowed_hosts(self) -> list[str]:
        return self._parse_comma_separated(self.ALLOWED_HOSTS)

    def get_cors_allowed_origins(self) -> list[str]:
        return self._parse_comma_separated(self.CORS_ALLOWED_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = settings.SECRET_KEY
DEBUG = settings.DEBUG
ALLOWED_HOSTS = settings.get_allowed_hosts()

# Application definition
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "channels",
    "corsheaders",
    "ninja_jwt",
    "ninja_extra",
    "axes",
    # Local apps
    "apps.core",
    "apps.users",
    "apps.chat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Authentication backends (Axes for brute force protection)
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# CORS
CORS_ALLOWED_ORIGINS = settings.get_cors_allowed_origins()
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": dj_database_url.config(
        default=settings.DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Channel Layers
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [settings.REDIS_URL],
        },
    },
}

# Cache (Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": settings.REDIS_URL,
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Custom User Model
AUTH_USER_MODEL = "users.User"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django Ninja JWT
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    "SIGNING_KEY": settings.JWT_SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_AUTHENTICATION_RULE": "ninja_jwt.authentication.default_user_authentication_rule",
}

# Django Axes - brute force protection
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"
AXES_CACHE = "default"
