from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

from garmin_mcp.config import GarminSettings
from garmin_mcp.errors import AuthFailureError, MfaRequiredError, RateLimitedError
from garmin_mcp.garmin_client import GarminClient, get_garmin_client, reset_garmin_client
from tests.fixtures.synthetic_garmin import (
    SYNTH_ACTIVITY,
    SYNTH_BATTERY,
    SYNTH_DAILY_STATUS,
    SYNTH_HRV,
    SYNTH_READINESS,
    SYNTH_SLEEP,
    SYNTH_STRESS,
    SYNTH_SUMMARY,
    SYNTH_TRAINING_STATUS,
    SYNTH_WEIGHT,
)


class FakeGarmin:
    def __init__(self, email: str, password: str) -> None:
        self.username = email
        self.password = password
        self.return_on_mfa = False
        self.prompt_mfa = None
        self.client = MagicMock()
        self._login_calls = 0

    def login(self, tokenstore: str | None = None) -> tuple[str | None, Any]:
        self._login_calls += 1
        if self._login_calls == 1 and getattr(self, "fail_first_login", False):
            raise GarminConnectAuthenticationError(
                "Cached tokens were rejected by the API; discarding"
            )
        if getattr(self, "mfa_on_login", False):
            return "needs_mfa", {"flow": "widget"}
        self.client.dump(tokenstore)
        return None, None

    def get_activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]:
        return [SYNTH_ACTIVITY]

    def get_activity(self, activity_id: str) -> dict[str, Any]:
        return dict(SYNTH_ACTIVITY, activityId=int(activity_id))

    def get_user_summary(self, cdate: str) -> dict[str, Any]:
        return dict(SYNTH_SUMMARY)

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        return SYNTH_SLEEP

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        return SYNTH_HRV

    def get_body_battery(self, start: str, end: str) -> list[dict[str, Any]]:
        return SYNTH_BATTERY

    def get_stress_data(self, cdate: str) -> dict[str, Any]:
        return SYNTH_STRESS

    def get_morning_training_readiness(self, cdate: str) -> dict[str, Any] | None:
        return SYNTH_READINESS

    def get_daily_training_status(self, cdate: str) -> dict[str, Any]:
        return SYNTH_DAILY_STATUS

    def get_training_status(self, cdate: str) -> dict[str, Any]:
        return SYNTH_TRAINING_STATUS

    def get_weigh_ins(self, start: str, end: str) -> dict[str, Any]:
        return SYNTH_WEIGHT


@pytest.fixture
def token_dir(tmp_path: Path) -> Path:
    return tmp_path / "garth"


@pytest.fixture
def client(token_dir: Path) -> GarminClient:
    settings = GarminSettings(
        email="user@example.com",
        password="not-a-real-password",
        token_dir=token_dir,
    )
    return GarminClient(settings, api_factory=FakeGarmin)


def test_login_persists_tokens(client: GarminClient, token_dir: Path) -> None:
    client.ensure_session()
    client._api.client.dump.assert_called_with(str(token_dir))


REAL_BAD_CREDENTIALS_MESSAGE = (
    "Authentication failed (401 Unauthorized). "
    "Possible causes:\n"
    "  • Incorrect email or password\n"
    "  • Account locked — check https://sso.garmin.com\n"
    "  • Garmin SSO service is temporarily unavailable\n"
    "Original error: 401 Client Error: Unauthorized for url: https://example.invalid"
)


def _real_client(token_dir: Path) -> GarminClient:
    settings = GarminSettings(
        email="user@example.com",
        password="not-a-real-password",
        token_dir=token_dir,
    )
    return GarminClient(settings)


def test_mfa_raises_bootstrap_hint_via_library_exception(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production sets return_on_mfa=False; garminconnect raises on MFA."""
    client = _real_client(token_dir)

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        assert return_on_mfa is False
        assert prompt_mfa is None
        raise GarminConnectAuthenticationError(
            "MFA Required but no prompt_mfa mechanism supplied"
        )

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)
    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(MfaRequiredError) as err:
            client.ensure_session()
    assert "bootstrap" in str(err.value).lower()
    assert "garmin_mcp.bootstrap" in str(err.value)


def test_bad_credentials_detected_stops_retry_storm(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _real_client(token_dir)
    call_count = {"n": 0}

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        call_count["n"] += 1
        raise GarminConnectAuthenticationError(REAL_BAD_CREDENTIALS_MESSAGE)

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)
    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()
    assert call_count["n"] == 1
    assert client._bad_credentials is True

    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()
    assert call_count["n"] == 1


def test_ambiguous_auth_failure_preserves_type_after_retries(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _real_client(token_dir)

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        raise GarminConnectAuthenticationError(
            "401 Unauthorized: session token rejected by API tier"
        )

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)
    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()


def test_default_api_factory_builds_library_garmin_without_network(
    token_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _real_client(token_dir)

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        assert return_on_mfa is False
        return None, None

    def fake_load_profile(self) -> None:
        self.display_name = email if (email := self.username) else "user"

    monkeypatch.setattr(Garmin, "_load_profile_and_settings", fake_load_profile)
    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        api = client.ensure_session()
    assert api.username == client._settings.email
    assert client._api is api


def test_fetch_recent_activities(client: GarminClient) -> None:
    client.ensure_session()
    out = client.fetch_recent_activities(days=7, limit=5)
    assert len(out["activities"]) == 1
    assert out["activities"][0]["type"] == "running"


def test_all_fetch_functions(client: GarminClient) -> None:
    client.ensure_session()
    client.fetch_activity_detail(990001)
    client.fetch_daily_summary("2026-01-10")
    client.fetch_sleep("2026-01-10")
    client.fetch_hrv("2026-01-10")
    client.fetch_body_battery_and_stress("2026-01-10")
    client.fetch_training_readiness_and_status("2026-01-10")
    client.fetch_body_composition("2026-01-09", "2026-01-10")


def test_login_with_backoff_recovers_poisoned_tokens(
    client: GarminClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGarmin(client._settings.email, client._settings.password)
    fake.fail_first_login = True
    client._api_factory = lambda _e, _p: fake
    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)
    client.ensure_session()
    assert fake._login_calls == 2


def test_login_rate_limited_not_retried(
    client: GarminClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class RateLimitedGarmin(FakeGarmin):
        def login(self, tokenstore: str | None = None) -> tuple[str | None, Any]:
            raise GarminConnectTooManyRequestsError("429 too many")

    client._api_factory = lambda _e, _p: RateLimitedGarmin(_e, _p)
    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)
    with pytest.raises(RateLimitedError):
        client.ensure_session()


def test_retry_after_reauth(client: GarminClient) -> None:
    auth_state = {"failed_once": False}

    class ReauthGarmin(FakeGarmin):
        def get_activity(self, activity_id: str) -> dict[str, Any]:
            if not auth_state["failed_once"]:
                auth_state["failed_once"] = True
                raise GarminConnectAuthenticationError("401 Unauthorized session expired")
            return super().get_activity(activity_id)

    client._api_factory = lambda e, p: ReauthGarmin(e, p)
    client.invalidate_session()
    out = client.fetch_activity_detail(990001)
    assert out["activity_id"] == 990001


def test_token_dir_permissions(client: GarminClient, token_dir: Path) -> None:
    client.ensure_session()
    mode = token_dir.stat().st_mode & 0o777
    assert mode == 0o700


def test_lazy_singleton_only_constructs_once(
    monkeypatch: pytest.MonkeyPatch, token_dir: Path
) -> None:
    reset_garmin_client()
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    monkeypatch.setenv("GARMINTOKENS", str(token_dir))
    calls = {"n": 0}

    def from_env(cls: type[GarminClient]) -> GarminClient:
        calls["n"] += 1
        return GarminClient(
            GarminSettings.from_env(),
            api_factory=FakeGarmin,
        )

    monkeypatch.setattr(GarminClient, "from_env", classmethod(from_env))
    a = get_garmin_client()
    b = get_garmin_client()
    assert a is b
    assert calls["n"] == 1
    reset_garmin_client()
