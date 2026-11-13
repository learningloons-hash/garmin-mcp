from datetime import datetime

from garmin_mcp.normalize import (
    _timestamp_to_iso,
    normalize_activity_detail,
    normalize_body_battery_stress,
    normalize_body_composition,
    normalize_daily_summary,
    normalize_hrv,
    normalize_recent_activity,
    normalize_sleep,
    normalize_training,
)
from tests.fixtures.realistic_garmin import (
    REAL_ACTIVITY_DETAIL_DTO,
    REAL_DAILY_TRAINING_STATUS_LIST,
    REAL_HRV_NIGHT,
    REAL_MAX_METRICS_LIST,
    REAL_SLEEP_DATE_ONLY_START,
    REAL_TRAINING_READINESS_LIST,
    REAL_TRAINING_STATUS_AGGREGATED,
)
from tests.fixtures.synthetic_garmin import (
    SYNTH_ACTIVITY,
    SYNTH_BATTERY,
    SYNTH_DAILY_STATUS,
    SYNTH_HRV,
    SYNTH_READINESS,
    SYNTH_SLEEP,
    SYNTH_STRESS,
    SYNTH_SUMMARY,
    SYNTH_TRAINING_STATUS,
    SYNTH_WEIGHT,
)


def test_normalize_recent_activity() -> None:
    out = normalize_recent_activity(SYNTH_ACTIVITY)
    assert out["activity_id"] == 990001
    assert out["distance_m"] == 5000.0
    assert out["calories_kcal"] == 350


def test_normalize_activity_detail_includes_pace() -> None:
    out = normalize_activity_detail(SYNTH_ACTIVITY)
    assert out["avg_pace_sec_per_km"] == 360
    assert out["elevation_gain_m"] == 25.0


def test_normalize_activity_detail_summary_dto_shape() -> None:
    out = normalize_activity_detail(REAL_ACTIVITY_DETAIL_DTO)
    assert out["activity_id"] == 25063564656
    assert out["name"] == "Example City Running"
    assert out["type"] == "running"
    assert out["start_time_local"] == "2026-11-13T16:54:26"
    assert out["duration_sec"] == 6594.0
    assert out["distance_m"] == 15020.0
    assert out["avg_hr_bpm"] == 132
    assert out["calories_kcal"] == 1025
    assert out["max_hr_bpm"] == 158
    assert out["elevation_gain_m"] == 42.0
    assert out["avg_pace_sec_per_km"] == int(round(6594.0 / 15.02))


def test_normalize_daily_summary() -> None:
    out = normalize_daily_summary("2026-01-10", SYNTH_SUMMARY)
    assert out["steps"] == 9000
    assert out["resting_hr_bpm"] == 55


def test_normalize_sleep() -> None:
    out = normalize_sleep("2026-01-10", SYNTH_SLEEP)
    assert out["sleep_score"] == 80
    assert out["duration_asleep_sec"] == 25200


def test_normalize_sleep_date_only_start_uses_gmt_ms() -> None:
    out = normalize_sleep("2026-11-13", REAL_SLEEP_DATE_ONLY_START)
    assert out["sleep_start_local"] == _timestamp_to_iso(1762991580000)
    assert out["sleep_end_local"] == _timestamp_to_iso(1763018760000)


def test_normalize_sleep_preserves_midnight_ms_and_iso() -> None:
    midnight = datetime(2026, 11, 13, 0, 0, 0)
    ms = int(midnight.timestamp() * 1000)
    payload = {
        "dailySleepDTO": {
            "calendarDate": "2026-11-13",
            "sleepStartTimestampLocal": ms,
            "sleepEndTimestampLocal": "2026-11-13T08:06:00",
        }
    }
    out = normalize_sleep("2026-11-13", payload)
    assert out["sleep_start_local"] == _timestamp_to_iso(ms)
    assert out["sleep_start_local"].endswith("T00:00:00")
    assert out["sleep_end_local"] == "2026-11-13T08:06:00"


def test_normalize_hrv() -> None:
    out = normalize_hrv("2026-01-10", SYNTH_HRV)
    assert out["overnight_hrv_ms"] == 48.5
    assert out["status"] == "balanced"


def test_normalize_hrv_reads_hrv_summary() -> None:
    out = normalize_hrv("2026-11-13", REAL_HRV_NIGHT)
    assert out["overnight_hrv_ms"] == 51.2
    assert out["status"] == "balanced"


def test_normalize_hrv_null_payload() -> None:
    out = normalize_hrv("2026-11-13", None)
    assert out["overnight_hrv_ms"] is None
    assert out["status"] is None


def test_normalize_body_battery_stress() -> None:
    out = normalize_body_battery_stress(
        "2026-01-10", SYNTH_BATTERY, SYNTH_STRESS, SYNTH_SUMMARY
    )
    assert out["body_battery_high"] == 88
    assert out["body_battery_low"] == 25
    assert out["rest_stress_minutes"] == 180


def test_normalize_body_battery_stress_summary_none() -> None:
    out = normalize_body_battery_stress("2026-01-10", SYNTH_BATTERY, SYNTH_STRESS, None)
    assert out["body_battery_high"] == 88
    assert out["avg_stress_level"] == 28


def test_normalize_body_battery_stress_partial_stress() -> None:
    out = normalize_body_battery_stress("2026-01-10", None, {}, None)
    assert out["date"] == "2026-01-10"
    assert out["body_battery_high"] is None
    assert out["avg_stress_level"] is None


def test_normalize_training() -> None:
    out = normalize_training(
        "2026-01-10", SYNTH_READINESS, SYNTH_DAILY_STATUS, SYNTH_TRAINING_STATUS
    )
    assert out["training_readiness_score"] == 72
    assert out["vo2_max"] == 49.0


def test_normalize_training_realistic_nested_and_list_shapes() -> None:
    out = normalize_training(
        "2026-11-13",
        REAL_TRAINING_READINESS_LIST,
        REAL_DAILY_TRAINING_STATUS_LIST,
        REAL_TRAINING_STATUS_AGGREGATED,
    )
    assert out["training_readiness_score"] == 68
    assert out["training_status"] == "PRODUCTIVE_3"
    assert out["vo2_max"] == 48.0
    assert out["acute_load"] == 412
    assert out["chronic_load"] == 520


def test_normalize_training_aggregated_load_fallback() -> None:
    out = normalize_training(
        "2026-11-13",
        REAL_TRAINING_READINESS_LIST[1],
        {},
        REAL_TRAINING_STATUS_AGGREGATED,
    )
    assert out["acute_load"] == 715
    assert out["chronic_load"] == 701


def test_normalize_training_vo2_from_max_metrics_fallback() -> None:
    training_status = {"mostRecentVO2Max": None, "mostRecentTrainingStatus": None}
    out = normalize_training(
        "2026-11-13",
        REAL_TRAINING_READINESS_LIST[1],
        {},
        training_status,
        REAL_MAX_METRICS_LIST,
    )
    assert out["vo2_max"] == 47.0


def test_normalize_body_composition_grams() -> None:
    out = normalize_body_composition(SYNTH_WEIGHT)
    assert len(out["entries"]) == 2
    assert out["entries"][1]["weight_kg"] == 72.4
