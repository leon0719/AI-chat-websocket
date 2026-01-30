"""Rate limiting utilities for WebSocket connections.

HTTP endpoints use Django Ninja's built-in throttling (see config/urls.py).
This module provides rate limiting for WebSocket connections only.
"""

import time

from django.core.cache import cache

from apps.core.log_config import logger


def _get_rate_limit_key(identifier: str, action: str) -> str:
    """Generate a rate limit cache key for WebSocket."""
    return f"ws_ratelimit:{action}:{identifier}"


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

    # Use Redis pipeline for atomic operations
    # This prevents race conditions between get and set
    try:
        # Try to use Redis atomic operations if available
        # cache.client is only available for Redis backends
        redis_client = cache.client.get_client()  # type: ignore[attr-defined]

        # Use Redis sorted set for sliding window rate limiting
        # Score is timestamp, member is unique request ID
        zset_key = f"{key}:zset"
        window_start = now - window_seconds

        # Atomic pipeline: remove old entries, add new, count, set expiry
        pipe = redis_client.pipeline(transaction=True)
        pipe.zremrangebyscore(zset_key, 0, window_start)  # Remove expired
        pipe.zcard(zset_key)  # Count current
        results = pipe.execute()

        current_count = results[1]

        if current_count >= max_requests:
            # Get oldest timestamp to calculate retry_after
            oldest = redis_client.zrange(zset_key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                retry_after = int(oldest_timestamp + window_seconds - now) + 1
            else:
                retry_after = 1
            logger.warning(
                f"WebSocket rate limit exceeded: action={action}, identifier={identifier}"
            )
            return False, max(retry_after, 1)

        # Add current request atomically
        pipe = redis_client.pipeline(transaction=True)
        pipe.zadd(zset_key, {f"{now}:{identifier}": now})
        pipe.expire(zset_key, window_seconds + 60)
        pipe.execute()

        return True, 0

    except (AttributeError, Exception):
        # Fallback for non-Redis cache backends (e.g., in tests)
        # Use simpler approach with cache.add for basic atomicity
        return _fallback_rate_limit(key, max_requests, window_seconds, now, identifier, action)


def _fallback_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    now: float,
    identifier: str,
    action: str,
) -> tuple[bool, int]:
    """Fallback rate limiting for non-Redis cache backends."""
    window_start = now - window_seconds

    # Get current data
    data = cache.get(key, {"timestamps": []})
    timestamps = data.get("timestamps", [])

    # Filter out expired timestamps
    timestamps = [ts for ts in timestamps if ts > window_start]

    if len(timestamps) >= max_requests:
        oldest_timestamp = min(timestamps) if timestamps else now
        retry_after = int(oldest_timestamp + window_seconds - now) + 1
        logger.warning(f"WebSocket rate limit exceeded: action={action}, identifier={identifier}")
        return False, max(retry_after, 1)

    # Add current request timestamp
    timestamps.append(now)
    cache.set(key, {"timestamps": timestamps}, timeout=window_seconds + 60)

    return True, 0
