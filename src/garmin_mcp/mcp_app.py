"""MCPServer factory: tools, auth, and HTTP routes."""

from __future__ import annotations

from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from garmin_mcp.garmin_client import GarminClient
from garmin_mcp.mcp_auth import BearerApiKeyMiddleware
from garmin_mcp.mcp_errors import raise_tool_error
from garmin_mcp.mcp_validation import (
    MAX_ACTIVITY_DAYS,
    MAX_ACTIVITY_ID,
    MAX_ACTIVITY_LIMIT,
    MAX_BODY_COMPOSITION_DAYS,
    clamp_int,
    parse_body_composition_range,
    parse_iso_date,
    today_singapore,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True)

_READ_TOOL_NAMES = frozenset(
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


async def _run_sync(fn: Any) -> Any:
    return await anyio.to_thread.run_sync(fn)


def create_mcp_server(*, client: GarminClient) -> MCPServer:
    """Build an MCPServer wired to ``client`` (HTTP auth applied in ``build_http_app``)."""
    mcp = MCPServer(
        "garmin-mcp",
        title="Garmin Connect (read-only)",
        instructions=(
            "Read-only access to the owner's Garmin Connect health and activity data. "
            "All dates are ISO YYYY-MM-DD; omit a date to use today in Asia/Singapore."
        ),
    )

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.tool(
        name="get_recent_activities",
        description=(
            "List recent Garmin activities within a lookback window. "
            "Returns compact JSON: activity_id, name, type, start_time_local, "
            "duration_sec, distance_m, avg_hr_bpm, calories_kcal."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_recent_activities(days: int = 7, limit: int = 20) -> dict[str, Any]:
        days = clamp_int("days", days, low=1, high=MAX_ACTIVITY_DAYS)
        limit = clamp_int("limit", limit, low=1, high=MAX_ACTIVITY_LIMIT)
        try:
            return await _run_sync(lambda: client.fetch_recent_activities(days=days, limit=limit))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_activity_detail",
        description=(
            "Fetch one activity by Garmin activity_id. Includes duration, distance, "
            "pace, heart rate, elevation, and calories where available."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_activity_detail(activity_id: int) -> dict[str, Any]:
        activity_id = clamp_int("activity_id", activity_id, low=1, high=MAX_ACTIVITY_ID)
        try:
            return await _run_sync(lambda: client.fetch_activity_detail(activity_id))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_daily_summary",
        description=(
            "Daily wellness summary for one calendar day: steps, calories_kcal, "
            "resting_hr_bpm."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_daily_summary(date: str | None = None) -> dict[str, Any]:
        day = parse_iso_date("date", date, default=today_singapore())
        try:
            return await _run_sync(lambda: client.fetch_daily_summary(day))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_sleep",
        description=(
            "Sleep session for one night ending on the given calendar date "
            "(duration, stages, sleep_score when available)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_sleep(date: str | None = None) -> dict[str, Any]:
        day = parse_iso_date("date", date, default=today_singapore())
        try:
            return await _run_sync(lambda: client.fetch_sleep(day))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_hrv",
        description="Overnight heart-rate variability (HRV) summary for one date.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_hrv(date: str | None = None) -> dict[str, Any]:
        day = parse_iso_date("date", date, default=today_singapore())
        try:
            return await _run_sync(lambda: client.fetch_hrv(day))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_body_battery_and_stress",
        description=(
            "Body Battery high/low and stress/rest metrics for one calendar day."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_body_battery_and_stress(date: str | None = None) -> dict[str, Any]:
        day = parse_iso_date("date", date, default=today_singapore())
        try:
            return await _run_sync(lambda: client.fetch_body_battery_and_stress(day))
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_training_readiness_and_status",
        description=(
            "Training readiness score, training status, VO2 max, and acute/chronic "
            "load for one date."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_training_readiness_and_status(date: str | None = None) -> dict[str, Any]:
        day = parse_iso_date("date", date, default=today_singapore())
        try:
            return await _run_sync(
                lambda: client.fetch_training_readiness_and_status(day)
            )
        except Exception as exc:
            raise_tool_error(exc)

    @mcp.tool(
        name="get_body_composition",
        description=(
            "Weight and body-composition entries between start_date and end_date "
            f"(inclusive, max {MAX_BODY_COMPOSITION_DAYS}-day span). "
            "Defaults to the last 30 days ending today (Asia/Singapore)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    async def get_body_composition(
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        start, end = parse_body_composition_range(start_date, end_date)
        try:
            return await _run_sync(
                lambda: client.fetch_body_composition(start, end)
            )
        except Exception as exc:
            raise_tool_error(exc)

    registered = {t.name for t in mcp._tool_manager.list_tools()}
    if registered != _READ_TOOL_NAMES:
        missing = _READ_TOOL_NAMES - registered
        extra = registered - _READ_TOOL_NAMES
        raise RuntimeError(f"MCP tool registry mismatch: missing={missing} extra={extra}")

    return mcp


def build_http_app(
    mcp: MCPServer,
    api_key: str,
    *,
    transport_host: str = "0.0.0.0",
    host: str | None = None,
):
    """Starlette ASGI app: ``/health`` public, ``/mcp`` bearer-protected.

    ``transport_host`` is passed to the MCP SDK for DNS-rebinding protection only.
    Use ``0.0.0.0`` behind Railway (the proxy rewrites ``Host``). Uvicorn bind
    address is separate (see ``server.main`` / ``HOST`` env). Deprecated alias:
    ``host=`` sets ``transport_host``.
    """
    if host is not None:
        transport_host = host
    base = mcp.streamable_http_app(streamable_http_path="/mcp", host=transport_host)
    return BearerApiKeyMiddleware(base, api_key)
