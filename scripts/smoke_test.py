#!/usr/bin/env python3
"""Post-deploy smoke test (real HTTP; requires MCP_URL + MCP_API_KEY)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from garmin_mcp.deploy_config import (
    EXPECTED_MCP_TOOL_NAMES,
    HEALTH_PATH,
    MCP_HTTP_PATH,
    normalize_mcp_url,
)

_SINGAPORE = ZoneInfo("Asia/Singapore")


def _service_base_url(mcp_url: str) -> str:
    url = mcp_url.rstrip("/")
    if url.endswith(MCP_HTTP_PATH):
        return url[: -len(MCP_HTTP_PATH)]
    return url


def _yesterday_singapore() -> str:
    return (datetime.now(_SINGAPORE).date() - timedelta(days=1)).isoformat()


async def _run_smoke(mcp_url: str, api_key: str) -> int:
    base = _service_base_url(mcp_url)
    health_url = f"{base.rstrip('/')}{HEALTH_PATH}"

    async with httpx2.AsyncClient(timeout=30.0) as anon:
        health = await anon.get(health_url)
        if health.status_code != 200 or health.json().get("status") != "ok":
            print(f"FAIL health check: {health.status_code}", file=sys.stderr)
            return 1
        unauth = await anon.post(mcp_url)
        if unauth.status_code != 401:
            print(
                f"FAIL expected 401 on unauthenticated /mcp, got {unauth.status_code}",
                file=sys.stderr,
            )
            return 1

    headers = {"Authorization": f"Bearer {api_key}"}
    http_client = httpx2.AsyncClient(headers=headers, timeout=60.0)
    async with streamable_http_client(mcp_url, http_client=http_client) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            if names != EXPECTED_MCP_TOOL_NAMES:
                print(f"FAIL tool list mismatch: {sorted(names)}", file=sys.stderr)
                return 1

            day = _yesterday_singapore()
            result = await session.call_tool("get_daily_summary", {"date": day})
            if result.is_error:
                text = " ".join(getattr(c, "text", "") for c in result.content)
                print(f"FAIL get_daily_summary: {text}", file=sys.stderr)
                return 1

            payload = result.structured_content or {}
            keys = sorted(payload.keys())
            print(
                f"OK health; {len(tools.tools)} tools; "
                f"get_daily_summary({day}) fields: {keys}"
            )
            return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a deployed garmin-mcp instance.")
    parser.add_argument(
        "--url",
        default=os.environ.get("MCP_URL", "").strip(),
        help="Service base URL or full /mcp URL (or set MCP_URL)",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("MCP_API_KEY", "").strip()
    if not args.url:
        print("MCP_URL or --url is required", file=sys.stderr)
        return 2
    if not api_key:
        print("MCP_API_KEY is required", file=sys.stderr)
        return 2

    mcp_url = normalize_mcp_url(args.url)
    return asyncio.run(_run_smoke(mcp_url, api_key))


if __name__ == "__main__":
    raise SystemExit(main())
