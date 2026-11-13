
from garmin_mcp.redact import redact_secrets


def test_redact_password_and_tokens() -> None:
    raw = (
        'password=supersecret "refresh_token":"abc123xyz" '
        "Authorization: Bearer sk-live-abcdef"
    )
    out = redact_secrets(raw, extra_values=("supersecret",))
    assert "supersecret" not in out
    assert "abc123xyz" not in out
    assert "sk-live-abcdef" not in out
    assert "[REDACTED]" in out


def test_redact_short_password_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    assert redact_secrets("failed login for pw") == "failed login for [REDACTED]"


def test_redact_email_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "mark@example.com")
    assert "[REDACTED]" in redact_secrets("logged in as mark@example.com")


def test_redact_bearer_blob() -> None:
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sig"
    out = redact_secrets(f"Authorization: Bearer {token}")
    assert token not in out
