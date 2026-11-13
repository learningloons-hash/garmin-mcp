"""Application errors for the Garmin client layer."""

from __future__ import annotations

import logging

from garmin_mcp.redact import redact_secrets

logger = logging.getLogger(__name__)


class GarminMcpError(Exception):
    """Base error for garmin-mcp client operations."""

    code: str = "garmin_error"

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __str__(self) -> str:
        return public_message(self)


class AuthFailureError(GarminMcpError):
    code = "auth_failure"


class MfaRequiredError(GarminMcpError):
    code = "mfa_required"

    BOOTSTRAP_HINT = (
        "Garmin requires MFA. Run once: python -m garmin_mcp.bootstrap "
        "(with GARMIN_EMAIL, GARMIN_PASSWORD, and GARMINTOKENS set). "
        "With valid tokens on the volume, the server should not need MFA again "
        "until tokens expire."
    )


class RateLimitedError(GarminMcpError):
    code = "rate_limited"


class NotFoundError(GarminMcpError):
    code = "not_found"


class UpstreamChangedError(GarminMcpError):
    code = "upstream_changed"


def map_library_exception(exc: BaseException) -> GarminMcpError:
    """Map garminconnect / requests failures to garmin-mcp errors."""
    from garminconnect import (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectNotFoundError,
        GarminConnectTooManyRequestsError,
    )

    raw = str(exc)
    logger.debug(
        "Garmin upstream error (%s): %s",
        type(exc).__name__,
        redact_secrets(raw),
        exc_info=exc,
    )
    lowered = raw.lower()

    if isinstance(exc, GarminConnectTooManyRequestsError):
        return RateLimitedError("Garmin rate limit exceeded; retry later.", cause=exc)

    if isinstance(exc, GarminConnectNotFoundError):
        return NotFoundError("Garmin resource not found.", cause=exc)

    if isinstance(exc, MfaRequiredError):
        return exc

    if isinstance(exc, GarminConnectAuthenticationError):
        if "mfa" in lowered:
            return MfaRequiredError(MfaRequiredError.BOOTSTRAP_HINT, cause=exc)
        return AuthFailureError(
            "Garmin authentication failed. Check GARMIN_EMAIL/GARMIN_PASSWORD "
            "and token files under GARMINTOKENS.",
            cause=exc,
        )

    if isinstance(exc, GarminConnectConnectionError):
        if "404" in lowered or "not found" in lowered:
            return NotFoundError("Garmin resource not found.", cause=exc)
        if "429" in lowered or "rate" in lowered:
            return RateLimitedError("Garmin rate limit exceeded; retry later.", cause=exc)
        if any(k in lowered for k in ("401", "unauthorized", "authentication")):
            return AuthFailureError("Garmin authentication failed.", cause=exc)
        if any(k in lowered for k in ("json", "parse", "keyerror", "schema")):
            return UpstreamChangedError(
                "Unexpected Garmin response shape; upstream API may have changed.",
                cause=exc,
            )
        return GarminMcpError(
            "Garmin connection error; see server logs for details.",
            cause=exc,
        )

    if isinstance(exc, KeyError | TypeError | ValueError):
        return UpstreamChangedError(
            "Unexpected Garmin response shape; upstream API may have changed.",
            cause=exc,
        )

    return GarminMcpError(
        f"Unexpected Garmin client error ({type(exc).__name__}).",
        cause=exc,
    )


def public_message(exc: GarminMcpError | BaseException) -> str:
    """User-safe message (never includes upstream or secret text)."""
    if isinstance(exc, GarminMcpError):
        return redact_secrets(exc.args[0] if exc.args else type(exc).__name__)
    return redact_secrets(str(exc))
