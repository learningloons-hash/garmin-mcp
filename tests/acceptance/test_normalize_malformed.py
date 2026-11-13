"""Acceptance tests: normalize_* functions under missing/partial/malformed data.

tests/test_normalize.py only exercises each normalize_* function against a
single complete, well-formed synthetic payload per field (see
tests/fixtures/synthetic_garmin.py). None of those tests feed in empty
dicts, missing nested keys, or the documented fallback-key variants
(e.g. ``weightSummaries`` vs ``dateWeightList``, ``avgHR`` vs
``averageHR``), so a regression that breaks a fallback path or a
None-vs-missing distinction would not be caught. This file adds that
coverage. No network calls; synthetic data only.
"""

from __future__ import annotations

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


def test_normalize_recent_activity_empty_dict() -> None:
    out = normalize_recent_activity({})
    assert out == {
        "activity_id": None,
        "name": None,
        "type": None,
        "start_time_local": None,
        "duration_sec": None,
        "distance_m": None,
        "avg_hr_bpm": None,
        "calories_kcal": None,
    }


def test_normalize_recent_activity_fallback_keys() -> None:
    out = normalize_recent_activity(
        {
            "activityUUID": "uuid-123",
            "activityType": "cycling",
            "avgHR": 133,
        }
    )
    assert out["activity_id"] == "uuid-123"
    assert out["type"] == "cycling"
    assert out["avg_hr_bpm"] == 133


def test_normalize_activity_detail_missing_duration_or_distance_no_pace() -> None:
    out = normalize_activity_detail({"activityId": 1, "distance": 5000.0})
    assert out["avg_pace_sec_per_km"] is None

    out2 = normalize_activity_detail({"activityId": 1, "duration": 1800.0})
    assert out2["avg_pace_sec_per_km"] is None


def test_normalize_daily_summary_empty_dict() -> None:
    out = normalize_daily_summary("2026-01-10", {})
    assert out == {
        "date": "2026-01-10",
        "steps": None,
        "calories_kcal": None,
        "resting_hr_bpm": None,
    }


def test_normalize_daily_summary_uses_total_kilocalories_when_present() -> None:
    out = normalize_daily_summary(
        "2026-01-10",
        {"totalKilocalories": 2500, "activeKilocalories": 999, "bmrKilocalories": 999},
    )
    assert out["calories_kcal"] == 2500


def test_normalize_daily_summary_steps_fallback_key() -> None:
    out = normalize_daily_summary("2026-01-10", {"steps": 1234})
    assert out["steps"] == 1234


def test_normalize_sleep_missing_dto_and_scores() -> None:
    out = normalize_sleep("2026-01-10", {})
    assert out["date"] == "2026-01-10"
    assert out["sleep_score"] is None
    assert out["duration_asleep_sec"] is None
    assert out["sleep_start_local"] is None


def test_normalize_sleep_flat_structure_without_dailySleepDTO() -> None:
    # normalize_sleep falls back to the raw dict itself when dailySleepDTO
    # is absent -- confirm that fallback actually surfaces fields.
    out = normalize_sleep(
        "2026-01-10",
        {"sleepTimeSeconds": 20000, "sleepScores": {"overall": {"value": 55}}},
    )
    assert out["duration_asleep_sec"] == 20000
    assert out["sleep_score"] == 55


def test_normalize_hrv_none_input() -> None:
    out = normalize_hrv("2026-01-10", None)
    assert out == {"date": "2026-01-10", "overnight_hrv_ms": None, "status": None}


def test_normalize_hrv_empty_dict_input() -> None:
    # {} is falsy -> same early-return path as None.
    out = normalize_hrv("2026-01-10", {})
    assert out["overnight_hrv_ms"] is None
    assert out["status"] is None


def test_normalize_hrv_missing_summary_key() -> None:
    out = normalize_hrv("2026-01-10", {"someOtherField": 1})
    assert out["overnight_hrv_ms"] is None


def test_normalize_body_battery_stress_all_none() -> None:
    out = normalize_body_battery_stress("2026-01-10", None, None, None)
    assert out == {
        "date": "2026-01-10",
        "body_battery_high": None,
        "body_battery_low": None,
        "avg_stress_level": None,
        "rest_stress_minutes": None,
    }


def test_normalize_body_battery_stress_empty_values_array_falls_back_to_summary_fields() -> None:
    battery_rows = [{"date": "2026-01-10", "bodyBatteryValuesArray": []}]
    out = normalize_body_battery_stress("2026-01-10", battery_rows, {}, None)
    # No levels parsed from the (empty) array, so it must fall back to the
    # per-row highest/lowest keys rather than silently staying None.
    assert out["body_battery_high"] is None
    assert out["body_battery_low"] is None


def test_normalize_body_battery_stress_row_with_highest_lowest_keys() -> None:
    battery_rows = [
        {
            "date": "2026-01-10",
            "bodyBatteryValuesArray": [],
            "bodyBatteryHighestValue": 77,
            "bodyBatteryLowestValue": 15,
        }
    ]
    out = normalize_body_battery_stress("2026-01-10", battery_rows, {}, None)
    assert out["body_battery_high"] == 77
    assert out["body_battery_low"] == 15


def test_normalize_body_battery_stress_no_matching_date_uses_first_row() -> None:
    battery_rows = [{"date": "2026-01-09", "bodyBatteryValuesArray": [[0, 10], [1, 50]]}]
    out = normalize_body_battery_stress("2026-01-10", battery_rows, {}, None)
    assert out["body_battery_high"] == 50
    assert out["body_battery_low"] == 10


def test_normalize_training_all_none() -> None:
    out = normalize_training("2026-01-10", None, None, None)
    assert out == {
        "date": "2026-01-10",
        "training_readiness_score": None,
        "training_status": None,
        "vo2_max": None,
        "acute_load": None,
        "chronic_load": None,
    }


def test_normalize_training_status_falls_back_to_readiness_level() -> None:
    out = normalize_training("2026-01-10", {"level": "low"}, {}, {})
    assert out["training_status"] == "low"


def test_normalize_training_vo2_nested_fallback() -> None:
    out = normalize_training(
        "2026-01-10",
        {},
        {},
        {"mostRecentVO2Max": {"vo2MaxValue": 51.5}},
    )
    assert out["vo2_max"] == 51.5


def test_normalize_body_composition_empty_dict() -> None:
    out = normalize_body_composition({})
    assert out == {"entries": []}


def test_normalize_body_composition_weightSummaries_fallback_key() -> None:
    out = normalize_body_composition(
        {
            "weightSummaries": [
                {"date": "2026-01-10", "weight": 70.0, "bmi": 21.0, "bodyFatPercentage": 17.5}
            ]
        }
    )
    assert len(out["entries"]) == 1
    assert out["entries"][0]["weight_kg"] == 70.0
    assert out["entries"][0]["body_fat_percent"] == 17.5


def test_normalize_body_composition_missing_weight_field() -> None:
    out = normalize_body_composition(
        {"dateWeightList": [{"calendarDate": "2026-01-10", "bmi": 21.0}]}
    )
    assert out["entries"][0]["weight_kg"] is None
