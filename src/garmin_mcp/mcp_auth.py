"""Static bearer-token verification for the MCP HTTP surface."""

from __future__ import annotations

import hmac
import json
import os
import sys
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

MIN_MCP_API_KEY_LEN = 32


def _constant_time_equal(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    # Hash both sides so compare_digest does not leak key length.
    provided_digest = hmac.digest(b"garmin-mcp-api-key", provided.encode(), "sha256")
    expected_digest = hmac.digest(b"garmin-mcp-api-key", expected.encode(), "sha256")
    return hmac.compare_digest(provided_digest, expected_digest)


def load_mcp_api_key() -> str:
    """Load and validate ``MCP_API_KEY`` from the environment."""
    key = os.environ.get("MCP_API_KEY", "").strip()
    if len(key) < MIN_MCP_API_KEY_LEN:
        raise ValueError(
            f"MCP_API_KEY must be set and at least {MIN_MCP_API_KEY_LEN} characters."
        )
    return key


def require_mcp_api_key_or_exit() -> str:
    try:
        return load_mcp_api_key()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


def extract_bearer_token(scope: Scope) -> str | None:
    for key, value in scope.get("headers", ()):
        if key.lower() == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip()
    return None


class BearerApiKeyMiddleware:
    """Require ``Authorization: Bearer <MCP_API_KEY>`` on MCP routes only."""

    def __init__(self, app: ASGIApp, expected_key: str, *, protected_prefix: str = "/mcp") -> None:
        self.app = app
        self._expected_key = expected_key
        self._protected_prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self._protected_prefix):
            token = extract_bearer_token(scope)
            if token is None or not _constant_time_equal(token, self._expected_key):
                await _send_json(send, 401, {"error": "unauthorized"})
                return
        await self.app(scope, receive, send)


async def _send_json(send: Send, status: int, body: dict[str, Any]) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})
