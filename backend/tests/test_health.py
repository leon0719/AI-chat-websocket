"""Tests for health check endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from django.db import OperationalError
from django.test import Client
from redis.exceptions import RedisError


@pytest.mark.django_db
class TestHealthCheck:
    """Test health check endpoint."""

    def test_healthy(self):
        client = Client()
        response = client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "ok"
        assert data["redis"] == "ok"

    def test_database_error(self):
        with patch("apps.core.api.connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = OperationalError("DB down")
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            client = Client()
            response = client.get("/api/health/")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "error"

    def test_redis_error(self):
        with patch("apps.core.api.cache") as mock_cache:
            mock_cache.set.side_effect = RedisError("Redis down")

            client = Client()
            response = client.get("/api/health/")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["redis"] == "error"
