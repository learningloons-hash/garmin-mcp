# garmin-mcp — Technical Specification

## Goal

Build a small, personal, **read-only** MCP (Model Context Protocol) server in Python that exposes Mark Lee’s own Garmin Connect data to his AI assistant (Grok Bot). Transport is **remote Streamable HTTP** (official MCP Python SDK / FastMCP). The server runs as a single always-on service on **Railway**.

Data access uses the open-source [`garminconnect`](https://github.com/cyberjunky/python-garminconnect) library (PyPI: `garminconnect`), which calls Garmin’s **unofficial** HTTP APIs.

## Non-goals

- **No write or modify operations** on Garmin (no uploading activities, changing settings, sending messages, etc.).
- **No multi-user** support; one Garmin account, one API key holder.
- **No public or unauthenticated access** to health data; bearer token required on MCP traffic (except `/health`).
- **No** syncing to a database, analytics warehouse, or third-party fitness apps (this milestone and product scope).
- **No** billing, subscriptions, or paid third-party services inside the repo.

## Architecture

```text
┌─────────────┐     HTTPS + Bearer (MCP_API_KEY)     ┌──────────────────┐
│  Grok Bot   │ ───────────────────────────────────► │  garmin-mcp      │
│  (client)   │         MCP Streamable HTTP          │  (FastMCP)       │
└─────────────┘                                      └────────┬─────────┘
                                                                │
                                                    garminconnect + garth
                                                                │
                                                                ▼
                                                    ┌──────────────────┐
                                                    │ Garmin Connect   │
                                                    │ (unofficial API) │
                                                    └──────────────────┘
```

Layers (by milestone):

| Layer | Responsibility |
|-------|----------------|
| **MCP** (M3) | Tool definitions, input validation, compact JSON outputs, auth middleware, `/health`. |
| **Garmin client** (M2) | Login, token persistence/refresh, typed fetch helpers, error mapping. |
| **Deploy** (M4) | Docker/Nixpacks, `PORT`, volume for tokens, runbook, smoke tests. |
| **Hook-up** (M5) | Mark configures custom connector in his bot. |

## Environment variables (names only)

| Name | Purpose |
|------|---------|
| `GARMIN_EMAIL` | Garmin Connect account email (M2 login). |
| `GARMIN_PASSWORD` | Garmin Connect password (Railway secret; used when tokens are missing or invalid). |
| `GARMINTOKENS` | Filesystem path for persisted OAuth token store (default `/data/garth`; Railway volume). |
| `MCP_API_KEY` | Shared secret; clients must send `Authorization: Bearer <MCP_API_KEY>`. |
| `PORT` | HTTP listen port (Railway sets this). |

Optional future vars (not required until implemented): log level, request timeouts, rate-limit knobs.

## Security model

1. **MCP surface**: Every MCP request (except `/health`) requires a valid bearer token equal to `MCP_API_KEY`; otherwise **401** with no data leakage.
2. **Secrets**: Live only in environment or Railway secrets/volume; never in git, tests, or logs.
3. **Tokens**: OAuth artifacts stored under `GARMINTOKENS`; directory ignored by git; treat volume backups as sensitive as passwords.
4. **Network**: HTTPS only in production; single-tenant; no OAuth for MCP clients (static API key is sufficient for personal use).
5. **Read-only**: Tool layer must not call Garmin endpoints that mutate user data (library calls audited in M2/M3).

## Risks (Garmin unofficial API)

- Endpoints and response shapes can **change without notice**; the server may break until `garminconnect` or this repo is updated.
- Use may **conflict with Garmin’s Terms of Service**; this is a personal, single-user integration with no Garmin partnership.
- **Rate limiting** or account lockouts are possible if traffic is abusive; keep request volume modest.
- **MFA/2FA**: Non-interactive server login fails with a clear error if MFA is required; Mark runs `python -m garmin_mcp.bootstrap` once. With tokens on a volume, MFA is not needed again until tokens expire.

## Garmin client auth (M2+)

On startup or first API use:

1. Load tokens from `GARMINTOKENS` (default `/data/garth`).
2. If missing, invalid, or rejected by Garmin, log in with `GARMIN_EMAIL` / `GARMIN_PASSWORD` and save tokens back to `GARMINTOKENS`.
3. Token refresh is handled by `garminconnect` / garth transparently; on auth failure the client may re-login with exponential backoff (no retry storms when credentials are definitively wrong).
4. If Garmin presents MFA during non-interactive login, return `mfa_required` and instruct Mark to run `python -m garmin_mcp.bootstrap`.

`GARMIN_EMAIL` and `GARMIN_PASSWORD` remain Railway secrets for the lifetime of the service (Mark’s decision).

## MCP tools (read-only, proposed)

All tools return **compact JSON** with explicit **units**. Errors are structured (see Error handling).

### `get_recent_activities`

**Input**

```json
{ "days": 7, "limit": 20 }
```

- `days` (int, 1–90, default 7): lookback window.
- `limit` (int, 1–50, default 20): max activities returned.

**Output**

```json
{
  "activities": [
    {
      "activity_id": 12345678901,
      "name": "Morning Run",
      "type": "running",
      "start_time_local": "2026-11-12T07:15:00",
      "duration_sec": 2847,
      "distance_m": 5120.5,
      "avg_hr_bpm": 142,
      "calories_kcal": 410
    }
  ]
}
```

### `get_activity_detail`

**Input**

```json
{ "activity_id": 12345678901 }
```

`activity_id` must be a positive integer up to **10^13** (inclusive); larger values are rejected at the MCP layer.

**Output** (subset; full detail trimmed for token size in implementation)

```json
{
  "activity_id": 12345678901,
  "name": "Morning Run",
  "type": "running",
  "start_time_local": "2026-11-12T07:15:00",
  "duration_sec": 2847,
  "distance_m": 5120.5,
  "elevation_gain_m": 42,
  "avg_hr_bpm": 142,
  "max_hr_bpm": 168,
  "calories_kcal": 410,
  "avg_pace_sec_per_km": 333
}
```

### `get_daily_summary`

**Input**

```json
{ "date": "2026-11-12" }
```

**Output**

```json
{
  "date": "2026-11-12",
  "steps": 10432,
  "calories_kcal": 2180,
  "resting_hr_bpm": 54
}
```

### `get_sleep`

**Input**

```json
{ "date": "2026-11-12" }
```

**Output**

```json
{
  "date": "2026-11-12",
  "sleep_start_local": "2026-11-11T22:48:00",
  "sleep_end_local": "2026-11-12T06:12:00",
  "duration_asleep_sec": 25200,
  "deep_sleep_sec": 5400,
  "light_sleep_sec": 12600,
  "rem_sleep_sec": 5100,
  "awake_sec": 1200,
  "sleep_score": 78
}
```

### `get_hrv`

**Input**

```json
{ "date": "2026-11-12" }
```

**Output**

```json
{
  "date": "2026-11-12",
  "overnight_hrv_ms": 52,
  "status": "balanced"
}
```

(`status` values depend on Garmin payload; map to stable enums where possible.)

### `get_body_battery_and_stress`

**Input**

```json
{ "date": "2026-11-12" }
```

**Output**

```json
{
  "date": "2026-11-12",
  "body_battery_high": 92,
  "body_battery_low": 18,
  "avg_stress_level": 28,
  "rest_stress_minutes": 180
}
```

### `get_training_readiness_and_status`

**Input**

```json
{ "date": "2026-11-12" }
```

**Output**

```json
{
  "date": "2026-11-12",
  "training_readiness_score": 75,
  "training_status": "productive",
  "vo2_max": 48.2,
  "acute_load": 320,
  "chronic_load": 295
}
```

Field availability varies by device/account; missing fields are omitted or `null` with a note in tool description.

### `get_body_composition`

**Input**

```json
{ "start_date": "2026-10-01", "end_date": "2026-11-12" }
```

**Output**

```json
{
  "entries": [
    {
      "date": "2026-11-10",
      "weight_kg": 72.4,
      "bmi": 22.1,
      "body_fat_percent": 18.5
    }
  ]
}
```

### `GET /health`

No auth. Returns service liveness only, e.g. `{"status": "ok"}` — **no Garmin data**.

## Error handling

Errors returned to the MCP client should be **clear and actionable** (no stack traces in production responses).

| Condition | Client-facing behavior |
|-----------|-------------------------|
| Missing/invalid `MCP_API_KEY` | HTTP 401, message: unauthorized. |
| Garmin session missing/expired | Tool error: re-run MFA bootstrap or check `GARMINTOKENS`. |
| Garmin auth failure (bad password) | Tool error: check credentials (deploy-time only). |
| Rate limit / HTTP 429 | Tool error: retry later; optional backoff in client. |
| Endpoint/parse failure (API drift) | Tool error: upstream schema change; log details server-side. |
| Invalid tool input | Validation error with field hints. |

## Milestones and acceptance criteria

### M1 — Spec, agent rules, skeleton (this repo baseline)

- `SPEC.md`, `AGENTS.md`, `pyproject.toml`, package layout, trivial tests, CI (ruff + pytest).
- **Acceptance**: `ruff check` and `pytest` pass; no Garmin network calls; no secrets in tree.

### M2 — Garmin client module (merged)

- Env-based login with retained `GARMIN_EMAIL` / `GARMIN_PASSWORD`; token dir `GARMINTOKENS` (default `/data/garth`); re-login on failure; MFA bootstrap CLI.
- Typed fetch functions backing each planned tool; unit tests with mocks (no real credentials).
- **Acceptance**: `ruff` + `pytest` pass offline; README bootstrap section; no MCP server yet.

### M3 — MCP server layer (merged)

- `MCPServer` (mcp 2.x SDK) + Streamable HTTP on `/mcp`; uvicorn on `0.0.0.0:$PORT`.
- Eight read-only tools wrapping M2 `fetch_*` helpers; bearer `MCP_API_KEY` on `/mcp`; unauthenticated `/health`.
- **Acceptance**: `ruff` + `pytest` pass offline with mocked Garmin client; no write tools; no live Garmin in CI.

### M4 — Railway deploy (in review)

- `Dockerfile` (Python 3.12.8), `railway.json` healthcheck `/health`, volume at `/data` for `GARMINTOKENS=/data/garth`.
- `docs/DEPLOY.md` runbook; `scripts/smoke_test.py` for Mark (`MCP_URL` + `MCP_API_KEY`).
- **Acceptance**: Mark can deploy from `main` without agent merging; CI green; no agent deploy or secrets in git.

### M5 — Hook-up

- Mark adds connector URL + key to Grok Bot; manual end-to-end validation.
- **Acceptance**: Mark confirms at least one tool returns live data in chat.

## Open decisions (for Mark)

- Exact **MCP SDK** pin and streamable HTTP mount path (finalize in M3 against SDK docs).
- How aggressively to **trim** activity detail payloads for LLM context limits.
- **Resolved:** retain `GARMIN_PASSWORD` on Railway; default `GARMINTOKENS=/data/garth`.
