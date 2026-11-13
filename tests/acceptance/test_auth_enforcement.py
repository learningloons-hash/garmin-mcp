"""Real-HTTP auth enforcement checks against a live uvicorn instance (M3 review)."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import httpx2
import pytest

from garmin_mcp.mcp_auth import MIN_MCP_API_KEY_LEN
from tests.acceptance.fakes import AcceptanceFakeGarminClient
from tests.acceptance.live_app import running_app

_API_KEY = "a" * MIN_MCP_API_KEY_LEN
_WRONG_KEY = "b" * MIN_MCP_API_KEY_LEN

_METHODS = ["GET", "POST", "DELETE", "OPTIONS", "HEAD"]
_PATHS = ["/mcp", "/mcp/"]


@pytest.fixture(scope="module")
def live():
    client = AcceptanceFakeGarminClient()
    with running_app(client, _API_KEY) as server:
        yield server


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("method", _METHODS)
def test_no_bearer_token_rejected_401(live, method: str, path: str) -> None:
    with httpx2.Client(base_url=live.base_url, timeout=10) as http:
        resp = http.request(method, path)
    assert resp.status_code == 401, (
        f"{method} {path} with no Authorization header returned {resp.status_code}, "
        f"expected 401. Body: {resp.text!r}"
    )


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("method", _METHODS)
def test_wrong_bearer_token_rejected_401(live, method: str, path: str) -> None:
    with httpx2.Client(base_url=live.base_url, timeout=10) as http:
        resp = http.request(
            method, path, headers={"Authorization": f"Bearer {_WRONG_KEY}"}
        )
    assert resp.status_code == 401, (
        f"{method} {path} with wrong bearer token returned {resp.status_code}, "
        f"expected 401. Body: {resp.text!r}"
    )


def test_health_requires_no_auth_and_is_exact(live) -> None:
    with httpx2.Client(base_url=live.base_url, timeout=10) as http:
        resp = http.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.text == '{"status": "ok"}' or resp.text == '{"status":"ok"}', (
        f"/health body had unexpected extra content: {resp.text!r}"
    )


def test_health_rejects_no_write_side_effects_even_with_bad_auth(live) -> None:
    # /health must stay public and unaffected by Authorization headers at all.
    with httpx2.Client(base_url=live.base_url, timeout=10) as http:
        resp = http.get("/health", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


_FAIL_FAST_SCRIPT = textwrap.dedent(
    """
    from garmin_mcp.mcp_auth import require_mcp_api_key_or_exit
    require_mcp_api_key_or_exit()
    print("UNEXPECTED: did not exit")
    """
)


@pytest.mark.parametrize(
    "env_value",
    [None, "", "short-key", "a" * (MIN_MCP_API_KEY_LEN - 1)],
    ids=["unset", "empty", "short-literal", "one-under-minimum"],
)
def test_missing_or_short_api_key_fails_fast_at_startup(env_value: str | None) -> None:
    env = dict(os.environ)
    env.pop("MCP_API_KEY", None)
    if env_value is not None:
        env["MCP_API_KEY"] = env_value

    repo_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src")
    env["PYTHONPATH"] = repo_src

    result = subprocess.run(
        [sys.executable, "-c", _FAIL_FAST_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1, (
        f"Expected exit code 1 for MCP_API_KEY={env_value!r}, "
        f"got {result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "UNEXPECTED" not in result.stdout
    assert "MCP_API_KEY" in result.stderr
