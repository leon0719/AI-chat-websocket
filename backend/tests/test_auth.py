"""Tests for authentication endpoints."""

import pytest
from django.core.cache import cache

from apps.users.services import (
    LOGIN_MAX_ATTEMPTS,
    blacklist_token,
    check_login_lockout,
    is_token_blacklisted,
    record_login_attempt,
)


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
                "password": "newpassword123",  # 12+ chars required
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
                "password": "password12345",  # 12+ chars required
            },
        )
        assert response.status_code == 400

    def test_login_success(self, api_client, user):
        """Test successful login via token/pair endpoint."""
        response = api_client.post(
            "/token/pair",
            json={
                "email": "test@example.com",
                "password": "testpassword123",
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
                "password": "testpassword123",
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

    def test_logout_success(self, authenticated_client, user):
        """Test successful logout."""
        response = authenticated_client.post("/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"

    def test_logout_unauthenticated(self, api_client):
        """Test logout without authentication."""
        response = api_client.post("/auth/logout")
        assert response.status_code == 401

    def test_password_minimum_length(self, api_client):
        """Test password minimum length validation (12 chars)."""
        response = api_client.post(
            "/auth/register",
            json={
                "email": "short@example.com",
                "username": "shortpass",
                "password": "short123",  # Only 8 chars
            },
        )
        assert response.status_code == 422  # Validation error


@pytest.mark.django_db
class TestLoginLockout:
    """Test login lockout functionality."""

    def test_lockout_after_max_attempts(self):
        """Test that account is locked after max failed attempts."""
        email = "locktest@example.com"

        # Record max failed attempts
        for _ in range(LOGIN_MAX_ATTEMPTS):
            record_login_attempt(email, success=False)

        # Check lockout
        is_locked, retry_after = check_login_lockout(email)
        assert is_locked is True
        assert retry_after > 0

    def test_lockout_cleared_on_success(self):
        """Test that lockout is cleared after successful login."""
        email = "cleartest@example.com"

        # Record some failed attempts
        for _ in range(LOGIN_MAX_ATTEMPTS - 1):
            record_login_attempt(email, success=False)

        # Successful login should clear attempts
        record_login_attempt(email, success=True)

        # Should not be locked
        is_locked, _ = check_login_lockout(email)
        assert is_locked is False

    def test_no_lockout_before_max_attempts(self):
        """Test that account is not locked before max attempts."""
        email = "notlocked@example.com"

        # Record fewer than max failed attempts
        for _ in range(LOGIN_MAX_ATTEMPTS - 1):
            record_login_attempt(email, success=False)

        # Should not be locked
        is_locked, _ = check_login_lockout(email)
        assert is_locked is False


@pytest.mark.django_db
class TestTokenBlacklist:
    """Test token blacklist functionality."""

    def test_blacklist_token(self, user):
        """Test blacklisting a token."""
        from ninja_jwt.tokens import AccessToken

        token = AccessToken.for_user(user)
        token_str = str(token)
        jti = token["jti"]

        # Before blacklisting
        assert is_token_blacklisted(jti) is False

        # Blacklist the token
        blacklist_token(token_str)

        # After blacklisting
        assert is_token_blacklisted(jti) is True

    def test_blacklisted_token_rejected(self, api_client, user):
        """Test that blacklisted token is rejected by REST API."""
        from ninja_jwt.tokens import AccessToken

        token = AccessToken.for_user(user)
        token_str = str(token)

        # Token works before blacklisting
        api_client.headers = {"Authorization": f"Bearer {token_str}"}
        response = api_client.get("/auth/me")
        assert response.status_code == 200

        # Blacklist the token
        blacklist_token(token_str)

        # Token should now be rejected
        response = api_client.get("/auth/me")
        assert response.status_code == 401
