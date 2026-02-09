"""Tests for authentication endpoints."""

import pytest
from django.core.cache import cache
from django.test import Client

from apps.users.services import blacklist_token, is_token_blacklisted
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


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
                "password": "NewPassword123!",  # Meets complexity: upper, lower, digit, special
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
                "password": "Password12345!",  # Meets complexity: upper, lower, digit, special
            },
        )
        assert response.status_code == 400

    def test_login_success(self, api_client, user):
        """Test successful login via token/pair endpoint."""
        response = api_client.post(
            "/auth/token/pair",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.json()}"
        )
        data = response.json()
        assert "access" in data
        # refresh token is now in HttpOnly cookie, not in response body
        assert "refresh_token" in response.cookies

    def test_login_invalid_credentials(self, api_client, user):
        """Test login with invalid credentials."""
        response = api_client.post(
            "/auth/token/pair",
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
        """Test token refresh using HttpOnly cookie."""
        # First login to get refresh token in cookie
        login_response = api_client.post(
            "/auth/token/pair",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )
        assert login_response.status_code == 200
        refresh_token_morsel = login_response.cookies.get("refresh_token")
        assert refresh_token_morsel is not None
        # Extract actual value from Morsel object
        refresh_token_value = refresh_token_morsel.value

        # Then refresh the token with cookie
        refresh_response = api_client.post(
            "/auth/token/refresh",
            COOKIES={"refresh_token": refresh_token_value},
        )
        assert refresh_response.status_code == 200, (
            f"Expected 200, got {refresh_response.status_code}: {refresh_response.json()}"
        )
        assert "access" in refresh_response.json()
        # Token rotation: new refresh token should be set in cookie
        assert "refresh_token" in refresh_response.cookies

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
                "password": "Short12!",  # Only 8 chars (meets complexity but too short)
            },
        )
        assert response.status_code == 422  # Validation error

    def test_password_complexity_missing_uppercase(self, api_client):
        """Test password complexity requires uppercase letter."""
        response = api_client.post(
            "/auth/register",
            json={
                "email": "weak@example.com",
                "username": "weakpass",
                "password": "password1234!",  # Missing uppercase
            },
        )
        assert response.status_code == 422

    def test_password_complexity_missing_special(self, api_client):
        """Test password complexity requires special character."""
        response = api_client.post(
            "/auth/register",
            json={
                "email": "weak@example.com",
                "username": "weakpass",
                "password": "Password12345",  # Missing special char
            },
        )
        assert response.status_code == 422


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


@pytest.mark.django_db
class TestTokenRefreshEdgeCases:
    """Test token refresh endpoint edge cases."""

    def test_refresh_no_cookie(self, user):
        """Test refresh with no refresh token cookie."""
        client = Client()
        response = client.post("/api/auth/token/refresh")
        assert response.status_code == 401

    def test_refresh_invalid_token(self, user):
        """Test refresh with invalid token in cookie."""
        client = Client()
        client.cookies["refresh_token"] = "invalid.token.here"
        response = client.post("/api/auth/token/refresh")
        assert response.status_code == 401

    def test_refresh_with_access_token_type(self, user):
        """Test refresh rejects access token (wrong type)."""
        from ninja_jwt.tokens import AccessToken

        access_token = AccessToken.for_user(user)
        client = Client()
        client.cookies["refresh_token"] = str(access_token)
        response = client.post("/api/auth/token/refresh")
        assert response.status_code == 401

    def test_refresh_blacklisted_token(self, user):
        """Test refresh rejects blacklisted refresh token."""
        from ninja_jwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        refresh_str = str(refresh)

        blacklist_token(refresh_str)

        client = Client()
        client.cookies["refresh_token"] = refresh_str
        response = client.post("/api/auth/token/refresh")
        assert response.status_code == 401


@pytest.mark.django_db
class TestLogoutEdgeCases:
    """Test logout endpoint edge cases."""

    def test_logout_with_cookie_refresh_token(self, user):
        """Test that logout blacklists refresh token from cookie."""
        from ninja_jwt.tokens import AccessToken, RefreshToken

        access = AccessToken.for_user(user)
        refresh = RefreshToken.for_user(user)
        refresh_str = str(refresh)

        client = Client()
        client.cookies["refresh_token"] = refresh_str
        response = client.post(
            "/api/auth/logout",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access!s}",
        )
        assert response.status_code == 200

    def test_logout_with_body_refresh_token(self, api_client, user):
        """Test that logout blacklists refresh token from body."""
        from ninja_jwt.tokens import AccessToken, RefreshToken

        access = AccessToken.for_user(user)
        refresh = RefreshToken.for_user(user)

        api_client.headers = {"Authorization": f"Bearer {access!s}"}
        response = api_client.post(
            "/auth/logout",
            json={"refresh_token": str(refresh)},
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestBlacklistTokenEdgeCases:
    """Test blacklist_token edge cases."""

    def test_blacklist_invalid_token(self):
        """Test blacklisting an invalid token does not raise."""
        blacklist_token("not.a.valid.jwt.token")

    def test_blacklist_token_no_jti(self):
        """Test blacklisting a token without jti claim."""
        import time

        import jwt
        from django.conf import settings

        from config.settings.base import settings as app_settings

        token = jwt.encode(
            {"user_id": "123", "exp": time.time() + 3600},
            str(settings.NINJA_JWT["SIGNING_KEY"]),
            algorithm=app_settings.JWT_ALGORITHM,
        )
        blacklist_token(token)
