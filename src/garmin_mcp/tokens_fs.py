"""Filesystem helpers for the Garmin OAuth token directory."""

from __future__ import annotations

from pathlib import Path

TOKEN_DIR_MODE = 0o700


def ensure_token_dir(path: Path) -> Path:
    """Create token directory with restricted permissions; tighten if it exists."""
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(TOKEN_DIR_MODE)
    return path
