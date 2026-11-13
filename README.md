# garmin-mcp

Personal, **read-only** [MCP](https://modelcontextprotocol.io/) server (Python, Streamable HTTP) that exposes your own Garmin Connect data to an AI assistant. Hosted on Railway as a single always-on service.

**Status:** Milestone 1 — specification, agent rules, and project skeleton only. No Garmin login, data fetching, or MCP server yet.

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

See [`.env.example`](.env.example). Names only in repo; set real values in Railway or a local `.env` (gitignored).

## License

MIT (see package metadata in `pyproject.toml`).
