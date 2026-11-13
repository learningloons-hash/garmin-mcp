"""Edge/bad inputs must produce clean structured tool errors, never 500s or crashes."""

from __future__ import annotations

import asyncio

import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN
from tests.acceptance.fakes import AcceptanceFakeGarminClient
from tests.acceptance.live_app import running_app

_API_KEY = "a" * MIN_MCP_API_KEY_LEN


@pytest.fixture
def live():
    client = AcceptanceFakeGarminClient()
    with running_app(client, _API_KEY) as server:
        yield server, client


async def _call(mcp_url: str, name: str, arguments: dict):
    http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {_API_KEY}"})
    async with streamable_http_client(mcp_url, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


def _text(result) -> str:
    return " ".join(getattr(c, "text", "") for c in result.content)


@pytest.mark.parametrize("days", [91, 1000, -1, 0])
def test_days_over_cap_is_structured_error_not_crash(live, days: int) -> None:
    server, _fake = live
    result = asyncio.run(
        _call(server.mcp_url, "get_recent_activities", {"days": days})
    )
    assert result.is_error is True
    assert "days" in _text(result).lower()


@pytest.mark.parametrize("limit", [51, 1000, -5, 0])
def test_limit_over_cap_is_structured_error_not_crash(live, limit: int) -> None:
    server, _fake = live
    result = asyncio.run(
        _call(server.mcp_url, "get_recent_activities", {"limit": limit})
    )
    assert result.is_error is True
    assert "limit" in _text(result).lower()


@pytest.mark.parametrize(
    "bad_date",
    [
        "not-a-date",
        "2026-13-40",
        "2026/11/12",
        "12-11-2026",
        "",
        "2026-02-30",
        "' OR 1=1 --",
        "2026-11-12T00:00:00",
    ],
)
def test_malformed_date_is_structured_error_not_crash(live, bad_date: str) -> None:
    server, _fake = live
    result = asyncio.run(_call(server.mcp_url, "get_sleep", {"date": bad_date}))
    assert result.is_error is True, f"date={bad_date!r} did not produce a tool error"
    text = _text(result).lower()
    assert "yyyy-mm-dd" in text or "date" in text


@pytest.mark.parametrize(
    "activity_id",
    [0, -1, -999999999999999999999999999999, 99999999999999999999999999999999999999],
)
def test_bad_activity_id_is_structured_error_not_crash(live, activity_id) -> None:
    server, _fake = live
    result = asyncio.run(
        _call(server.mcp_url, "get_activity_detail", {"activity_id": activity_id})
    )
    assert result.is_error is True, f"activity_id={activity_id!r} did not error cleanly"


def test_malformed_activity_id_type_is_structured_error_not_crash(live) -> None:
    server, _fake = live
    result = asyncio.run(
        _call(
            server.mcp_url,
            "get_activity_detail",
            {"activity_id": "not-a-number-at-all"},
        )
    )
    assert result.is_error is True, (
        f"non-numeric activity_id did not error cleanly: {result!r}"
    )
