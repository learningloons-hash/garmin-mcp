"""Map internal Garmin errors to MCP tool-facing messages."""

from __future__ import annotations

from typing import NoReturn

from mcp.server.mcpserver.exceptions import ToolError

from garmin_mcp.errors import (
    AuthFailureError,
    GarminMcpError,
    MfaRequiredError,
    RateLimitedError,
    map_library_exception,
    public_message,
)


def safe_tool_message(exc: GarminMcpError) -> str:
    """User- and model-safe tool error text (no upstream secrets)."""
    if isinstance(exc, AuthFailureError):
        return (
            "Garmin authentication failed. On Railway, verify GARMIN_EMAIL and "
            "GARMIN_PASSWORD are correct and GARMINTOKENS contains valid token files."
        )
    if isinstance(exc, MfaRequiredError):
        return public_message(exc)
    if isinstance(exc, RateLimitedError):
        return "Garmin rate limit exceeded. Try again in a few minutes."
    return public_message(exc)


def raise_tool_error(exc: BaseException) -> NoReturn:
    if isinstance(exc, ToolError):
        raise exc
    if isinstance(exc, GarminMcpError):
        raise ToolError(safe_tool_message(exc)) from exc
    mapped = map_library_exception(exc)
    raise ToolError(safe_tool_message(mapped)) from exc
