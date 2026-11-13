"""Synthetic Garmin API payloads for offline tests (not real user data)."""

SYNTH_ACTIVITY = {
    "activityId": 990001,
    "activityName": "Test Run",
    "activityType": {"typeKey": "running"},
    "startTimeLocal": "2026-01-10T08:00:00",
    "duration": 1800.0,
    "distance": 5000.0,
    "averageHR": 140,
    "maxHR": 165,
    "calories": 350,
    "elevationGain": 25.0,
}

SYNTH_SUMMARY = {
    "totalSteps": 9000,
    "activeKilocalories": 450,
    "bmrKilocalories": 1600,
    "restingHeartRate": 55,
    "bodyBatteryHighestValue": 90,
    "bodyBatteryLowestValue": 20,
    "averageStressLevel": 30,
    "restStressDuration": 7200,
}

SYNTH_SLEEP = {
    "dailySleepDTO": {
        "sleepTimeSeconds": 25200,
        "deepSleepSeconds": 5000,
        "lightSleepSeconds": 12000,
        "remSleepSeconds": 6000,
        "awakeSleepSeconds": 1000,
        "sleepStartTimestampLocal": "2026-01-09T22:30:00",
        "sleepEndTimestampLocal": "2026-01-10T06:30:00",
        "sleepScores": {"overall": {"value": 80}},
    }
}

SYNTH_HRV = {"hrvSummary": {"lastNightAvg": 48.5, "status": "balanced"}}

SYNTH_BATTERY = [
    {
        "date": "2026-01-10",
        "bodyBatteryValuesArray": [[0, 25], [1, 88], [2, 40]],
    }
]

SYNTH_STRESS = {"averageStressLevel": 28, "restStressDuration": 10800}

SYNTH_READINESS = {"score": 72, "level": "high"}
SYNTH_DAILY_STATUS = {
    "trainingStatus": "productive",
    "acuteTrainingLoad": 300,
    "chronicTrainingLoad": 280,
}
SYNTH_TRAINING_STATUS = {"vo2Max": 49.0}

SYNTH_WEIGHT = {
    "dateWeightList": [
        {
            "calendarDate": "2026-01-09",
            "weight": 72.1,
            "bmi": 22.0,
            "bodyFat": 18.2,
        },
        {
            "calendarDate": "2026-01-10",
            "weight": 72400,
            "bmi": 22.1,
            "bodyFatPercentage": 18.0,
        },
    ]
}
