from pathlib import Path

from garmin_mcp.tokens_fs import TOKEN_DIR_MODE, ensure_token_dir


def test_ensure_token_dir_mode(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "garth"
    ensure_token_dir(target)
    assert target.is_dir()
    assert (target.stat().st_mode & 0o777) == TOKEN_DIR_MODE


def test_ensure_token_dir_tightens_existing(tmp_path: Path) -> None:
    target = tmp_path / "garth"
    target.mkdir(mode=0o755)
    ensure_token_dir(target)
    assert (target.stat().st_mode & 0o777) == TOKEN_DIR_MODE
