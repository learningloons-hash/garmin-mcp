"""HTTP entry point: Streamable MCP on /mcp, health on /health."""

from __future__ import annotations

import logging
import os

import uvicorn

from garmin_mcp.garmin_client import get_garmin_client
from garmin_mcp.mcp_app import build_http_app, create_mcp_server
from garmin_mcp.mcp_auth import require_mcp_api_key_or_exit

logger = logging.getLogger(__name__)


def build_app():
    """ASGI app for uvicorn (also used in tests)."""
    api_key = require_mcp_api_key_or_exit()
    client = get_garmin_client()
    mcp = create_mcp_server(client=client)
    # HOST: uvicorn bind address. MCP_TRANSPORT_HOST: SDK streamable-http host knob
    # (0.0.0.0 disables DNS-rebinding Host checks so Railway's rewritten Host works).
    transport_host = os.environ.get("MCP_TRANSPORT_HOST", "0.0.0.0")
    return build_http_app(mcp, api_key, transport_host=transport_host)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    app = build_app()
    logger.info("Listening on %s:%s (MCP /mcp, health /health)", host, port)
    uvicorn.run(app, host=host, port=port, log_level=os.environ.get("LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()
