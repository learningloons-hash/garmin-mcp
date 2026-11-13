"""Environment configuration for the Garmin client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TOKEN_DIR = "/data/garth"


@dataclass(frozen=True)
class GarminSettings:
    email: str
    password: str
    token_dir: Path

    @classmethod
    def from_env(cls) -> GarminSettings:
        email = os.environ.get("GARMIN_EMAIL", "").strip()
        password = os.environ.get("GARMIN_PASSWORD", "").strip()
        token_raw = os.environ.get("GARMINTOKENS", DEFAULT_TOKEN_DIR).strip()
        token_dir = Path(token_raw or DEFAULT_TOKEN_DIR)
        return cls(email=email, password=password, token_dir=token_dir)

    def validate_for_login(self) -> None:
        if not self.email or not self.password:
            raise ValueError(
                "GARMIN_EMAIL and GARMIN_PASSWORD must be set for Garmin login."
            )
