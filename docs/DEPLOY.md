# Deploy garmin-mcp to Railway

Mark deploys this repo personally. Agents do **not** merge or click deploy for you.

## What you are running

- **Docker** image (Python **3.12.8**) running `python -m garmin_mcp.server`
- Listens on **`0.0.0.0:$PORT`** (Railway sets `PORT`)
- **`GET /health`** — no auth, no Garmin calls
- **`POST /mcp`** — Streamable HTTP MCP (requires `Authorization: Bearer <MCP_API_KEY>`)
- OAuth token files under **`GARMINTOKENS`** (default **`/data/garth`** on a persistent volume)

## Prerequisites

- Garmin Connect account (email + password)
- [Railway](https://railway.com/) account (Hobby plan is enough for a single always-on web service; check Railway’s current pricing page for your region—no paid third-party services are required in this repo)
- Railway CLI optional but useful for MFA bootstrap: `npm i -g @railway/cli` or see Railway docs

## Step 1 — Create the Railway project

Create a **new, dedicated** Railway project named **`garmin-mcp`** (do not reuse an existing project or service from another app).

1. In Railway: **New Project** → name it **`garmin-mcp`** → **Deploy from GitHub repo** → `learningloons-hash/garmin-mcp` (branch **`main`** after Mark merges M4).
2. Railway detects **`railway.json`** + **`Dockerfile`** and builds the container.

## Step 2 — Add a volume for Garmin tokens

Garmin OAuth tokens must survive redeploys.

1. Open the service → **Volumes** → **Add volume**
2. Mount path: **`/data`**
3. Leave **`GARMINTOKENS=/data/garth`** (default in Docker image and `DEFAULT_TOKEN_DIR` in code). The app creates `garth` with mode `0700` on first use.

**Garmin login is lazy:** the process starts without calling Garmin. With a new volume, **`/data/garth` stays empty** until the **first MCP tool call** that needs Garmin data (for example `get_daily_summary` in the smoke test). That call triggers login/token save using `GARMIN_EMAIL` / `GARMIN_PASSWORD`. **`GET /health` succeeds on boot** regardless—no Garmin network I/O. After tokens exist on the volume, later tool calls load them and usually avoid password login until tokens expire.

## Step 3 — Set service variables

In the service **Variables** tab (treat as secrets):

| Variable | Required | Example / notes |
|----------|----------|----------------|
| `GARMIN_EMAIL` | Yes | Garmin Connect login email |
| `GARMIN_PASSWORD` | Yes | Garmin password (secret) |
| `MCP_API_KEY` | Yes | ≥ 32 characters; generate below |
| `GARMINTOKENS` | Recommended | `/data/garth` (matches volume) |
| `MCP_TRANSPORT_HOST` | Optional | Default `0.0.0.0` — keeps Railway’s rewritten `Host` header from HTTP 421 |
| `HOST` | Optional | Default `0.0.0.0` (uvicorn bind) |
| `LOG_LEVEL` | Optional | `info` |

Generate **`MCP_API_KEY`** locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into Railway **once**; store a copy in your password manager for Grok Bot / smoke tests. Never commit it.

Railway injects **`PORT`** automatically—do not set it unless Railway support asks you to.

## Step 4 — Generate a public domain

1. Service → **Settings** → **Networking** → **Generate domain** (e.g. `garmin-mcp-production.up.railway.app`)
2. Deploy must stay **healthy** (`/health` per `railway.json` health check)

## Step 5 — Verify `/health`

```bash
curl -sS "https://YOUR_DOMAIN.up.railway.app/health"
```

Expected: `{"status":"ok"}`

## Step 6 — Smoke test (authenticated MCP)

**Prerequisites:** a local clone of this repo and the package installed (includes `mcp`, `httpx2`, etc.):

```bash
cd garmin-mcp
pip install -e .
```

From a machine with network access (use the same `MCP_API_KEY` as Railway):

```bash
export MCP_URL="https://YOUR_DOMAIN.up.railway.app"
export MCP_API_KEY="your-long-secret-key"
python scripts/smoke_test.py
```

The tool call to `get_daily_summary` is typically the **first** Garmin login on a fresh deploy; allow time for that one-time auth.

Expected stdout shape (no secrets):

```text
OK health; 8 tools; get_daily_summary(YYYY-MM-DD) fields: [...]
```

The script also asserts unauthenticated `POST /mcp` returns **401**.

## MFA / first-time Garmin login

If Garmin requires MFA, **non-interactive** server login fails with an error pointing at the bootstrap CLI.

**Option A — `railway run` (interactive):**

```bash
railway link   # once, select project/service
railway variables set GARMIN_EMAIL=... GARMIN_PASSWORD=... GARMINTOKENS=/data/garth
railway run python -m garmin_mcp.bootstrap
```

Enter the MFA code when prompted. Tokens land on the mounted volume.

**Option B — Local bootstrap, then copy tokens:**

1. Locally: `export GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMINTOKENS=./local-garth`
2. `python -m garmin_mcp.bootstrap`
3. Upload the resulting token files into the Railway volume at `/data/garth` (Railway volume shell or one-off copy). Prefer Option A when possible.

After valid tokens exist on the volume, the running service should not need MFA again until tokens expire or are revoked.

## Rotate `MCP_API_KEY`

1. Generate a new key with the `secrets.token_urlsafe` command above.
2. Update Railway variable `MCP_API_KEY`.
3. Redeploy if required (variable change usually triggers a restart).
4. Update your MCP client (Grok Bot connector) to the new bearer token.
5. Remove the old key from any password manager entries.

## Cost note

This is a **single small Python web service** with one volume. On Railway’s **Hobby** plan, one always-on service typically fits personal use; you do not need Pro/Team features for this project. Exact usage and limits change—check [Railway pricing](https://railway.com/pricing) before relying on a specific dollar amount.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Crash loop on boot | Logs for `MCP_API_KEY must be set`; key length ≥ 32 |
| 401 on MCP tools | Client `Authorization: Bearer` matches Railway `MCP_API_KEY` |
| MFA / auth errors | Run bootstrap; confirm volume mounted at `/data` |
| 421 on `/mcp` | Ensure `MCP_TRANSPORT_HOST=0.0.0.0` (default) |
| Stale tokens | Delete token files on volume (careful) and re-login or re-bootstrap |

## Files in this repo

| File | Purpose |
|------|---------|
| `Dockerfile` | Production image, Python 3.12.8, healthcheck |
| `railway.json` | Railway build + `/health` health check path |
| `scripts/smoke_test.py` | Post-deploy verification (not run in CI against live Garmin) |
