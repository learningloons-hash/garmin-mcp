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


def test_normalize_daily_summary() -> None:
    out = normalize_daily_summary("2026-01-10", SYNTH_SUMMARY)
    assert out["steps"] == 9000
    assert out["resting_hr_bpm"] == 55


def test_normalize_sleep() -> None:
    out = normalize_sleep("2026-01-10", SYNTH_SLEEP)
    assert out["sleep_score"] == 80
    assert out["duration_asleep_sec"] == 25200


def test_normalize_hrv() -> None:
    out = normalize_hrv("2026-01-10", SYNTH_HRV)
    assert out["overnight_hrv_ms"] == 48.5
    assert out["status"] == "balanced"


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


def test_normalize_body_composition_grams() -> None:
    out = normalize_body_composition(SYNTH_WEIGHT)
    assert len(out["entries"]) == 2
    assert out["entries"][1]["weight_kg"] == 72.4
