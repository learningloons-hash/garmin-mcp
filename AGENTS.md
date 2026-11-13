# Agent rules for garmin-mcp

These rules apply to **every** coding agent (human or automated) working in this repository.

## Scope and milestones

1. Work **one milestone per branch/PR** after M1 (M2 client, M3 MCP, M4 deploy, M5 hook-up). Do not combine milestones in a single PR unless Mark explicitly asks.
2. Read `SPEC.md` before implementing; if the spec and code disagree, update the spec in the same PR when behavior is intentional.
3. **Never merge to `main`** and **never deploy** to Railway or any production environment. Mark alone merges and deploys.

## Security and privacy

1. **Never commit** secrets, `.env` contents, Garmin OAuth token files, or real Garmin API responses containing personal health data.
2. **Never** add real credentials to tests, fixtures, or CI. Use mocks, VCR-style recordings with redacted bodies, or synthetic data only.
3. **Tools stay strictly read-only** at the MCP layer and in the Garmin client (no calls that create, update, or delete Garmin data).

## Dependencies and cost

1. Keep **dependencies minimal** and **version-pinned** in `pyproject.toml` (runtime and dev).
2. **Do not** add paid services, SaaS APIs that require payment, or dependencies that need commercial licenses unless Mark approves in writing in the issue/PR.
3. Prefer stdlib and existing stack (`mcp`, `garminconnect`, `pytest`, `ruff`) over new libraries.

## Testing and quality

1. Run **`ruff check`** and **`pytest`** before pushing. Fix failures; do not disable rules without Mark’s approval.
2. **Do not edit** anything under `tests/acceptance/` except as directed by the independent tester. That directory is reserved for acceptance/smoke tests Mark or a separate agent owns.
3. Unit tests must run **without network** to Garmin by default.

## Honesty

1. In PR descriptions and handoff notes, **report what was verified** (commands run, tests passed) and **what was not** (e.g. no live Garmin call, no Railway deploy).
2. Do not claim M3/M4 behavior is done when only scaffolding exists.

## Git hygiene

1. Small, focused commits with clear messages.
2. No force-push to shared branches unless Mark requests it.
3. Do not revert Mark’s manual changes without coordination.

## When stuck

1. Document blockers in the PR (API drift, MFA edge cases, SDK API changes).
2. Prefer spec updates and TODOs in code over silent guessing about Garmin field names.
