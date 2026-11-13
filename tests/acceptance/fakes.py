"""Synthetic GarminClient stand-ins for acceptance tests (no real Garmin calls)."""

from __future__ import annotations

from typing import Any

SYNTH_DAILY_SUMMARY = {
    "date": "2026-01-10",
    "steps": 9000,
    "calories_kcal": 2050,
    "resting_hr_bpm": 55,
}


class AcceptanceFakeGarminClient:
    """Minimal read-only fetch_* surface, matching GarminClient's public API."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_recent_activities(self, *, days: int = 7, limit: int = 20) -> dict[str, Any]:
        self.calls.append("fetch_recent_activities")
        return {"activities": []}

    def fetch_activity_detail(self, activity_id: int | str) -> dict[str, Any]:
        self.calls.append("fetch_activity_detail")
        return {"activity_id": int(activity_id), "name": "Test Run"}

    def fetch_daily_summary(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_daily_summary")
        return dict(SYNTH_DAILY_SUMMARY, date=cdate)

    def fetch_sleep(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_sleep")
        return {"date": cdate}

    def fetch_hrv(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_hrv")
        return {"date": cdate}

    def fetch_body_battery_and_stress(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_body_battery_and_stress")
        return {"date": cdate}

    def fetch_training_readiness_and_status(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_training_readiness_and_status")
        return {"date": cdate}

    def fetch_body_composition(self, start_date: str, end_date: str) -> dict[str, Any]:
        self.calls.append("fetch_body_composition")
        return {"entries": []}


# Synthetic secrets embedded in a raised exception, used only to verify the
# server never echoes them back to a client or into its own logs. These are
# not real credentials.
LEAK_EMAIL = "fake-user@example.test"
LEAK_PASSWORD = "FakePassw0rd!123"
LEAK_BEARER = "Bearer FAKE.JWT.TOKEN"


class LeakyFakeGarminClient(AcceptanceFakeGarminClient):
    """Raises an exception carrying synthetic secrets and a real stack trace."""

    def fetch_daily_summary(self, cdate: str) -> dict[str, Any]:
        self.calls.append("fetch_daily_summary")
        _raise_with_secrets()


def _raise_with_secrets() -> None:
    def _inner() -> None:
        message = (
            f"upstream failure: email={LEAK_EMAIL} password={LEAK_PASSWORD} "
            f"Authorization: {LEAK_BEARER}"
        )
        raise RuntimeError(message)

    def _middle() -> None:
        _inner()

    _middle()
