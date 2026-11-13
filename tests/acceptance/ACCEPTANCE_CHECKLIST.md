# M2 Garmin client — acceptance checklist

Independent review of PR #1 (`m2-garmin-client`, commit `c8c54ae`). Status as
of this review; see the independent tester's full report for details.

## Verified correct (via real `garminconnect==0.3.20`, not just hand-rolled fakes)

- [x] Non-interactive MFA required -> raises `MfaRequiredError` pointing to
      `python -m garmin_mcp.bootstrap`, via the *actual* exception path the
      real library takes when `return_on_mfa=False`/`prompt_mfa=None`.
      (`tests/acceptance/test_mfa_real_path.py`)
- [x] Bad credentials (real 401 "Incorrect email or password" message) stop
      after exactly 1 login attempt, no retry storm, `_bad_credentials` flag
      set so subsequent calls short-circuit without hitting the network again.
      (`tests/acceptance/test_bad_credentials_real_path.py::test_bad_credentials_stops_after_one_attempt`)
- [x] Password is never present in the public-facing error string, even when
      the upstream error text happens to echo it back.
      (`test_public_error_never_leaks_password`)
- [x] Rate limit on login (`GarminConnectTooManyRequestsError`) is not
      retried (existing `tests/test_garmin_client.py::test_login_rate_limited_not_retried`).
- [x] Token directory is created/tightened to `0o700` before every login
      attempt, including the normal "tokens already valid" path (existing
      `tests/test_garmin_client.py::test_token_dir_permissions`,
      `tests/test_tokens_fs.py`).
- [x] No write/modify/delete Garmin API calls anywhere reachable from `src/`
      — every `api.*` call is `get_*`, `login`, or `resume_login`. Confirmed
      by diffing against the full list of mutating methods in the installed
      `garminconnect` package (`add_*`, `delete_*`, `update_*`, `set_*`,
      `create_*`, `upload_*`, `remove_*`).
- [x] No secrets, real tokens, or real personal data in the working tree or
      in `git log -p` across all commits on this branch. `.env.example` has
      empty placeholder values; `.gitignore` excludes `.env*`, token/garth
      directories, and OAuth JSON files.
- [x] `normalize_*` functions degrade gracefully (no crash, sensible
      `None`s) under empty dicts, missing nested keys, and documented
      fallback-key variants (`weightSummaries` vs `dateWeightList`, `avgHR`
      vs `averageHR`, flat vs `dailySleepDTO`-wrapped sleep payloads, etc).
      (`tests/acceptance/test_normalize_malformed.py`, 21 new cases, all pass
      against the current `src/garmin_mcp/normalize.py` unchanged.)

## BLOCKER — confirmed by a failing (xfail) regression test

- [ ] **Retry-exhaustion mistypes the final exception.** When an auth
      failure's text doesn't match any of the three hard-coded "permanent"
      markers in `_is_permanent_auth_failure`
      (`src/garmin_mcp/garmin_client.py:278-282`), `_login_with_backoff`
      exhausts all 3 attempts and then does
      `raise map_library_exception(last_exc) from last_exc`
      (`garmin_client.py:144`) where `last_exc` is *already* a proper
      `AuthFailureError`. `map_library_exception` doesn't recognize internal
      `GarminMcpError`/`AuthFailureError` instances (it only pattern-matches
      `garminconnect`/stdlib exception types) and falls through to its
      catch-all, re-wrapping the error as a generic
      `GarminMcpError("Unexpected Garmin client error (AuthFailureError).")`.
      The specific `auth_failure` error code/type is lost for any caller
      (e.g. a future M3 MCP tool layer) that branches on
      `isinstance(exc, AuthFailureError)` to give "check your credentials"
      guidance instead of a generic error.
      Reproduced in `tests/acceptance/test_bad_credentials_real_path.py::test_ambiguous_auth_failure_preserves_type_after_retry_exhaustion`
      (marked `xfail(strict=True)` — will flip to a hard failure, alerting
      the team, if someone "fixes" this without actually fixing it, and will
      start failing the xfail-strict check once genuinely fixed, signalling
      it's time to remove the marker).

## Weak/misleading existing test coverage (not blockers, but should be fixed)

- [ ] `tests/test_garmin_client.py::test_mfa_raises_bootstrap_hint` exercises
      the `status == "needs_mfa"` tuple-return branch in `_perform_login`
      (`garmin_client.py:158-159`) via a `FakeGarmin` that returns that tuple
      directly. The *real* `garminconnect` library only ever returns that
      tuple when `return_on_mfa=True` — and `garmin_client.py:151` always
      sets `return_on_mfa = False`. So, with the client's actual
      configuration, that branch is unreachable in production, and the
      existing test gives false confidence: it doesn't test the code path
      MFA actually takes (an exception, handled by the *other* branch at
      `garmin_client.py:160-164`). See
      `tests/acceptance/test_mfa_real_path.py` for the real-path version.
- [ ] `tests/test_garmin_client.py::test_bad_credentials_no_retry_storm` sets
      `client._bad_credentials = True` directly and asserts the (trivial)
      short-circuit guard at the top of `ensure_session()` works. It never
      calls `_is_permanent_auth_failure()` or drives the retry loop with a
      realistic error message, so a regression in the marker strings (e.g.
      a future `garminconnect` wording change) would not be caught. See
      `tests/acceptance/test_bad_credentials_real_path.py` for coverage via
      the real message text and the real retry loop.
- [ ] Every single test in `tests/test_garmin_client.py` injects
      `api_factory=FakeGarmin` (or a subclass), so the default
      `api_factory` lambda — `lambda email, password: Garmin(email,
      password, retry_attempts=0)` — and its interaction with the *actual*
      `garminconnect.Garmin` class/constructor signature is never exercised
      by the unit suite. `FakeGarmin.__init__` doesn't even accept the
      `retry_attempts` kwarg the real factory passes, which this gap papers
      over. This review's acceptance tests close part of that gap by using
      the real default `api_factory` and patching only the low-level SSO
      strategy chain.
- [ ] `tests/test_normalize.py` only ever feeds each `normalize_*` function
      a single, complete synthetic payload; none of the missing-field /
      fallback-key / malformed-shape branches visible in
      `src/garmin_mcp/normalize.py` (e.g. `weightSummaries` fallback,
      `avgHR` fallback, flat-vs-DTO sleep shape, `hrv=None`) were previously
      tested. `tests/acceptance/test_normalize_malformed.py` adds 21 cases;
      all pass against the unmodified normalizer code (no bugs found there,
      just previously-unverified behavior).

## Nits (not blockers)

- `GarminSettings.validate_for_login()` runs *before* any token-load
  attempt in `_login_with_backoff` (`garmin_client.py:110`), so if
  `GARMIN_EMAIL`/`GARMIN_PASSWORD` were ever unset while valid cached tokens
  exist, the client would hard-fail instead of using the tokens (the real
  `garminconnect.login()` would have happily used tokens alone). Not a
  practical issue today since SPEC.md resolves to keep both env vars set for
  the service's lifetime, but worth a comment if that assumption ever
  changes.
- `map_library_exception`'s blanket `isinstance(exc, KeyError | TypeError |
  ValueError)` -> `UpstreamChangedError` mapping also catches the plain
  `ValueError` from `GarminSettings.validate_for_login()` (missing
  credentials), mislabeling a config/deploy error as "upstream API may have
  changed." Confusing for whoever debugs a missing-secret deploy, not a
  security issue.
- `tokens_fs.ensure_token_dir()`'s `path.chmod(0o700)` follows symlinks (the
  stdlib default). If `GARMINTOKENS` ever pointed at a path where a symlink
  could be planted by another local process before the server starts, this
  would chmod the symlink's target rather than detecting/rejecting the
  symlink. Low severity for this single-tenant, Railway-volume deployment,
  but worth noting since the vendored `garminconnect` library has explicit
  anti-symlink handling for its own token files (see its `sso.py` comments)
  and this repo's own `ensure_token_dir` does not mirror that care.
