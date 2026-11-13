"""One-time interactive MFA bootstrap for Garmin OAuth tokens."""

from __future__ import annotations

import getpass
import logging
import sys

from garminconnect import Garmin

from garmin_mcp.config import GarminSettings
from garmin_mcp.errors import map_library_exception
from garmin_mcp.redact import redact_secrets

logger = logging.getLogger(__name__)

BOOTSTRAP_HELP = """\
Garmin MFA bootstrap
--------------------
Loads GARMIN_EMAIL, GARMIN_PASSWORD, and GARMINTOKENS from the environment.

Writes OAuth tokens to GARMINTOKENS so the server can start without an
interactive MFA prompt. With tokens on a persistent volume, you typically only
need this again when tokens expire or are revoked.

Run: python -m garmin_mcp.bootstrap
"""


def main(argv: list[str] | None = None) -> int:
    _ = argv
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(BOOTSTRAP_HELP)

    settings = GarminSettings.from_env()
    try:
        settings.validate_for_login()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    token_dir = settings.token_dir
    token_dir.mkdir(parents=True, exist_ok=True)

    password = settings.password or getpass.getpass("Garmin password: ")

    api = Garmin(settings.email, password, return_on_mfa=True)
    try:
        status, client_state = api.login(tokenstore=str(token_dir))
    except Exception as exc:
        mapped = map_library_exception(exc)
        print(redact_secrets(str(mapped)), file=sys.stderr)
        return 1

    if status == "needs_mfa":
        print(
            "Garmin sent an MFA challenge. Enter the code from your email, SMS, or authenticator."
        )
        code = input("MFA code: ").strip()
        if not code:
            print("MFA code is required.", file=sys.stderr)
            return 1
        try:
            api.resume_login(client_state, code)
        except Exception as exc:
            mapped = map_library_exception(exc)
            print(redact_secrets(str(mapped)), file=sys.stderr)
            return 1

    try:
        api.client.dump(str(token_dir))
    except Exception as exc:
        logger.warning("Token dump failed: %s", redact_secrets(str(exc)))

    print(f"Tokens saved under {token_dir}")
    print(
        "The server should load these tokens on startup and only re-login with "
        "GARMIN_EMAIL/GARMIN_PASSWORD if tokens are missing or invalid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
