"""Tests for rate limiting functionality."""

from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.core.ratelimit import (
    _fallback_rate_limit,
    check_ws_rate_limit,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestWebSocketRateLimit:
    """Test WebSocket rate limiting."""

    def test_allows_requests_within_limit(self):
        """Test that requests within limit are allowed."""
        identifier = "test-user-1"
        action = "message"

        for i in range(5):
            is_allowed, retry_after = check_ws_rate_limit(
                identifier=identifier,
                action=action,
                max_requests=10,
                window_seconds=60,
            )
            assert is_allowed is True, f"Request {i + 1} should be allowed"
            assert retry_after == 0

    def test_blocks_requests_over_limit(self):
        """Test that requests over limit are blocked."""
        identifier = "test-user-2"
        action = "message"
        max_requests = 3

        # First, make max_requests allowed requests
        for _ in range(max_requests):
            is_allowed, _ = check_ws_rate_limit(
                identifier=identifier,
                action=action,
                max_requests=max_requests,
                window_seconds=60,
            )
            assert is_allowed is True

        # Next request should be blocked
        is_allowed, retry_after = check_ws_rate_limit(
            identifier=identifier,
            action=action,
            max_requests=max_requests,
            window_seconds=60,
        )
        assert is_allowed is False
        assert retry_after > 0

    def test_different_identifiers_have_separate_limits(self):
        """Test that different users have separate rate limits."""
        action = "message"
        max_requests = 2

        # User 1 exhausts their limit
        for _ in range(max_requests):
            check_ws_rate_limit(
                identifier="user-1",
                action=action,
                max_requests=max_requests,
                window_seconds=60,
            )

        # User 1 is blocked
        is_allowed, _ = check_ws_rate_limit(
            identifier="user-1",
            action=action,
            max_requests=max_requests,
            window_seconds=60,
        )
        assert is_allowed is False

        # User 2 can still make requests
        is_allowed, _ = check_ws_rate_limit(
            identifier="user-2",
            action=action,
            max_requests=max_requests,
            window_seconds=60,
        )
        assert is_allowed is True


class TestFallbackRateLimit:
    """Test fallback rate limiting behavior."""

    def test_fail_closed_denies_requests(self):
        """Test that fail-closed mode denies requests when Redis unavailable."""
        with patch("apps.core.ratelimit._is_fail_closed", return_value=True):
            is_allowed, retry_after = _fallback_rate_limit(
                key="test-key",
                max_requests=10,
                window_seconds=60,
                now=1000.0,
                identifier="test-user",
                action="test-action",
            )
            assert is_allowed is False
            assert retry_after == 60

    def test_fail_open_allows_requests(self):
        """Test that fail-open mode allows requests (for testing)."""
        with patch("apps.core.ratelimit._is_fail_closed", return_value=False):
            is_allowed, retry_after = _fallback_rate_limit(
                key="test-key-open",
                max_requests=10,
                window_seconds=60,
                now=1000.0,
                identifier="test-user",
                action="test-action",
            )
            assert is_allowed is True
            assert retry_after == 0

    def test_fail_open_blocks_over_limit(self):
        """Test that fail-open fallback blocks when over limit."""
        with patch("apps.core.ratelimit._is_fail_closed", return_value=False):
            now = 1000.0
            for i in range(3):
                _fallback_rate_limit(
                    key="test-key-overlimit",
                    max_requests=3,
                    window_seconds=60,
                    now=now + i * 0.1,
                    identifier="test-user",
                    action="test-action",
                )

            is_allowed, retry_after = _fallback_rate_limit(
                key="test-key-overlimit",
                max_requests=3,
                window_seconds=60,
                now=now + 1.0,
                identifier="test-user",
                action="test-action",
            )
            assert is_allowed is False
            assert retry_after > 0
