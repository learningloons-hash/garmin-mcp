from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)

from garmin_mcp.errors import (
    AuthFailureError,
    MfaRequiredError,
    NotFoundError,
    RateLimitedError,
    map_library_exception,
)


def test_map_mfa_auth_error() -> None:
    exc = GarminConnectAuthenticationError("MFA Required but no prompt_mfa mechanism")
    mapped = map_library_exception(exc)
    assert isinstance(mapped, MfaRequiredError)


def test_map_rate_limit() -> None:
    mapped = map_library_exception(GarminConnectTooManyRequestsError("429"))
    assert isinstance(mapped, RateLimitedError)


def test_map_not_found() -> None:
    mapped = map_library_exception(GarminConnectNotFoundError("missing"))
    assert isinstance(mapped, NotFoundError)


def test_map_auth_failure() -> None:
    mapped = map_library_exception(GarminConnectAuthenticationError("401 Unauthorized"))
    assert isinstance(mapped, AuthFailureError)


def test_connection_error_hides_upstream_detail() -> None:
    mapped = map_library_exception(
        GarminConnectConnectionError("super-secret-upstream-token-value leaked")
    )
    text = str(mapped)
    assert "super-secret-upstream-token-value" not in text
    assert "leaked" not in text
    assert "server logs" in text
