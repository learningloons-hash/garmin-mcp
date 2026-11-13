from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from mcp.client import Client
from starlette.testclient import TestClient

from garmin_mcp.config import GarminSettings
from garmin_mcp.errors import AuthFailureError
from garmin_mcp.garmin_client import GarminClient
from garmin_mcp.mcp_app import build_http_app, create_mcp_server
from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN, load_mcp_api_key, require_mcp_api_key_or_exit
from tests.fixtures.synthetic_garmin import (
    SYNTH_ACTIVITY,
    SYNTH_SLEEP,
    SYNTH_SUMMARY,
)

_TEST_API_KEY = "a" * MIN_MCP_API_KEY_LEN
_WRONG_API_KEY = "b" * MIN_MCP_API_KEY_LEN

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


class FakeMcpGarminClient:
    """Minimal stand-in for GarminClient fetch API (read-only surface)."""

    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    def fetch_recent_activities(self, *, days: int = 7, limit: int = 20) -> dict[str, Any]:
        self.calls.append("fetch_recent_activities")
        return {"activities": [SYNTH_ACTIVITY], "days": days, "limit": limit}

    def fetch_activity_detail(self, activity_id: int | str) -> dict[str, Any]:
        self.calls.append("fetch_activity_detail")
        return dict(SYNTH_ACTIVITY, activity_id=int(activity_id))

    def fetch_daily_summary(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_daily_summary")
        return {"date": cdate, **{k: SYNTH_SUMMARY.get(k) for k in ("steps",)}}

    def fetch_sleep(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_sleep")
        return {"date": cdate, "duration_asleep_sec": SYNTH_SLEEP.get("sleepTimeSeconds")}

    def fetch_hrv(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_hrv")
        return {"date": cdate, "overnight_hrv_ms": 50}

    def fetch_body_battery_and_stress(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_body_battery_and_stress")
        return {"date": cdate, "body_battery_high": 90}

    def fetch_training_readiness_and_status(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_training_readiness_and_status")
        return {"date": cdate, "training_readiness_score": 80}

    def fetch_body_composition(self, start_date: str, end_date: str) -> dict[str, Any]:
        self.calls.append("fetch_body_composition")
        return {"entries": [], "start_date": start_date, "end_date": end_date}


@pytest.fixture
def fake_client() -> FakeMcpGarminClient:
    return FakeMcpGarminClient()


@pytest.fixture
def mcp_server(fake_client: FakeMcpGarminClient):
    return create_mcp_server(client=fake_client)  # type: ignore[arg-type]


@pytest.fixture
def http_app(mcp_server):
    return build_http_app(mcp_server, _TEST_API_KEY, host="127.0.0.1")


def test_mcp_api_key_length_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_API_KEY", "too-short")
    with pytest.raises(ValueError):
        load_mcp_api_key()
    with pytest.raises(SystemExit):
        require_mcp_api_key_or_exit()


def test_health_unauthenticated(http_app) -> None:
    with TestClient(http_app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_mcp_requires_bearer(http_app) -> None:
    with TestClient(http_app) as client:
        no_auth = client.post("/mcp")
        bad_auth = client.post("/mcp", headers={"Authorization": f"Bearer {_WRONG_API_KEY}"})
    assert no_auth.status_code == 401
    assert bad_auth.status_code == 401


def test_mcp_accepts_bearer_header(http_app) -> None:
    with TestClient(http_app) as client:
        resp = client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {_TEST_API_KEY}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert resp.status_code != 401


def test_tools_are_read_only(mcp_server) -> None:
    tools = asyncio.run(mcp_server.list_tools())
    names = {t.name for t in tools}
    assert names == _EXPECTED_TOOLS
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True


def test_no_write_surface_on_fake_client(fake_client: FakeMcpGarminClient) -> None:
    read_methods = {m for m in dir(fake_client) if m.startswith("fetch_")}
    assert read_methods == {
        "fetch_activity_detail",
        "fetch_body_battery_and_stress",
        "fetch_body_composition",
        "fetch_daily_summary",
        "fetch_hrv",
        "fetch_recent_activities",
        "fetch_sleep",
        "fetch_training_readiness_and_status",
    }


async def _call_tool(mcp_server, name: str, arguments: dict[str, Any] | None = None):
    async with Client(mcp_server) as client:
        return await client.call_tool(name, arguments or {})


def _tool_error_text(result) -> str:
    assert result.is_error is True
    return " ".join(c.text for c in result.content if hasattr(c, "text") and c.text)


def test_get_daily_summary_round_trip(mcp_server, fake_client: FakeMcpGarminClient) -> None:
    result = asyncio.run(_call_tool(mcp_server, "get_daily_summary", {"date": "2026-01-10"}))
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["date"] == "2026-01-10"
    assert "fetch_daily_summary" in fake_client.calls


def test_get_recent_activities_validation(mcp_server) -> None:
    bad_days = asyncio.run(_call_tool(mcp_server, "get_recent_activities", {"days": 0}))
    bad_limit = asyncio.run(_call_tool(mcp_server, "get_recent_activities", {"limit": 100}))
    assert "days" in _tool_error_text(bad_days).lower()
    assert "limit" in _tool_error_text(bad_limit).lower()


def test_invalid_date_rejected(mcp_server) -> None:
    result = asyncio.run(_call_tool(mcp_server, "get_sleep", {"date": "not-a-date"}))
    assert "yyyy-mm-dd" in _tool_error_text(result).lower()


def test_auth_failure_maps_to_safe_message() -> None:
    class FailingClient(FakeMcpGarminClient):
        def fetch_daily_summary(self, cdate: str) -> dict[str, Any]:
            raise AuthFailureError(
                "secret-upstream-token",
                cause=Exception("password=leaked"),
            )

    server = create_mcp_server(client=FailingClient())  # type: ignore[arg-type]
    result = asyncio.run(_call_tool(server, "get_daily_summary", {"date": "2026-01-10"}))
    msg = _tool_error_text(result).lower()
    assert "garmin_email" in msg
    assert "secret-upstream" not in msg
    assert "leaked" not in msg


def test_get_activity_detail_rejects_huge_id(mcp_server) -> None:
    huge = 10**13 + 1
    result = asyncio.run(_call_tool(mcp_server, "get_activity_detail", {"activity_id": huge}))
    assert "activity_id" in _tool_error_text(result).lower()


def test_get_activity_detail_positive_id(mcp_server, fake_client: FakeMcpGarminClient) -> None:
    result = asyncio.run(_call_tool(mcp_server, "get_activity_detail", {"activity_id": 42}))
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["activity_id"] == 42


def test_body_composition_range_cap(mcp_server) -> None:
    result = asyncio.run(
        _call_tool(
            mcp_server,
            "get_body_composition",
            {"start_date": "2020-01-01", "end_date": "2026-01-01"},
        )
    )
    assert "90" in _tool_error_text(result)


def test_real_garmin_client_still_constructible(tmp_path: Path) -> None:
    settings = GarminSettings(
        email="u@example.com",
        password="pw",
        token_dir=tmp_path / "garth",
    )
    client = GarminClient(settings, api_factory=lambda e, p: MagicMock())
    server = create_mcp_server(client=client)
    tools = asyncio.run(server.list_tools())
    assert len(tools) == 8
