from pathlib import Path
from unittest.mock import MagicMock, patch

from garmin_mcp import bootstrap


def test_bootstrap_mfa_flow(tmp_path: Path, monkeypatch) -> None:
    token_dir = tmp_path / "tokens"
    monkeypatch.setenv("GARMIN_EMAIL", "user@example.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "secret-password-value")
    monkeypatch.setenv("GARMINTOKENS", str(token_dir))

    fake_api = MagicMock()
    fake_api.login.return_value = ("needs_mfa", {"state": 1})
    fake_api.client = MagicMock()

    with (
        patch.object(bootstrap, "Garmin", return_value=fake_api),
        patch("builtins.input", return_value="123456"),
    ):
        code = bootstrap.main()

    assert code == 0
    fake_api.resume_login.assert_called_once_with({"state": 1}, "123456")
    fake_api.client.dump.assert_called_once_with(str(token_dir))
