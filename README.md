# garmin-mcp

Personal, **read-only** [MCP](https://modelcontextprotocol.io/) server (Python, Streamable HTTP) that exposes your own Garmin Connect data to an AI assistant. Planned hosting: Railway as a single always-on service.

**Status:** Milestone 3 — MCP HTTP server (Streamable HTTP on `/mcp`, eight read-only tools, bearer auth). M2 Garmin client is merged; Railway deploy is M4.

## Documentation

- [`SPEC.md`](SPEC.md) — architecture, tools, risks, milestones
- [`AGENTS.md`](AGENTS.md) — rules for coding agents on this repo

## Requirements

- Python 3.12+

## Setup (developers)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

```bash
ruff check .
pytest
```

## Environment variables

See [`.env.example`](.env.example).

| Variable | Purpose |
|----------|---------|
| `GARMIN_EMAIL` | Garmin Connect email (secret) |
| `GARMIN_PASSWORD` | Garmin Connect password (secret; used when tokens fail) |
| `GARMINTOKENS` | Directory for OAuth token files (default `/data/garth`) |
| `MCP_API_KEY` | Bearer token for MCP clients (M3+) |
| `PORT` | HTTP port (M3+/Railway) |
| `HOST` | Uvicorn bind address (default `0.0.0.0`) |
| `MCP_TRANSPORT_HOST` | MCP SDK streamable-http host knob (default `0.0.0.0`; keep `0.0.0.0` on Railway so rewritten `Host` headers are not rejected) |

## Garmin session and MFA bootstrap

The client loads tokens from `GARMINTOKENS` on first use. If tokens are missing or invalid, it logs in with `GARMIN_EMAIL` / `GARMIN_PASSWORD` and saves new tokens. With a persistent volume, you usually only need MFA once.

When Garmin requires 2FA during **non-interactive** server login, login fails with an error pointing at this command:

```bash
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=...
export GARMINTOKENS=/data/garth   # or a local path
python -m garmin_mcp.bootstrap
```

The bootstrap CLI prompts for the MFA code interactively and writes tokens to `GARMINTOKENS`. After that, the running service should start without MFA until tokens expire.

## Run the MCP server (M3)

```bash
export MCP_API_KEY='...'   # at least 32 characters
export GARMIN_EMAIL=...
export GARMIN_PASSWORD=...
export GARMINTOKENS=./data/garth
export PORT=8000
python -m garmin_mcp.server
```

- Streamable HTTP MCP endpoint: `POST /mcp` (requires `Authorization: Bearer $MCP_API_KEY`)
- Liveness: `GET /health` → `{"status":"ok"}` (no auth, no Garmin I/O)

## Client API (library)

```python
from garmin_mcp.garmin_client import get_garmin_client

client = get_garmin_client()
client.fetch_daily_summary("2026-11-12")
```

Available fetch methods: `fetch_recent_activities`, `fetch_activity_detail`, `fetch_daily_summary`, `fetch_sleep`, `fetch_hrv`, `fetch_body_battery_and_stress`, `fetch_training_readiness_and_status`, `fetch_body_composition`.

## License

MIT (see package metadata in `pyproject.toml`).
