"""Input validation helpers for MCP tools."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.mcpserver.exceptions import ToolError

SINGAPORE = ZoneInfo("Asia/Singapore")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_ACTIVITY_DAYS = 90
MAX_ACTIVITY_LIMIT = 50
MAX_BODY_COMPOSITION_DAYS = 90


def today_singapore() -> str:
    return datetime.now(SINGAPORE).date().isoformat()


def parse_iso_date(name: str, value: str | None, *, default: str | None = None) -> str:
    candidate = (value if value is not None else default)
    if candidate is None:
        raise ToolError(f"Missing required date field {name!r}.")
    text = candidate.strip()
    if not ISO_DATE.match(text):
        raise ToolError(f"Invalid {name}: use YYYY-MM-DD (got {text!r}).")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ToolError(f"Invalid {name}: {text!r} is not a calendar date.") from exc
    return text


def clamp_int(name: str, value: int, *, low: int, high: int) -> int:
    if value < low or value > high:
        raise ToolError(f"{name} must be between {low} and {high} (got {value}).")
    return value


def parse_body_composition_range(start_date: str | None, end_date: str | None) -> tuple[str, str]:
    end = parse_iso_date("end_date", end_date, default=today_singapore())
    start = parse_iso_date(
        "start_date",
        start_date,
        default=(date.fromisoformat(end) - timedelta(days=29)).isoformat(),
    )
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    if start_d > end_d:
        raise ToolError("start_date must be on or before end_date.")
    if (end_d - start_d).days > MAX_BODY_COMPOSITION_DAYS:
        raise ToolError(
            f"Date range too wide: at most {MAX_BODY_COMPOSITION_DAYS} days between "
            "start_date and end_date."
        )
    return start, end
