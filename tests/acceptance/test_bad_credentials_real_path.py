"""Acceptance test: bad-credentials detection via the REAL error-message text.

garmin_client._is_permanent_auth_failure() decides whether a login failure is
"permanent" (bad password -> stop retrying, set _bad_credentials) by
substring-matching the lowercased exception text against a short marker
list, e.g. "incorrect email or password". That function is never exercised
by the existing unit tests: tests/test_garmin_client.py::
test_bad_credentials_no_retry_storm sets ``client._bad_credentials = True``
directly, bypassing the detection logic entirely, so a regression in the
marker strings (e.g. if a future garminconnect version rewords its 401
message) would not be caught by the suite.

This test drives the real retry loop (_login_with_backoff) with the actual
401 message text produced by the installed garminconnect==0.3.20
(garminconnect/api/base.py's login() HTTPError handler), via the client's
real default api_factory (a genuine garminconnect.Garmin instance) with only
the low-level SSO strategy chain patched. No network calls; no real
credentials (placeholder values only).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from garminconnect import GarminConnectAuthenticationError

from garmin_mcp.config import GarminSettings
from garmin_mcp.errors import AuthFailureError
from garmin_mcp.garmin_client import GarminClient

# Verbatim shape of the real library's 401 message (api/base.py), which is
# what _is_permanent_auth_failure must recognize via its "incorrect email or
# password" marker.
REAL_BAD_CREDENTIALS_MESSAGE = (
    "Authentication failed (401 Unauthorized). "
    "Possible causes:\n"
    "  • Incorrect email or password\n"
    "  • Account locked — check https://sso.garmin.com\n"
    "  • Garmin SSO service is temporarily unavailable\n"
    "Original error: 401 Client Error: Unauthorized for url: https://example.invalid"
)


def test_bad_credentials_stops_after_one_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = GarminSettings(
        email="fake@example.com",
        password="definitely-wrong-password",
        token_dir=tmp_path / "garth",
    )
    client = GarminClient(settings)  # real default api_factory

    call_count = {"n": 0}

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        call_count["n"] += 1
        raise GarminConnectAuthenticationError(REAL_BAD_CREDENTIALS_MESSAGE)

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)

    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()

    assert call_count["n"] == 1, (
        "bad credentials must not trigger a retry storm "
        f"(expected exactly 1 login attempt, got {call_count['n']})"
    )
    assert client._bad_credentials is True

    # A second call must not attempt the network again either.
    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()
    assert call_count["n"] == 1, "second call re-attempted login after bad credentials"


def test_public_error_never_leaks_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_password = "sUpEr-s3cr3t-placeholder-pw-not-real"
    settings = GarminSettings(
        email="fake@example.com",
        password=secret_password,
        token_dir=tmp_path / "garth",
    )
    client = GarminClient(settings)

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        # Simulate an upstream error that (hypothetically) echoes the submitted
        # password back, as some auth providers' error bodies do. Message
        # matches a permanent-failure marker so this fails on attempt 1 and
        # isolates redaction from the retry-exhaustion behavior below.
        raise GarminConnectAuthenticationError(
            f"Incorrect email or password for fake@example.com password={password}"
        )

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)

    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError) as err:
            client.ensure_session()

    assert secret_password not in str(err.value)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BLOCKER: when an AuthFailureError's text does not match any of the "
        "hard-coded permanent-failure markers in _is_permanent_auth_failure "
        "(garmin_client.py:278-282), _login_with_backoff exhausts all "
        "_MAX_LOGIN_ATTEMPTS and then re-raises via "
        "`raise map_library_exception(last_exc) from last_exc` "
        "(garmin_client.py:144). map_library_exception() does not recognize "
        "already-typed internal GarminMcpError/AuthFailureError instances "
        "(it only pattern-matches garminconnect/stdlib exception types), so "
        "it falls through to the generic catch-all and re-wraps the error as "
        "a plain GarminMcpError('Unexpected Garmin client error "
        "(AuthFailureError).'). The specific AuthFailureError type (and its "
        "clear, credential-focused message) is lost after retry exhaustion "
        "for any ambiguous/unrecognized auth failure wording — a problem for "
        "any caller (e.g. a future MCP tool layer) that branches on "
        "isinstance(exc, AuthFailureError) to give users 'check your "
        "credentials' guidance vs. a generic error."
    ),
)
def test_ambiguous_auth_failure_preserves_type_after_retry_exhaustion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = GarminSettings(
        email="fake@example.com",
        password="some-password-placeholder",
        token_dir=tmp_path / "garth",
    )
    client = GarminClient(settings)

    def fake_login(self, email, password, prompt_mfa=None, return_on_mfa=False):
        # Deliberately does NOT contain any of the three hard-coded
        # permanent-failure markers, so _is_permanent_auth_failure returns
        # False and the loop retries until attempts are exhausted.
        raise GarminConnectAuthenticationError(
            "401 Unauthorized: session token rejected by API tier"
        )

    monkeypatch.setattr("garmin_mcp.garmin_client.time.sleep", lambda _s: None)

    with patch("garminconnect.client.sso.LoginMixin.login", fake_login):
        with pytest.raises(AuthFailureError):
            client.ensure_session()
