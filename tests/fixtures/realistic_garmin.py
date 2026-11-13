"""Realistic Garmin API payload shapes (synthetic values, not user data)."""

# Garmin sometimes sends a calendar-date midnight string for local start while the
# GMT field holds the real instant (ms epoch).
REAL_SLEEP_MIDNIGHT_STRING_START = {
    "dailySleepDTO": {
        "calendarDate": "2026-11-13",
        "sleepTimeSeconds": 28380,
        "sleepStartTimestampLocal": "2026-11-13T00:00:00",
        "sleepStartTimestampGMT": 1762991580000,
        "sleepEndTimestampLocal": 1763018760000,
        "sleepEndTimestampGMT": 1763018760000,
        "sleepScores": {"overall": {"value": 78}},
    }
}

REAL_TRAINING_READINESS_LIST = [
    {
        "calendarDate": "2026-11-13",
        "inputContext": "SCHEDULED",
        "score": 55,
        "level": "low",
    },
    {
        "calendarDate": "2026-11-13",
        "inputContext": "AFTER_WAKEUP_RESET",
        "score": 68,
        "level": "moderate",
    },
]

REAL_DAILY_TRAINING_STATUS_LIST = [
    {
        "calendarDate": "2026-11-13",
        "trainingStatus": 7,
        "trainingStatusFeedbackPhrase": "PRODUCTIVE_3",
        "primaryTrainingDevice": True,
        "dailyTrainingLoadAcute": 412,
        "dailyTrainingLoadChronic": 520,
    }
]

REAL_TRAINING_STATUS_AGGREGATED = {
    "userId": 10001,
    "mostRecentVO2Max": {
        "generic": {
            "calendarDate": "2026-11-12",
            "vo2MaxValue": 48.0,
            "vo2MaxPreciseValue": 47.8,
        },
        "cycling": None,
    },
    "mostRecentTrainingStatus": {
        "latestTrainingStatusData": {
            "3620729386": {
                "calendarDate": "2026-11-13",
                "trainingStatus": 7,
                "trainingStatusFeedbackPhrase": "PRODUCTIVE_3",
                "primaryTrainingDevice": True,
                "acuteTrainingLoadDTO": {
                    "dailyTrainingLoadAcute": 715,
                    "dailyTrainingLoadChronic": 701,
                    "acwrStatus": "OPTIMAL",
                },
            }
        }
    },
}
