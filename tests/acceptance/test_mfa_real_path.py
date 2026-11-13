"""Acceptance test: MFA handling via the REAL garminconnect exception path.

garmin_client.GarminClient hard-codes ``return_on_mfa = False`` and
``prompt_mfa = None`` on every constructed ``Garmin`` instance (see
``_perform_login`` in src/garmin_mcp/garmin_client.py). Given that
configuration, the installed garminconnect==0.3.20 library's own
``LoginMixin.login`` (client/sso.py) NEVER returns the
``("needs_mfa", client_state)`` tuple that ``_perform_login`` checks for
with ``if status == "needs_mfa": ...`` — that return value is only produced
when ``return_on_mfa=True``, which this client never sets for the
non-interactive path. Instead, when real_on_mfa=False and prompt_mfa=None,
the library raises::

    GarminConnectAuthenticationError("MFA Required but no prompt_mfa mechanism supplied")

which is handled by the *other* branch in ``_perform_login``
(``except GarminConnectAuthenticationError as exc: if "mfa" in lowered: ...``).

The existing unit test ``tests/test_garmin_client.py::test_mfa_raises_bootstrap_hint``
only exercises the ``status == "needs_mfa"`` branch via a hand-rolled
``FakeGarmin`` that does not mirror the real library's behavior for
``return_on_mfa=False``. That branch is therefore untested for the actual
production code path, and (as far as this client's own configuration is
concerned) effectively dead code.

This test uses the REAL ``garminconnect.Garmin`` class (via the client's
default ``api_factory``) and patches only the low-level SSO login strategy
chain, to prove the client surfaces the correct, bootstrap-pointing
``MfaRequiredError`` through the real exception path. No network calls;
no real credentials (placeholder email/password only).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from garminconnect import GarminConnectAuthenticationError

from garmin_mcp.config import GarminSettings
from garmin_mcp.errors import MfaRequiredError
from garmin_mcp.garmin_client import GarminClient


def _fake_login_mfa_required(self, email, password, prompt_mfa=None, return_on_mfa=False):
    assert return_on_mfa is False, (
        "garmin_client.py is expected to always set return_on_mfa=False for the "
        "non-interactive server path; if this changes, the needs_mfa status-tuple "
        "branch in _perform_login may become reachable and this test must be revisited."
    )
    assert prompt_mfa is None
    raise GarminConnectAuthenticationError(
        "MFA Required but no prompt_mfa mechanism supplied"
    )


def test_real_garminconnect_mfa_required_raises_bootstrap_hint(tmp_path: Path) -> None:
    settings = GarminSettings(
        email="fake@example.com",
        password="fake-placeholder-password",
        token_dir=tmp_path / "garth",
    )
    # Default api_factory -> constructs a real garminconnect.Garmin instance.
    client = GarminClient(settings)

    with patch(
        "garminconnect.client.sso.LoginMixin.login",
        _fake_login_mfa_required,
    ):
        with pytest.raises(MfaRequiredError) as err:
            client.ensure_session()

    assert "bootstrap" in str(err.value).lower()
    assert "garmin_mcp.bootstrap" in str(err.value)
