"""Rate limiting utilities for WebSocket connections.

HTTP endpoints use Django Ninja's built-in throttling (see config/urls.py).
This module provides rate limiting for WebSocket connections only.
"""

import time

from django.conf import settings
from django.core.cache import cache

from apps.core.log_config import logger


def _is_fail_closed() -> bool:
    """Check if rate limiting should fail closed (deny on Redis failure)."""
    return getattr(settings, "RATELIMIT_FAIL_CLOSED", True)


def _get_rate_limit_key(identifier: str, action: str) -> str:
    """Generate a rate limit cache key for WebSocket."""
    return f"ws_ratelimit:{action}:{identifier}"


def _get_redis_client():
    """Get Redis client, returns None if not available."""
    try:
        return cache.client.get_client()  # type: ignore[attr-defined]
    except AttributeError:
        return None


def check_ws_rate_limit(
    identifier: str,
    action: str,
    max_requests: int = 20,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """Check rate limit for WebSocket actions using atomic Redis operations.

    Args:
        identifier: Unique identifier (user ID or connection ID)
        action: Action name (e.g., "message", "connect")
        max_requests: Maximum allowed requests in window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (is_allowed, retry_after_seconds)
    """
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
    redis_client,
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
    """
    if _is_fail_closed():
        logger.critical(
            f"Rate limit fallback triggered (fail-closed): action={action}, identifier={identifier}"
        )
        return False, 60

    # Non-Redis cache backend (e.g., in tests with LocMemCache)
    window_start = now - window_seconds

    data = cache.get(key, {"timestamps": []})
    timestamps = data.get("timestamps", [])
    timestamps = [ts for ts in timestamps if ts > window_start]

    if len(timestamps) >= max_requests:
        oldest_timestamp = min(timestamps) if timestamps else now
        retry_after = int(oldest_timestamp + window_seconds - now) + 1
        logger.warning(f"WebSocket rate limit exceeded: action={action}, identifier={identifier}")
        return False, max(retry_after, 1)

    timestamps.append(now)
    cache.set(key, {"timestamps": timestamps}, timeout=window_seconds + 60)

    return True, 0
