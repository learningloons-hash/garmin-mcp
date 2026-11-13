"""Realistic Garmin API payload shapes (synthetic values, not user data)."""

# Date-only local start placeholder; GMT ms holds the instant.
REAL_SLEEP_DATE_ONLY_START = {
    "dailySleepDTO": {
        "calendarDate": "2026-11-13",
        "sleepTimeSeconds": 28380,
        "sleepStartTimestampLocal": "2026-11-13",
        "sleepStartTimestampGMT": 1762991580000,
        "sleepEndTimestampLocal": 1763018760000,
        "sleepScores": {"overall": {"value": 78}},
    }
}

REAL_HRV_NIGHT = {
    "hrvSummary": {
        "calendarDate": "2026-11-13",
        "lastNightAvg": 51.2,
        "weeklyAvg": 49.0,
        "status": "balanced",
        "feedbackPhrase": "HRV_NORMAL",
    },
    "hrvReadings": [{"hrvValue": 42, "readingTimeGMT": 1762993200000}],
}

REAL_MAX_METRICS_LIST = [
    {
        "userId": 10001,
        "generic": {"vo2MaxValue": 47.0, "vo2MaxPreciseValue": 46.7},
        "cycling": None,
    }
]

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
