"""Real end-to-end MCP round trip: live uvicorn + real mcp streamable_http client.

No part of the MCP protocol is mocked here - only the GarminClient (upstream
Garmin Connect) is faked, via the mechanism create_mcp_server(client=...)
already supports.
"""

from __future__ import annotations

import asyncio

import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN
from tests.acceptance.fakes import SYNTH_DAILY_SUMMARY, AcceptanceFakeGarminClient
from tests.acceptance.live_app import running_app

_API_KEY = "a" * MIN_MCP_API_KEY_LEN

_EXPECTED_TOOLS = {
    "get_recent_activities",
    "get_activity_detail",
    "get_daily_summary",
    "get_sleep",
    "get_hrv",
    "get_body_battery_and_stress",
    "get_training_readiness_and_status",
    "get_body_composition",
}


@pytest.fixture
def live():
    client = AcceptanceFakeGarminClient()
    with running_app(client, _API_KEY) as server:
        yield server, client


async def _list_tools_over_real_transport(mcp_url: str):
    http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {_API_KEY}"})
    async with streamable_http_client(mcp_url, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            tools_result = await session.list_tools()
            return init_result, tools_result


def test_initialize_and_list_tools_over_real_transport(live) -> None:
    server, _fake = live
    init_result, tools_result = asyncio.run(
        _list_tools_over_real_transport(server.mcp_url)
    )
    assert init_result.server_info.name == "garmin-mcp"

    names = {t.name for t in tools_result.tools}
    assert names == _EXPECTED_TOOLS
    assert len(tools_result.tools) == 8

    for tool in tools_result.tools:
        assert tool.annotations is not None, f"{tool.name} missing annotations"
        assert tool.annotations.read_only_hint is True, (
            f"{tool.name} does not have readOnlyHint=true: {tool.annotations!r}"
        )


async def _call_daily_summary_over_real_transport(mcp_url: str):
    http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {_API_KEY}"})
    async with streamable_http_client(mcp_url, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool("get_daily_summary", {"date": "2026-01-10"})


def test_call_get_daily_summary_real_transport_returns_fake_data(live) -> None:
    server, fake_client = live
    result = asyncio.run(_call_daily_summary_over_real_transport(server.mcp_url))
    assert result.is_error is not True, result
    assert result.structured_content is not None
    assert result.structured_content["date"] == "2026-01-10"
    assert result.structured_content["steps"] == SYNTH_DAILY_SUMMARY["steps"]
    assert "fetch_daily_summary" in fake_client.calls
