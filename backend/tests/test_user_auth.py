"""Tests for JWT auth utilities (get_user_from_token, JWTAuth)."""

import pytest
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import AccessToken, RefreshToken

from apps.users.auth import get_user_from_token
from apps.users.jwt_utils import TokenType
from apps.users.services import blacklist_token

User = get_user_model()


@pytest.mark.django_db
class TestGetUserFromToken:
    """Test get_user_from_token() edge cases."""

    def test_valid_access_token(self, user):
        token = AccessToken.for_user(user)
        result = get_user_from_token(str(token))
        assert result is not None
        assert result.id == user.id

    def test_invalid_token(self):
        result = get_user_from_token("invalid.jwt.token")
        assert result is None

    def test_wrong_token_type(self, user):
        """Test that refresh token is rejected when expecting access."""
        refresh = RefreshToken.for_user(user)
        result = get_user_from_token(str(refresh), token_type=TokenType.ACCESS)
        assert result is None

    def test_blacklisted_token(self, user):
        token = AccessToken.for_user(user)
        token_str = str(token)

        blacklist_token(token_str)

        result = get_user_from_token(token_str)
        assert result is None

    def test_nonexistent_user(self, user):
        """Test token with user_id of deleted user."""
        token = AccessToken.for_user(user)
        token_str = str(token)

        user.delete()

        result = get_user_from_token(token_str)
        assert result is None


@pytest.mark.django_db
class TestJWTAuthBlacklist:
    """Test JWTAuth custom authentication with blacklist."""

    def test_blacklisted_token_rejected_via_api(self, api_client, user):
        token = AccessToken.for_user(user)
        token_str = str(token)

        blacklist_token(token_str)

        api_client.headers = {"Authorization": f"Bearer {token_str}"}
        response = api_client.get("/auth/me")
        assert response.status_code == 401

    def test_refresh_token_rejected_for_api(self, api_client, user):
        """Test that refresh token type is rejected for REST API auth."""
        refresh = RefreshToken.for_user(user)
        api_client.headers = {"Authorization": f"Bearer {refresh!s}"}
        response = api_client.get("/auth/me")
        assert response.status_code == 401
