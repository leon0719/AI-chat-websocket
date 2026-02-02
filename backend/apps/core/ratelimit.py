"""Rate limiting utilities for WebSocket connections.

HTTP endpoints use Django Ninja's built-in throttling (see config/urls.py).
This module provides rate limiting for WebSocket connections only.
"""

import threading
import time
from functools import lru_cache

import redis
from django.conf import settings
from django.core.cache import cache

from apps.core.log_config import logger

_fallback_lock = threading.Lock()
_redis_client: redis.Redis | None = None


def _is_fail_closed() -> bool:
    """Check if rate limiting should fail closed (deny on Redis failure)."""
    return getattr(settings, "RATELIMIT_FAIL_CLOSED", True)


def _get_rate_limit_key(identifier: str, action: str) -> str:
    """Generate a rate limit cache key for WebSocket."""
    return f"ws_ratelimit:{action}:{identifier}"


@lru_cache(maxsize=1)
def _get_redis_url() -> str | None:
    """Get Redis URL from Django settings."""
    # Try to get from cache backend config
    cache_config = getattr(settings, "CACHES", {}).get("default", {})
    location = cache_config.get("LOCATION")
    if location:
        return location

    # Fallback to REDIS_URL setting
    return getattr(settings, "REDIS_URL", None)


def _get_redis_client() -> redis.Redis | None:
    """Get Redis client for rate limiting.

    Creates a direct Redis connection using the URL from settings.
    This is more reliable than accessing Django cache internals.
    """
    global _redis_client

    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    redis_url = _get_redis_url()
    if not redis_url:
        return None

    try:
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
        return None


def check_ws_rate_limit(
    identifier: str,
    action: str,
    max_requests: int = 20,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """Check rate limit for WebSocket actions. Returns (is_allowed, retry_after_seconds)."""
    key = _get_rate_limit_key(identifier, action)
    now = time.time()

    redis_client = _get_redis_client()
    if redis_client is None:
        return _fallback_rate_limit(key, max_requests, window_seconds, now, identifier, action)

    try:
        return _redis_rate_limit(
            redis_client, key, max_requests, window_seconds, now, identifier, action
        )
    except Exception as e:
        logger.critical(f"Redis rate limit failed: {e}, action={action}, identifier={identifier}")
        return _fallback_rate_limit(key, max_requests, window_seconds, now, identifier, action)


def _redis_rate_limit(
    redis_client: redis.Redis,
    key: str,
    max_requests: int,
    window_seconds: int,
    now: float,
    identifier: str,
    action: str,
) -> tuple[bool, int]:
    """Rate limiting using Redis sorted set for sliding window."""
    zset_key = f"{key}:zset"
    window_start = now - window_seconds

    pipe = redis_client.pipeline(transaction=True)
    pipe.zremrangebyscore(zset_key, 0, window_start)
    pipe.zcard(zset_key)
    results = pipe.execute()

    current_count = results[1]

    if current_count >= max_requests:
        oldest = redis_client.zrange(zset_key, 0, 0, withscores=True)
        if oldest:
            oldest_timestamp = oldest[0][1]
            retry_after = int(oldest_timestamp + window_seconds - now) + 1
        else:
            retry_after = 1
        logger.warning(f"WebSocket rate limit exceeded: action={action}, identifier={identifier}")
        return False, max(retry_after, 1)

    pipe = redis_client.pipeline(transaction=True)
    pipe.zadd(zset_key, {f"{now}:{identifier}": now})
    pipe.expire(zset_key, window_seconds + 60)
    pipe.execute()

    return True, 0


def _fallback_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    now: float,
    identifier: str,
    action: str,
) -> tuple[bool, int]:
    """Fallback rate limiting when Redis is unavailable.

    When RATELIMIT_FAIL_CLOSED is True (default), deny requests for security.
    This prevents attackers from bypassing rate limits by causing Redis failures.

    Uses threading.Lock for thread-safety in non-Redis environments.
    """
    if _is_fail_closed():
        logger.critical(
            f"Rate limit fallback triggered (fail-closed): action={action}, identifier={identifier}"
        )
        return False, 60

    with _fallback_lock:
        window_start = now - window_seconds

        data = cache.get(key, {"timestamps": []})
        timestamps = data.get("timestamps", [])
        timestamps = [ts for ts in timestamps if ts > window_start]

        if len(timestamps) >= max_requests:
            oldest_timestamp = min(timestamps) if timestamps else now
            retry_after = int(oldest_timestamp + window_seconds - now) + 1
            logger.warning(
                f"WebSocket rate limit exceeded: action={action}, identifier={identifier}"
            )
            return False, max(retry_after, 1)

        timestamps.append(now)
        cache.set(key, {"timestamps": timestamps}, timeout=window_seconds + 60)

        return True, 0
