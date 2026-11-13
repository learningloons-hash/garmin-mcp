"""Redact secrets from log and error strings."""

from __future__ import annotations

import re
from re import Pattern

_SENSITIVE_ENV_NAMES = (
    "GARMIN_EMAIL",
    "GARMIN_PASSWORD",
    "MCP_API_KEY",
)

# Bearer tokens, common OAuth-ish keys, and inline JSON token blobs.
_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"(?i)(password\s*[=:]\s*)(\S+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\"refresh_token\"\s*:\s*\")([^\"]+)(\")"), r'\1[REDACTED]\3'),
    (re.compile(r"(?i)(\"access_token\"\s*:\s*\")([^\"]+)(\")"), r'\1[REDACTED]\3'),
    (re.compile(r"(?i)(tokenstore\s*[=:]\s*)(\S+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(mfa[-_ ]?code)\s*[=:]\s*(\S+)"), r"\1=[REDACTED]"),
    (
        re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9\-._~+/]+=*)\b"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"\b([A-Za-z0-9\-_]{32,})(\.[A-Za-z0-9\-_]{16,})+\b"
        ),
        "[REDACTED]",
    ),
]


def redact_secrets(text: str, extra_values: tuple[str, ...] = ()) -> str:
    """Remove passwords, tokens, and known env values from free text."""
    import os

    redacted = text
    for pattern, repl in _PATTERNS:
        redacted = pattern.sub(repl, redacted)

    candidates: list[str] = list(extra_values)
    for name in _SENSITIVE_ENV_NAMES:
        val = os.environ.get(name)
        if val:
            candidates.append(val)

    for value in candidates:
        if not value:
            continue
        redacted = redacted.replace(value, "[REDACTED]")

    return redacted
