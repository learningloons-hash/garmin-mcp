from garmin_mcp.deploy_config import (
    EXPECTED_MCP_TOOL_NAMES,
    HEALTH_PATH,
    MCP_HTTP_PATH,
    RAILWAY_TOKEN_DIR,
    normalize_mcp_url,
)


def test_normalize_mcp_url() -> None:
    assert normalize_mcp_url("https://example.up.railway.app") == (
        "https://example.up.railway.app/mcp"
    )
    assert normalize_mcp_url("https://example.up.railway.app/mcp") == (
        "https://example.up.railway.app/mcp"
    )


def test_railway_token_dir_matches_default_garmin_setting() -> None:
    from garmin_mcp.config import DEFAULT_TOKEN_DIR

    assert RAILWAY_TOKEN_DIR == DEFAULT_TOKEN_DIR


def test_expected_tool_count() -> None:
    assert len(EXPECTED_MCP_TOOL_NAMES) == 8


def test_health_path_constant() -> None:
    assert HEALTH_PATH == "/health"
    assert MCP_HTTP_PATH == "/mcp"
