"""Tests for SDK authentication classes."""

from __future__ import annotations

import httpx
import pytest

from pragma_sdk.auth import BearerAuth


def test_bearer_auth_adds_authorization_header() -> None:
    """BearerAuth adds Authorization header to requests."""
    auth = BearerAuth(token="test_token")
    request = httpx.Request("GET", "https://api.example.com/test")

    flow = auth.auth_flow(request)
    authenticated_request = next(flow)

    assert authenticated_request.headers["Authorization"] == "Bearer test_token"


def test_bearer_auth_rejects_empty_token() -> None:
    """BearerAuth raises ValueError for empty token."""
    with pytest.raises(ValueError, match="Bearer token cannot be empty"):
        BearerAuth(token="")


async def test_bearer_auth_async_adds_authorization_header() -> None:
    """BearerAuth adds Authorization header to async requests."""
    auth = BearerAuth(token="test_token")
    request = httpx.Request("GET", "https://api.example.com/test")

    flow = auth.async_auth_flow(request)
    authenticated_request = await flow.__anext__()

    assert authenticated_request.headers["Authorization"] == "Bearer test_token"
