#!/usr/bin/env python3
"""Print key structure (types only) of raw Garmin API responses for one date.

Requires GARMIN_EMAIL, GARMIN_PASSWORD, and optional GARMINTOKENS (default /data/garth).
Does not print response values — only field names and types.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from datetime import date
from typing import Any

from garminconnect import Garmin

from garmin_mcp.config import GarminSettings
from garmin_mcp.shape_dump import describe_value_shape
from garmin_mcp.tokens_fs import ensure_token_dir


def _login() -> Garmin:
    settings = GarminSettings.from_env()
    settings.validate_for_login()
    ensure_token_dir(settings.token_dir)
    client = Garmin(settings.email, settings.password)
    client.login(tokenstore=str(settings.token_dir))
    return client


def _safe_shape(label: str, fetch: Callable[[], Any]) -> dict[str, Any]:
    try:
        raw = fetch()
    except Exception as exc:
        return {label: {"error_type": type(exc).__name__}}
    return {label: describe_value_shape(raw)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today().isoformat(),
        help="Calendar date YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args()
    cdate = args.date

    api = _login()
    sections = [
        _safe_shape("get_hrv_data", lambda: api.get_hrv_data(cdate)),
        _safe_shape("get_training_readiness", lambda: api.get_training_readiness(cdate)),
        _safe_shape("get_training_status", lambda: api.get_training_status(cdate)),
        _safe_shape("get_max_metrics", lambda: api.get_max_metrics(cdate)),
        _safe_shape("get_sleep_data", lambda: api.get_sleep_data(cdate)),
    ]
    out: dict[str, Any] = {"date": cdate}
    for part in sections:
        out.update(part)

    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
