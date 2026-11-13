"""Helpers for running the real garmin-mcp ASGI app over a live TCP socket.

Not a test module itself (no ``test_`` functions) - imported by the
acceptance tests in this directory to drive the app through real HTTP,
rather than Starlette's in-process TestClient, per the M3 independent
review brief.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import uvicorn

from garmin_mcp.mcp_app import build_http_app, create_mcp_server


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LiveServer:
    """Runs the real ASGI app with uvicorn in a background thread."""

    def __init__(self, app: Any, *, bind_host: str = "127.0.0.1") -> None:
        self.bind_host = bind_host
        self.port = free_port()
        config = uvicorn.Config(
            app,
            host=bind_host,
            port=self.port,
            log_level="warning",
            lifespan="on",
        )
        self.server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self.server.run, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://{self.bind_host}:{self.port}"

    @property
    def mcp_url(self) -> str:
        return f"{self.base_url}/mcp"

    def start(self, timeout: float = 10.0) -> None:
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn server did not start in time")
            time.sleep(0.01)

    def stop(self, timeout: float = 10.0) -> None:
        self.server.should_exit = True
        self._thread.join(timeout=timeout)


@contextmanager
def running_app(
    client: Any,
    api_key: str,
    *,
    host: str = "0.0.0.0",
    bind_host: str = "127.0.0.1",
) -> Iterator[LiveServer]:
    """Build the real app (create_mcp_server + build_http_app) and serve it live."""
    mcp = create_mcp_server(client=client)
    app = build_http_app(mcp, api_key, host=host)
    live = LiveServer(app, bind_host=bind_host)
    live.start()
    try:
        yield live
    finally:
        live.stop()
