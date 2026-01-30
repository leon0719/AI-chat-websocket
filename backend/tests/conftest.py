"""Pytest configuration and fixtures."""

import os

import pytest
from django.contrib.auth import get_user_model
from ninja.testing import TestClient
from ninja_jwt.tokens import AccessToken

from config.urls import api

# Prevent Django Ninja TestClient registry conflicts
os.environ["NINJA_SKIP_REGISTRY"] = "true"

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
    )


@pytest.fixture
def api_client():
    """Create a test API client."""
    return TestClient(api)


@pytest.fixture
def authenticated_client(api_client, user):
    """Create an authenticated test client."""
    token = AccessToken.for_user(user)
    api_client.headers = {"Authorization": f"Bearer {token!s}"}
    return api_client
