"""WebSocket authentication middleware."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from apps.core.log_config import logger
from apps.users.auth import get_user_from_token


class JWTAuthMiddleware(BaseMiddleware):
    """JWT authentication middleware for WebSocket connections."""

    async def __call__(self, scope, receive, send):
        """Authenticate WebSocket connection using JWT token from query string.

        Rejects connections without valid authentication at middleware level.
        """
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token = query_params.get("token", [None])[0]

        if not token:
            logger.warning("WebSocket connection rejected: missing token")
            await self._reject_connection(send, 4001)
            return

        user = await self._get_user(token)
        if user is None:
            logger.warning("WebSocket connection rejected: invalid token")
            await self._reject_connection(send, 4001)
            return

        scope["user"] = user
        return await super().__call__(scope, receive, send)

    async def _reject_connection(self, send, code: int):
        """Reject WebSocket connection with specific close code."""
        await send({"type": "websocket.close", "code": code})

    @database_sync_to_async
    def _get_user(self, token: str):
        """Get user from token (sync to async wrapper)."""
        return get_user_from_token(token)
