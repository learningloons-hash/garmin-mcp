"""Normalize raw garminconnect responses to compact dicts with units."""

from __future__ import annotations

from collections.abc import Mapping
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
    for key in ("activityTypeDTO", "activityType", "eventTypeDTO"):
        at = raw.get(key)
        if isinstance(at, dict):
            type_key = at.get("typeKey")
            if type_key is not None:
                return str(type_key)
            type_id = at.get("typeId")
            if type_id is not None:
                return str(type_id)
        if isinstance(at, str):
            return at
    return None


def _activity_metrics_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Metrics from get_activity summaryDTO with list-endpoint top-level fallbacks."""
    row: dict[str, Any] = {}
    summary = raw.get("summaryDTO")
    if isinstance(summary, dict):
        row.update(summary)
    for key in (
        "startTimeLocal",
        "duration",
        "distance",
        "averageHR",
        "avgHR",
        "maxHR",
        "maxHeartRate",
        "elevationGain",
        "calories",
    ):
        if row.get(key) is None and raw.get(key) is not None:
            row[key] = raw.get(key)
    return row


def _pace_sec_per_km(duration_sec: float | None, distance_m: float | None) -> int | None:
    if not duration_sec or not distance_m or distance_m <= 0:
        return None
    km = distance_m / 1000.0
    return int(round(duration_sec / km))


def _timestamp_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        # Garmin often uses millisecond epochs for local sleep timestamps.
        seconds = value / 1000.0 if value > 1_000_000_000_000 else value
        return datetime.fromtimestamp(seconds).isoformat(sep="T", timespec="seconds")
    if isinstance(value, str):
        return value
    return None


def _is_date_only_timestamp(value: str, calendar_date: str | None) -> bool:
    """Date-only placeholders (no time); not local ISO timestamps at midnight."""
    if calendar_date and value == calendar_date:
        return True
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


def _sleep_timestamp_local(dto: Mapping[str, Any], *, start: bool) -> str | None:
    """Prefer millisecond local epochs; reject date-only strings when GMT ms is available."""
    calendar_date = dto.get("calendarDate")
    local_key = "sleepStartTimestampLocal" if start else "sleepEndTimestampLocal"
    gmt_key = "sleepStartTimestampGMT" if start else "sleepEndTimestampGMT"

    local_val = dto.get(local_key)
    if isinstance(local_val, int | float):
        return _timestamp_to_iso(local_val)
    if isinstance(local_val, str):
        if not _is_date_only_timestamp(local_val, calendar_date):
            return local_val

    gmt_val = dto.get(gmt_key)
    if isinstance(gmt_val, int | float):
        return _timestamp_to_iso(gmt_val)
    return None


def _hrv_summary_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    summary = raw.get("hrvSummary")
    if isinstance(summary, dict):
        return summary
    return {}


def _vo2_from_sport_sections(row: Mapping[str, Any]) -> float | int | None:
    for sport_key in ("generic", "cycling"):
        section = row.get(sport_key) or {}
        if isinstance(section, dict):
            val = section.get("vo2MaxValue")
            if val is None:
                val = section.get("vo2MaxPreciseValue")
            if val is not None:
                return val
    return None


def _pick_primary_training_device(device_map: dict[str, Any]) -> dict[str, Any]:
    if not device_map:
        return {}
    for device in device_map.values():
        if isinstance(device, dict) and device.get("primaryTrainingDevice"):
            return device
    first = next(iter(device_map.values()), None)
    return first if isinstance(first, dict) else {}


def _coerce_readiness_snapshot(readiness: Any) -> dict[str, Any]:
    if readiness is None:
        return {}
    if isinstance(readiness, list):
        morning = next(
            (
                entry
                for entry in readiness
                if isinstance(entry, dict)
                and entry.get("inputContext") == "AFTER_WAKEUP_RESET"
            ),
            None,
        )
        if morning is not None:
            return morning
        first = readiness[0] if readiness else None
        return first if isinstance(first, dict) else {}
    if isinstance(readiness, dict):
        return readiness
    return {}


def _coerce_daily_training_status(daily_status: Any) -> dict[str, Any]:
    if daily_status is None:
        return {}
    if isinstance(daily_status, list):
        primary = next(
            (
                entry
                for entry in daily_status
                if isinstance(entry, dict) and entry.get("primaryTrainingDevice")
            ),
            None,
        )
        if primary is not None:
            return primary
        first = daily_status[0] if daily_status else None
        return first if isinstance(first, dict) else {}
    if isinstance(daily_status, dict):
        return daily_status
    return {}


def _training_device_snapshot(training_status: dict[str, Any]) -> dict[str, Any]:
    recent = training_status.get("mostRecentTrainingStatus") or {}
    if not isinstance(recent, dict):
        return {}
    device_map = recent.get("latestTrainingStatusData") or {}
    if not isinstance(device_map, dict):
        return {}
    return _pick_primary_training_device(device_map)


def _vo2_max_from_training_status(training_status: dict[str, Any]) -> float | int | None:
    vo2_root = training_status.get("mostRecentVO2Max") or {}
    if isinstance(vo2_root, dict):
        vo2 = _vo2_from_sport_sections(vo2_root)
        if vo2 is not None:
            return vo2
    return training_status.get("vo2Max") or training_status.get("vo2MaxValue")


def _vo2_max_from_max_metrics(max_metrics: Any) -> float | int | None:
    if max_metrics is None:
        return None
    if isinstance(max_metrics, list):
        row = max_metrics[0] if max_metrics else None
    elif isinstance(max_metrics, dict):
        row = max_metrics
    else:
        return None
    if not isinstance(row, dict):
        return None
    return _vo2_from_sport_sections(row)


def _acute_chronic_load(
    daily_row: dict[str, Any], device_row: dict[str, Any]
) -> tuple[Any, Any]:
    acute_block = device_row.get("acuteTrainingLoadDTO") or {}
    if not isinstance(acute_block, dict):
        acute_block = {}
    acute = (
        daily_row.get("dailyTrainingLoadAcute")
        or acute_block.get("dailyTrainingLoadAcute")
        or daily_row.get("acuteTrainingLoad")
        or daily_row.get("dailyAcuteLoad")
    )
    chronic = (
        daily_row.get("dailyTrainingLoadChronic")
        or acute_block.get("dailyTrainingLoadChronic")
        or daily_row.get("chronicTrainingLoad")
        or daily_row.get("dailyChronicLoad")
    )
    return acute, chronic


def normalize_recent_activity(raw: dict[str, Any]) -> dict[str, Any]:
    activity_id = raw.get("activityId") or raw.get("activityUUID")
    metrics = _activity_metrics_row(raw)
    distance = metrics.get("distance")
    duration = metrics.get("duration")
    return {
        "activity_id": activity_id,
        "name": raw.get("activityName"),
        "type": _activity_type(raw),
        "start_time_local": metrics.get("startTimeLocal"),
        "duration_sec": duration,
        "distance_m": float(distance) if distance is not None else None,
        "avg_hr_bpm": metrics.get("averageHR") or metrics.get("avgHR"),
        "calories_kcal": metrics.get("calories"),
    }


def normalize_activity_detail(raw: dict[str, Any]) -> dict[str, Any]:
    base = normalize_recent_activity(raw)
    metrics = _activity_metrics_row(raw)
    distance = metrics.get("distance")
    duration = metrics.get("duration")
    base.update(
        {
            "elevation_gain_m": metrics.get("elevationGain"),
            "max_hr_bpm": metrics.get("maxHR") or metrics.get("maxHeartRate"),
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
        "sleep_start_local": _sleep_timestamp_local(dto, start=True),
        "sleep_end_local": _sleep_timestamp_local(dto, start=False),
        "duration_asleep_sec": dto.get("sleepTimeSeconds"),
        "deep_sleep_sec": dto.get("deepSleepSeconds"),
        "light_sleep_sec": dto.get("lightSleepSeconds"),
        "rem_sleep_sec": dto.get("remSleepSeconds"),
        "awake_sec": dto.get("awakeSleepSeconds"),
        "sleep_score": overall,
    }


def normalize_hrv(cdate: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    if raw is None or not isinstance(raw, dict):
        return {"date": cdate, "overnight_hrv_ms": None, "status": None}
    summary = _hrv_summary_fields(raw)
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

    summary_fields = summary or {}
    if summary_fields:
        high = high if high is not None else summary_fields.get("bodyBatteryHighestValue")
        low = low if low is not None else summary_fields.get("bodyBatteryLowestValue")

    stress_fields = stress or {}
    rest_stress = stress_fields.get("restStressDuration") or summary_fields.get(
        "restStressDuration"
    )
    if rest_stress is not None:
        rest_stress = int(rest_stress) // 60

    return {
        "date": cdate,
        "body_battery_high": high,
        "body_battery_low": low,
        "avg_stress_level": stress_fields.get("averageStressLevel")
        or summary_fields.get("averageStressLevel"),
        "rest_stress_minutes": rest_stress,
    }


def normalize_training(
    cdate: str,
    readiness: dict[str, Any] | list[dict[str, Any]] | None,
    daily_status: dict[str, Any] | list[dict[str, Any]] | None,
    training_status: dict[str, Any] | None,
    max_metrics: Any | None = None,
) -> dict[str, Any]:
    readiness_row = _coerce_readiness_snapshot(readiness)
    daily_row = _coerce_daily_training_status(daily_status)
    training_status = training_status or {}
    device_row = _training_device_snapshot(training_status)

    score = readiness_row.get("score")
    status = (
        daily_row.get("trainingStatusFeedbackPhrase")
        or device_row.get("trainingStatusFeedbackPhrase")
        or daily_row.get("trainingStatus")
        or device_row.get("trainingStatus")
        or training_status.get("trainingStatus")
        or readiness_row.get("level")
    )
    vo2 = _vo2_max_from_training_status(training_status)
    if vo2 is None:
        vo2 = _vo2_max_from_max_metrics(max_metrics)
    acute, chronic = _acute_chronic_load(daily_row, device_row)

    return {
        "date": cdate,
        "training_readiness_score": score,
        "training_status": status,
        "vo2_max": vo2,
        "acute_load": acute,
        "chronic_load": chronic,
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
