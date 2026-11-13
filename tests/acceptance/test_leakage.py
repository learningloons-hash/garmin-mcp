"""Confirm synthetic secrets + a real traceback never reach the client or app logs.

Uses obviously-fake placeholder values only (never real-looking secrets).
"""

from __future__ import annotations

import asyncio
import logging

import httpx2
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN
from tests.acceptance.fakes import (
    LEAK_BEARER,
    LEAK_EMAIL,
    LEAK_PASSWORD,
    LeakyFakeGarminClient,
)
from tests.acceptance.live_app import running_app

_API_KEY = "a" * MIN_MCP_API_KEY_LEN
_SECRETS = (LEAK_EMAIL, LEAK_PASSWORD, LEAK_BEARER, "FAKE.JWT.TOKEN")


@pytest.fixture
def live():
    client = LeakyFakeGarminClient()
    with running_app(client, _API_KEY) as server:
        yield server, client


async def _call_daily_summary(mcp_url: str):
    http_client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {_API_KEY}"})
    async with streamable_http_client(mcp_url, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool("get_daily_summary", {"date": "2026-01-10"})


def test_tool_error_result_does_not_contain_secrets(live, caplog) -> None:
    server, _fake = live
    caplog.set_level(logging.DEBUG)

    result = asyncio.run(_call_daily_summary(server.mcp_url))

    assert result.is_error is True, (
        f"expected tool call to surface as an error result, got: {result!r}"
    )
    returned_text = " ".join(
        getattr(c, "text", "") for c in result.content
    )
    for secret in _SECRETS:
        assert secret not in returned_text, (
            f"secret {secret!r} leaked into tool result: {returned_text!r}"
        )


def test_no_log_line_contains_secrets_or_full_traceback(live, caplog) -> None:
    server, _fake = live
    caplog.set_level(logging.DEBUG)

    asyncio.run(_call_daily_summary(server.mcp_url))

    full_log_text = caplog.text
    leaked = [secret for secret in _SECRETS if secret in full_log_text]
    assert not leaked, (
        f"secrets leaked into app logs: {leaked!r}\n--- captured log ---\n{full_log_text}"
    )
