from garminconnect import (
    GarminConnectAuthenticationError,
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
