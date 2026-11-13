"""Deployment constants for Railway / Docker (no secrets)."""

from __future__ import annotations

DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_MCP_TRANSPORT_HOST = "0.0.0.0"
HEALTH_PATH = "/health"
MCP_HTTP_PATH = "/mcp"
RAILWAY_TOKEN_MOUNT = "/data"
RAILWAY_TOKEN_DIR = f"{RAILWAY_TOKEN_MOUNT}/garth"

EXPECTED_MCP_TOOL_NAMES = frozenset(
    {
        "get_recent_activities",
        "get_activity_detail",
        "get_daily_summary",
        "get_sleep",
        "get_hrv",
        "get_body_battery_and_stress",
        "get_training_readiness_and_status",
        "get_body_composition",
    }
)


def normalize_mcp_url(base: str) -> str:
    """Return the Streamable HTTP MCP endpoint URL from a service base URL."""
    text = base.strip().rstrip("/")
    if text.endswith(MCP_HTTP_PATH):
        return text
    return f"{text}{MCP_HTTP_PATH}"
