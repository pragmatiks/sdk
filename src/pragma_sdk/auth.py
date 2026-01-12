"""Authentication for Pragma API."""

from __future__ import annotations

import httpx


class BearerAuth(httpx.Auth):
    """Add bearer token authentication to API requests.

    Args:
        token: JWT or bearer token for authentication.

    Raises:
        ValueError: If token is empty.

    Example:
        >>> from pragma_sdk import PragmaClient, BearerAuth
        >>> auth = BearerAuth(token="sk_test_...")
        >>> client = PragmaClient(auth=auth)
    """

    def __init__(self, token: str):
        """Validate and store the bearer token.

        Raises:
            ValueError: If token is empty.
        """
        if not token:
            raise ValueError("Bearer token cannot be empty")
        self.token = token

    def auth_flow(self, request: httpx.Request):
        """Add Authorization header to the request.

        Yields:
            The request with Authorization header set.
        """
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request

    async def async_auth_flow(self, request: httpx.Request):
        """Add Authorization header to the request (async variant).

        Yields:
            The request with Authorization header set.
        """
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request
