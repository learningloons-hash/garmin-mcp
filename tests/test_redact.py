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
