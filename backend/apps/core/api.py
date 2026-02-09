"""Core API endpoints."""

from django.core.cache import cache
from django.db import DatabaseError, OperationalError, connection
from ninja import Router
from redis.exceptions import RedisError

from apps.core.log_config import logger

router = Router()


@router.get("/health/", response={200: dict, 503: dict})
def health_check(request):
    """Health check endpoint for load balancers and container orchestration."""
    health = {
        "status": "healthy",
        "database": "ok",
        "redis": "ok",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except (DatabaseError, OperationalError):
        logger.exception("Database health check failed")
        health["database"] = "error"
        health["status"] = "unhealthy"

    try:
        cache.set("health_check", "ok", 1)
        cache.get("health_check")
    except (RedisError, ConnectionError, TimeoutError):
        logger.exception("Redis health check failed")
        health["redis"] = "error"
        health["status"] = "unhealthy"

    status_code = 200 if health["status"] == "healthy" else 503
    return status_code, health
