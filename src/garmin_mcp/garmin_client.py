"""Read-only Garmin Connect client with token persistence and normalized fetches."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, TypeVar

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from garmin_mcp.config import DEFAULT_TOKEN_DIR, GarminSettings
from garmin_mcp.errors import (
    AuthFailureError,
    MfaRequiredError,
    RateLimitedError,
    UpstreamChangedError,
    map_library_exception,
    public_message,
)
from garmin_mcp.normalize import (
    normalize_activity_detail,
    normalize_body_battery_stress,
    normalize_body_composition,
    normalize_daily_summary,
    normalize_hrv,
    normalize_recent_activity,
    normalize_sleep,
    normalize_training,
)
from garmin_mcp.redact import redact_secrets
from garmin_mcp.tokens_fs import ensure_token_dir

logger = logging.getLogger(__name__)

T = TypeVar("T")

_singleton: GarminClient | None = None
_singleton_lock = threading.Lock()

# Backoff for re-login after transient auth failures (not bad-password lockouts).
_LOGIN_BACKOFF_BASE_SEC = 1.0
_LOGIN_BACKOFF_MAX_SEC = 30.0
_MAX_LOGIN_ATTEMPTS = 3


def get_garmin_client() -> GarminClient:
    """Return a process-wide lazy singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = GarminClient.from_env()
    return _singleton


def reset_garmin_client() -> None:
    """Clear the singleton (tests only)."""
    global _singleton
    with _singleton_lock:
        _singleton = None


class GarminClient:
    """Wrapper around garminconnect with session management and normalization."""

    def __init__(
        self,
        settings: GarminSettings,
        *,
        api_factory: Callable[[str, str], Garmin] | None = None,
    ) -> None:
        self._settings = settings
        self._api_factory = api_factory or (
            lambda email, password: Garmin(email, password, retry_attempts=0)
        )
        self._api: Garmin | None = None
        self._session_lock = threading.Lock()
        self._logged_in = False
        self._bad_credentials = False

    @classmethod
    def from_env(cls) -> GarminClient:
        return cls(GarminSettings.from_env())

    @property
    def token_dir(self) -> str:
        return str(self._settings.token_dir or DEFAULT_TOKEN_DIR)

    def ensure_session(self) -> Garmin:
        """Load tokens or log in; raise on MFA when non-interactive."""
        if self._bad_credentials:
            raise AuthFailureError(
                "Garmin credentials previously rejected; refusing to retry login."
            )
        with self._session_lock:
            if self._logged_in and self._api is not None:
                return self._api
            self._login_with_backoff()
            assert self._api is not None
            return self._api

    def _login_with_backoff(self) -> None:
        self._settings.validate_for_login()
        last_exc: Exception | None = None
        for attempt in range(_MAX_LOGIN_ATTEMPTS):
            if attempt:
                delay = min(
                    _LOGIN_BACKOFF_BASE_SEC * (2 ** (attempt - 1)),
                    _LOGIN_BACKOFF_MAX_SEC,
                )
                logger.info("Garmin login retry in %.1fs (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
            try:
                self._perform_login()
                self._logged_in = True
                return
            except AuthFailureError as exc:
                last_exc = exc
                if _is_permanent_auth_failure(exc):
                    self._bad_credentials = True
                    raise
            except MfaRequiredError:
                raise
            except RateLimitedError:
                raise
            except Exception as exc:
                last_exc = exc
                mapped = map_library_exception(exc)
                if isinstance(mapped, RateLimitedError):
                    raise mapped from exc
                if isinstance(mapped, AuthFailureError) and _is_permanent_auth_failure(mapped):
                    self._bad_credentials = True
                    raise mapped from exc
                if not isinstance(mapped, AuthFailureError):
                    raise mapped from exc
        if last_exc:
            raise map_library_exception(last_exc) from last_exc
        raise AuthFailureError("Garmin login failed after retries.")

    def _perform_login(self) -> None:
        email = self._settings.email
        password = self._settings.password
        self._api = self._api_factory(email, password)
        self._api.return_on_mfa = False
        self._api.prompt_mfa = None

        try:
            tokenstore = self.token_dir
            ensure_token_dir(self._settings.token_dir)
            status, _state = self._api.login(tokenstore=tokenstore)
            if status == "needs_mfa":
                raise MfaRequiredError(MfaRequiredError.BOOTSTRAP_HINT)
        except GarminConnectAuthenticationError as exc:
            lowered = str(exc).lower()
            if "mfa" in lowered:
                raise MfaRequiredError(MfaRequiredError.BOOTSTRAP_HINT, cause=exc) from exc
            raise map_library_exception(exc) from exc

        logger.info(
            "Garmin session ready (tokens under %s)",
            redact_secrets(self.token_dir),
        )

    def invalidate_session(self) -> None:
        with self._session_lock:
            self._logged_in = False
            self._api = None

    def _call(self, fn: Callable[[Garmin], T]) -> T:
        try:
            api = self.ensure_session()
            return fn(api)
        except (MfaRequiredError, AuthFailureError):
            raise
        except Exception as exc:
            mapped = map_library_exception(exc)
            if mapped.cause:
                logger.warning(
                    "Garmin API call failed: %s",
                    public_message(mapped),
                )
            if isinstance(mapped, AuthFailureError):
                self.invalidate_session()
            raise mapped from exc

    def _retry_after_reauth(self, fn: Callable[[Garmin], T]) -> T:
        try:
            return self._call(fn)
        except AuthFailureError:
            self.invalidate_session()
            return self._call(fn)

    # --- Public fetch API (SPEC tool shapes) ---

    def fetch_recent_activities(self, *, days: int = 7, limit: int = 20) -> dict[str, Any]:
        end = date.today()
        start = end - timedelta(days=max(days, 1) - 1)

        def work(api: Garmin) -> dict[str, Any]:
            raw_list = api.get_activities_by_date(start.isoformat(), end.isoformat())
            if not isinstance(raw_list, list):
                raise UpstreamChangedError("get_activities_by_date did not return a list")
            sliced = raw_list[:limit]
            return {"activities": [normalize_recent_activity(item) for item in sliced]}

        return self._retry_after_reauth(work)

    def fetch_activity_detail(self, activity_id: int | str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            raw = api.get_activity(str(activity_id))
            return normalize_activity_detail(raw)

        return self._retry_after_reauth(work)

    def fetch_daily_summary(self, cdate: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            raw = api.get_user_summary(cdate)
            return normalize_daily_summary(cdate, raw)

        return self._retry_after_reauth(work)

    def fetch_sleep(self, cdate: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            raw = api.get_sleep_data(cdate)
            return normalize_sleep(cdate, raw)

        return self._retry_after_reauth(work)

    def fetch_hrv(self, cdate: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            raw = api.get_hrv_data(cdate)
            return normalize_hrv(cdate, raw)

        return self._retry_after_reauth(work)

    def fetch_body_battery_and_stress(self, cdate: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            battery = api.get_body_battery(cdate, cdate)
            stress = api.get_stress_data(cdate)
            summary: dict[str, Any] | None = None
            try:
                summary = api.get_user_summary(cdate)
            except GarminConnectConnectionError:
                summary = None
            return normalize_body_battery_stress(cdate, battery, stress, summary)

        return self._retry_after_reauth(work)

    def fetch_training_readiness_and_status(self, cdate: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            readiness = api.get_morning_training_readiness(cdate)
            daily_status = api.get_daily_training_status(cdate)
            training_status = api.get_training_status(cdate)
            return normalize_training(cdate, readiness, daily_status, training_status)

        return self._retry_after_reauth(work)

    def fetch_body_composition(self, start_date: str, end_date: str) -> dict[str, Any]:
        def work(api: Garmin) -> dict[str, Any]:
            raw = api.get_weigh_ins(start_date, end_date)
            return normalize_body_composition(raw)

        return self._retry_after_reauth(work)


def _is_permanent_auth_failure(exc: AuthFailureError) -> bool:
    parts = [str(exc)]
    if exc.cause:
        parts.append(str(exc.cause))
        inner = exc.cause
        while inner.__cause__ is not None:
            inner = inner.__cause__
            parts.append(str(inner))
    text = " ".join(parts).lower()
    permanent_markers = (
        "incorrect email or password",
        "username and password are required",
        "credentials previously rejected",
        "account locked",
    )
    if any(marker in text for marker in permanent_markers):
        return True
    # garminconnect 0.3.20 raises this shape for wrong-password 401s from SSO.
    if isinstance(exc.cause, GarminConnectAuthenticationError):
        cause_lower = str(exc.cause).lower()
        if "authentication failed (401 unauthorized)" in cause_lower and (
            "incorrect email or password" in cause_lower or "account locked" in cause_lower
        ):
            return True
    return False
