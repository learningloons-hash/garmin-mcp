"""Normalize raw garminconnect responses to compact dicts with units."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _activity_type(raw: dict[str, Any]) -> str | None:
    at = raw.get("activityType")
    if isinstance(at, dict):
        return at.get("typeKey") or at.get("typeId")
    if isinstance(at, str):
        return at
    return None


def _pace_sec_per_km(duration_sec: float | None, distance_m: float | None) -> int | None:
    if not duration_sec or not distance_m or distance_m <= 0:
        return None
    km = distance_m / 1000.0
    return int(round(duration_sec / km))


def _timestamp_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        # Garmin often uses millisecond epochs for local sleep timestamps.
        seconds = value / 1000.0 if value > 1_000_000_000_000 else value
        return datetime.fromtimestamp(seconds).isoformat(sep="T", timespec="seconds")
    return None


def normalize_recent_activity(raw: dict[str, Any]) -> dict[str, Any]:
    activity_id = raw.get("activityId") or raw.get("activityUUID")
    distance = raw.get("distance")
    return {
        "activity_id": activity_id,
        "name": raw.get("activityName"),
        "type": _activity_type(raw),
        "start_time_local": raw.get("startTimeLocal"),
        "duration_sec": raw.get("duration"),
        "distance_m": float(distance) if distance is not None else None,
        "avg_hr_bpm": raw.get("averageHR") or raw.get("avgHR"),
        "calories_kcal": raw.get("calories"),
    }


def normalize_activity_detail(raw: dict[str, Any]) -> dict[str, Any]:
    base = normalize_recent_activity(raw)
    distance = raw.get("distance")
    duration = raw.get("duration")
    base.update(
        {
            "elevation_gain_m": raw.get("elevationGain"),
            "max_hr_bpm": raw.get("maxHR") or raw.get("maxHeartRate"),
            "avg_pace_sec_per_km": _pace_sec_per_km(
                float(duration) if duration is not None else None,
                float(distance) if distance is not None else None,
            ),
        }
    )
    return base


def normalize_daily_summary(cdate: str, raw: dict[str, Any]) -> dict[str, Any]:
    active_kcal = raw.get("activeKilocalories")
    bmr_kcal = raw.get("bmrKilocalories") or 0
    total_kcal = raw.get("totalKilocalories")
    if total_kcal is None and active_kcal is not None:
        total_kcal = (active_kcal or 0) + (bmr_kcal or 0)
    return {
        "date": cdate,
        "steps": raw.get("totalSteps") or raw.get("steps"),
        "calories_kcal": total_kcal,
        "resting_hr_bpm": raw.get("restingHeartRate") or raw.get("minHeartRate"),
    }


def normalize_sleep(cdate: str, raw: dict[str, Any]) -> dict[str, Any]:
    dto = raw.get("dailySleepDTO") or raw
    scores = dto.get("sleepScores") or {}
    overall = _nested(scores, "overall", "value")
    return {
        "date": cdate,
        "sleep_start_local": _timestamp_to_iso(dto.get("sleepStartTimestampLocal")),
        "sleep_end_local": _timestamp_to_iso(dto.get("sleepEndTimestampLocal")),
        "duration_asleep_sec": dto.get("sleepTimeSeconds"),
        "deep_sleep_sec": dto.get("deepSleepSeconds"),
        "light_sleep_sec": dto.get("lightSleepSeconds"),
        "rem_sleep_sec": dto.get("remSleepSeconds"),
        "awake_sec": dto.get("awakeSleepSeconds"),
        "sleep_score": overall,
    }


def normalize_hrv(cdate: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {"date": cdate, "overnight_hrv_ms": None, "status": None}
    summary = raw.get("hrvSummary") or raw
    return {
        "date": cdate,
        "overnight_hrv_ms": summary.get("lastNightAvg"),
        "status": summary.get("status"),
    }


def normalize_body_battery_stress(
    cdate: str,
    battery_rows: list[dict[str, Any]] | None,
    stress: dict[str, Any] | None,
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    high = low = None
    if battery_rows:
        row = next((r for r in battery_rows if r.get("date") == cdate), battery_rows[0])
        values = row.get("bodyBatteryValuesArray") or []
        levels = [pair[1] for pair in values if isinstance(pair, list) and len(pair) >= 2]
        if levels:
            high, low = max(levels), min(levels)
        else:
            high = row.get("bodyBatteryHighestValue") or row.get("charged")
            low = row.get("bodyBatteryLowestValue") or row.get("drained")

    if summary:
        high = high if high is not None else summary.get("bodyBatteryHighestValue")
        low = low if low is not None else summary.get("bodyBatteryLowestValue")

    stress = stress or {}
    rest_stress = stress.get("restStressDuration") or summary.get("restStressDuration")
    if rest_stress is not None:
        rest_stress = int(rest_stress) // 60

    return {
        "date": cdate,
        "body_battery_high": high,
        "body_battery_low": low,
        "avg_stress_level": stress.get("averageStressLevel")
        or summary.get("averageStressLevel"),
        "rest_stress_minutes": rest_stress,
    }


def normalize_training(
    cdate: str,
    readiness: dict[str, Any] | None,
    daily_status: dict[str, Any] | None,
    training_status: dict[str, Any] | None,
) -> dict[str, Any]:
    readiness = readiness or {}
    daily_status = daily_status or {}
    training_status = training_status or {}

    score = readiness.get("score")
    status = (
        daily_status.get("trainingStatus")
        or training_status.get("trainingStatus")
        or readiness.get("level")
    )
    vo2 = training_status.get("vo2Max") or training_status.get("vo2MaxValue")
    if vo2 is None:
        vo2 = _nested(training_status, "mostRecentVO2Max", "vo2MaxValue")

    return {
        "date": cdate,
        "training_readiness_score": score,
        "training_status": status,
        "vo2_max": vo2,
        "acute_load": daily_status.get("acuteTrainingLoad") or daily_status.get("dailyAcuteLoad"),
        "chronic_load": daily_status.get("chronicTrainingLoad")
        or daily_status.get("dailyChronicLoad"),
    }


def normalize_body_composition(raw: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for item in raw.get("dateWeightList") or raw.get("weightSummaries") or []:
        weight = item.get("weight") or item.get("weightGrams")
        if weight is not None and weight > 500:
            weight = weight / 1000.0
        entries.append(
            {
                "date": item.get("calendarDate") or item.get("date"),
                "weight_kg": weight,
                "bmi": item.get("bmi"),
                "body_fat_percent": item.get("bodyFat") or item.get("bodyFatPercentage"),
            }
        )
    entries.sort(key=lambda e: e.get("date") or "")
    return {"entries": entries}
