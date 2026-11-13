"""Railway rewrites Host to the public domain; the app must not 421 on that."""

from __future__ import annotations

import httpx2
import pytest

from garmin_mcp.mcp_app import build_http_app, create_mcp_server
from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN
from tests.acceptance.fakes import AcceptanceFakeGarminClient
from tests.acceptance.live_app import LiveServer

_API_KEY = "a" * MIN_MCP_API_KEY_LEN


@pytest.fixture
def live_default_host():
    """App built the way server.build_app() does by default: HOST unset -> '0.0.0.0'."""
    client = AcceptanceFakeGarminClient()
    mcp = create_mcp_server(client=client)
    app = build_http_app(mcp, _API_KEY, host="0.0.0.0")
    server = LiveServer(app)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def test_railway_rewritten_host_header_not_rejected_421(live_default_host) -> None:
    with httpx2.Client(base_url=live_default_host.base_url, timeout=10) as http:
        resp = http.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Host": "garmin-mcp-production.up.railway.app",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert resp.status_code != 421, (
        f"Railway-style rewritten Host header was rejected: "
        f"{resp.status_code} {resp.text!r}"
    )


def test_health_also_unaffected_by_railway_host_header(live_default_host) -> None:
    with httpx2.Client(base_url=live_default_host.base_url, timeout=10) as http:
        resp = http.get(
            "/health", headers={"Host": "garmin-mcp-production.up.railway.app"}
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_arbitrary_host_header_also_accepted_dns_rebinding_protection_is_off(
    live_default_host,
) -> None:
    """Documents that with HOST=0.0.0.0 (the Railway default), the MCP SDK's
    DNS-rebinding Host/Origin validation is NOT engaged (it only auto-enables
    when host is 127.0.0.1/localhost/::1). This is required for Railway (its
    proxy always rewrites Host), but it does mean the app accepts literally
    any Host header - Host is not a security boundary here. Auth is enforced
    separately by BearerApiKeyMiddleware regardless of Host, so this is not a
    bypass of authentication, just an absence of an additional defense layer.
    """
    with httpx2.Client(base_url=live_default_host.base_url, timeout=10) as http:
        resp = http.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {_API_KEY}",
                "Host": "totally-unrelated-evil-host.example",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
    assert resp.status_code != 421
