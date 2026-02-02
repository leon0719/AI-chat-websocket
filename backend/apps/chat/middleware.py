"""WebSocket authentication middleware."""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from apps.users.auth import get_user_from_token


class JWTAuthMiddleware(BaseMiddleware):
    """JWT authentication middleware for WebSocket connections.

    Supports in-band authentication where the client sends the token
    after establishing the connection, rather than in the query string.
    This is more secure as tokens won't appear in server logs or browser history.

    The consumer is responsible for:
    1. Accepting the connection
    2. Requiring an 'auth' message with the token before any other operations
    3. Closing the connection if authentication fails or times out
    """

    async def __call__(self, scope, receive, send):
        """Allow WebSocket connection and delegate auth to consumer.

        Sets user to None initially; consumer handles in-band authentication.
        """
        scope["user"] = None
        scope["auth_helper"] = self._get_user
        return await super().__call__(scope, receive, send)

    @staticmethod
    @database_sync_to_async
    def _get_user(token: str):
        """Get user from token (sync to async wrapper)."""
        return get_user_from_token(token)
