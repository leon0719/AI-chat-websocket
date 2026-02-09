"""Tests for custom middleware."""

from unittest.mock import MagicMock

from django.test import RequestFactory, override_settings

from apps.core.middleware import ContentSecurityPolicyMiddleware, RequestContextMiddleware


class TestContentSecurityPolicyMiddleware:
    """Test CSP middleware."""

    def _make_middleware(self):
        mock_response = MagicMock()
        mock_response.__setitem__ = MagicMock()
        mock_response.__getitem__ = MagicMock()

        def get_response(request):
            return mock_response

        middleware = ContentSecurityPolicyMiddleware(get_response)
        return middleware, mock_response

    @override_settings(DEBUG=False)
    def test_adds_csp_header_when_not_debug(self):
        middleware, mock_response = self._make_middleware()
        request = RequestFactory().get("/")

        middleware(request)

        mock_response.__setitem__.assert_called_with(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )

    @override_settings(DEBUG=True)
    def test_no_csp_header_when_debug(self):
        middleware, mock_response = self._make_middleware()
        request = RequestFactory().get("/")

        middleware(request)

        for call in mock_response.__setitem__.call_args_list:
            assert call[0][0] != "Content-Security-Policy"


class TestRequestContextMiddleware:
    """Test request context middleware."""

    def _make_middleware(self):
        response = MagicMock()
        response_headers = {}
        response.__setitem__ = lambda self, k, v: response_headers.__setitem__(k, v)
        response.__getitem__ = lambda self, k: response_headers[k]

        def get_response(request):
            return response

        middleware = RequestContextMiddleware(get_response)
        return middleware, response, response_headers

    def test_generates_request_id(self):
        middleware, response, headers = self._make_middleware()
        request = RequestFactory().get("/")

        middleware(request)

        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) == 8

    def test_uses_provided_request_id(self):
        middleware, response, headers = self._make_middleware()
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="custom-id-123")

        middleware(request)

        assert headers["X-Request-ID"] == "custom-id-123"

    def test_sets_user_context_for_authenticated_user(self):
        middleware, response, headers = self._make_middleware()
        request = RequestFactory().get("/")
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.id = "test-user-uuid"
        request.user = mock_user

        middleware(request)

        assert "X-Request-ID" in headers

    def test_sets_anonymous_user_context(self):
        middleware, response, headers = self._make_middleware()
        request = RequestFactory().get("/")

        middleware(request)

        assert "X-Request-ID" in headers
