"""Tests for authentication endpoints."""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test to reset rate limiting."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestAuthEndpoints:
    """Test authentication API endpoints."""

    def test_register_success(self, api_client):
        """Test successful user registration."""
        response = api_client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "username": "newuser",
                "password": "newpass123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"

    def test_register_duplicate_email(self, api_client, user):
        """Test registration with duplicate email."""
        response = api_client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "username": "another",
                "password": "password123",
            },
        )
        assert response.status_code == 400

    def test_login_success(self, api_client, user):
        """Test successful login via token/pair endpoint."""
        response = api_client.post(
            "/token/pair",
            json={
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.json()}"
        )
        data = response.json()
        assert "access" in data
        assert "refresh" in data

    def test_login_invalid_credentials(self, api_client, user):
        """Test login with invalid credentials."""
        response = api_client.post(
            "/token/pair",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_me_authenticated(self, authenticated_client, user):
        """Test getting current user info."""
        response = authenticated_client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email

    def test_me_unauthenticated(self, api_client):
        """Test getting current user info without authentication."""
        response = api_client.get("/auth/me")
        assert response.status_code == 401

    def test_token_refresh(self, api_client, user):
        """Test token refresh."""
        # First login to get tokens
        login_response = api_client.post(
            "/token/pair",
            json={
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh"]

        # Then refresh the token
        refresh_response = api_client.post(
            "/token/refresh",
            json={"refresh": refresh_token},
        )
        assert refresh_response.status_code == 200
        assert "access" in refresh_response.json()
