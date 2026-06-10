<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 01-control-plane-api
plan: 05
subsystem: api
tags: [fastapi, bootconfig, internal-router, asvs-l1, secret-hygiene, credential-seam, enumeration-resistance, source-ip-binding, integration-tests, WORK-03, ADR-0002]

# Dependency graph
requires:
  - phase: 01-control-plane-api (Plan 01)
    provides: SqliteProvider.getByVmid (active vmid owner), consolidated Settings (git_credential_token, bootconfig_source_ip_check, worker_pool_start/end, config_repo/branch)
  - phase: 01-control-plane-api (Plan 03)
    provides: WorkspaceService over the two provider ABCs, lib/errors typed service errors (.code → envelope)
  - phase: 01-control-plane-api (Plan 04)
    provides: get_service DI seam, include_router + ServiceError→envelope mapping pattern, JsonFormatter field whitelist, integration conftest (ASGITransport + temp SQLite + Fake + respx stub-ttyd)
provides:
  - "GET /api/v1/internal/bootconfig/{vmid} — the pull-at-boot ASVS L1 surface (WORK-03)"
  - "WorkspaceService.get_by_vmid (active workspace lookup, 404 on miss)"
  - "WorkspaceService.mint_repo_credential — pluggable A3 credential seam (no hard-coded PAT)"
  - "IllegalVmidError(.code=illegal_vmid) → enumeration-resistant 404 mapping"
affects: [phase-03-reproducible-workers]

# Tech tracking
tech-stack:
  added: []  # no new runtime dependency; reuses fastapi/httpx/respx already present
  patterns:
    - "Internal router is thin: vmid-in-pool gate → get_by_vmid → optional source-IP bind → mint credential → log {vmid, repo} only → respond(camelCase)"
    - "Credential issuance behind a pluggable seam (mint_repo_credential) reading a short-lived Settings token; placeholder when unset; never a hard-coded PAT"
    - "Enumeration resistance: out-of-pool / source-IP-mismatch both raise IllegalVmidError → 404 with a generic 'Not found.' message (no echo of the probe)"
    - "Secret hygiene by construction: the credential is a response-body field only, never a log extra (the JsonFormatter whitelist drops anything else anyway)"

key-files:
  created:
    - api/routers/internal.py
    - api/tests/integration/test_bootconfig.py
  modified:
    - api/services/workspaceService.py
    - api/lib/errors.py
    - api/main.py

key-decisions:
  - "Credential seam reads settings.git_credential_token and returns a marked placeholder when unset (A3) — no long-lived PAT hard-coded; the real issuer is operator config to confirm before Phase 3"
  - "IllegalVmidError reused for BOTH the out-of-pool gate AND a source-IP mismatch, so both present the identical generic 404 (no enumeration aid)"
  - "Source-IP defense-in-depth compares request.client.host to the workspace's resolved lxc_ip (ADR-0004) and is gated off by default; documented as NOT authentication (v1 LAN no-auth)"
  - "Source-IP check passes through when lxc_ip is unresolved, so it never blocks a legitimate boot before the static IP is known"

patterns-established:
  - "Thin internal router + Depends(get_service) + IllegalVmidError → 404 with a generic message"
  - "Pluggable credential issuance seam on the service (short-lived, repo-scoped, never logged/persisted)"
  - "Sentinel-token caplog + event-data assertion proving the no-secrets-in-logs gate (block_on=high)"

requirements-completed: [WORK-03]

# Metrics
duration: 9min
completed: 2026-06-10
---

# Phase 1 Plan 05: Pull-at-Boot Bootconfig Endpoint Summary

**`GET /api/v1/internal/bootconfig/{vmid}` — the phase's one real ASVS L1 surface — serves a worker's non-secret boot identifiers plus a short-lived, repo-scoped git credential minted per-fetch via a pluggable seam, with a vmid-in-pool gate, enumeration-resistant 404s, optional source-IP defense-in-depth, and a hard guarantee (sentinel-proven) that the credential never reaches a log line or event blob.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-10T16:26:00Z
- **Completed:** 2026-06-10T16:35:08Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `GET /api/v1/internal/bootconfig/{vmid}` (`routers/internal.py`): `int` path param (FastAPI rejects non-int, ASVS V5); rejects any `vmid` outside `[worker_pool_start, worker_pool_end]` with a 404 that does NOT echo the probed value (T-01-17); looks up the active workspace via the service; mints a per-fetch credential; returns the non-secret payload (`configRepo`/`configBranch`/`projectRepo`/`projectBranch` + `gitCredential`) in camelCase.
- Pluggable credential issuance (`WorkspaceService.mint_repo_credential`, A3): reads the short-lived, repo-scoped `settings.git_credential_token` (gitignored `.env`) and returns it, or a clearly-marked placeholder when unset. No long-lived PAT is hard-coded; the real issuer (GitHub App installation token / deploy token / ephemeral PAT) is operator config to confirm before Phase 3 wires `burrow-boot.sh`.
- Secret hygiene (T-01-18, block_on=high): the credential is a response-body field ONLY; the log line carries `{vmid, repo}` via whitelisted extras and nothing else. A sentinel-token integration test proves the exact credential value appears in ZERO captured log records and ZERO event `data` blobs.
- Source-IP defense-in-depth (T-01-19): gated by `settings.bootconfig_source_ip_check` (default off), compares `request.client.host` to the workspace's VMID-derived `lxc_ip` (ADR-0004) and 404s a mismatch — explicitly documented as NOT authentication (v1 LAN no-auth).
- `IllegalVmidError(.code="illegal_vmid")` added to `lib/errors.py` and mapped to 404 in `main.py` with a generic `"Not found."` message; `internal.router` registered in `create_app`.

## Task Commits

1. **Task 1: get_by_vmid lookup + pluggable mint_repo_credential seam** - `e1d143e` (feat)
2. **Task 2: bootconfig endpoint (vmid-in-pool gate, secret hygiene, registered)** - `d48b43e` (feat)
3. **Task 3: integration coverage + no-cred-in-logs gate (WORK-03)** - `a4981e2` (test)

**Plan metadata:** (this commit) `docs(01-05): complete plan`

## Files Created/Modified
- `api/routers/internal.py` - the bootconfig endpoint: vmid-in-pool gate, `get_by_vmid` lookup, gated source-IP bind, per-fetch credential mint, non-secret camelCase payload, log `{vmid, repo}` only. Thin; imports no driver (seam guard green).
- `api/services/workspaceService.py` - `get_by_vmid` (delegates to `db.getByVmid`, raises `WorkspaceNotFoundError` on miss) + `mint_repo_credential` (pluggable A3 seam reading `settings.git_credential_token`, placeholder fallback, no hard-coded PAT).
- `api/lib/errors.py` - `IllegalVmidError(.code="illegal_vmid")`; holds the probed `.vmid` for triage, message is generic (never echoed).
- `api/main.py` - `IllegalVmidError` → 404 in the status table + a `"Not found."` safe message; `include_router(internal.router)`.
- `api/tests/integration/test_bootconfig.py` - in-pool 200 / out-of-pool 404-no-echo / no-active-workspace 404 / sentinel-credential-not-in-logs-or-events / source-IP gate on↔off (5 tests).

## Decisions Made
- **Pluggable credential, no hard-coded PAT (A3):** `mint_repo_credential` reads the Plan-01 `git_credential_token` Settings key (short-lived, repo-scoped, gitignored `.env`) and returns a marked placeholder when unset. The docstring records that the real minting mechanism is operator config to confirm before Phase 3, and that the value must be short-lived, single-repo-scoped, never logged, and never persisted to worker env (ADR-0002). A grep confirms no token literal in the new code.
- **One error type for both rejection paths:** the out-of-pool gate and the source-IP mismatch both raise `IllegalVmidError`, so both 404 with the identical generic message — a prober cannot distinguish "out of pool" from "in pool but wrong source IP" from "no workspace" (enumeration resistance).
- **Source-IP check is defense-in-depth, gated off, and pass-through on unresolved IP:** it never blocks a legitimate boot before `lxc_ip` is known, and the no-auth LAN posture is preserved unless an operator opts in.
- **config.py untouched:** the two Settings keys (`git_credential_token`, `bootconfig_source_ip_check`) were already added by Plan 01 (single-owner config); this plan only reads them.

## Deviations from Plan

None - plan executed exactly as written. Tasks 1-3 implemented the service seam, the router, and the integration test as specified; all acceptance criteria met with no auto-fixes required.

## Authentication Gates

None - no external auth was required during execution. (The endpoint itself is intentionally no-auth per the v1 LAN-only posture; the operator credential-mechanism decision is documented as User Setup below, not an execution gate.)

## Known Stubs
- **`mint_repo_credential` placeholder (intentional, A3):** when `git_credential_token` is unset, the seam returns `placeholder-credential-for:<repo>` rather than a real credential. This is the deliberate, documented A3 placeholder — the endpoint contract is exercisable in CI without a real token, and the concrete issuer is operator config to be confirmed before Phase 3 wires `burrow-boot.sh`. It does not block WORK-03's endpoint-contract goal (the contract, gates, and secret hygiene are all real and CI-proven); the live consumer pull-step is Phase 3.

## User Setup Required
- **Service:** git-host (GitHub / Gitea / etc.) — credential-minting mechanism.
  - **Why:** the bootconfig endpoint returns a short-lived, repo-scoped git credential so a worker can clone the project repo at boot (ADR-0002). The concrete minting mechanism is operator config (A3).
  - **Env var:** `BURROW_GIT_CREDENTIAL_TOKEN` — a short-lived, repo-scoped token (deploy token / GitHub App installation token / ephemeral PAT). Stored ONLY in the gitignored `.env`; NEVER a long-lived PAT, NEVER committed or logged.
  - **A3 operator-confirm (before Phase 3):** decide and document the real credential-minting mechanism (deploy keys / App installation / fine-grained PAT) in the git-host settings, and replace the `mint_repo_credential` body accordingly. The returned value must stay short-lived and single-repo-scoped.

## Verification Evidence
- `cd api && uv run pytest -q` — **99 passed** (unit + integration, incl. the 5 new `test_bootconfig.py` cases).
- `uv run ruff check .` — All checks passed. `uv run ruff format --check .` — 49 files already formatted.
- `uv run mypy . --strict` — Success: no issues found in 49 source files.
- `uvx --with charset-normalizer reuse lint` — REUSE-compliant (149/149 files; new files carry the SPDX header).
- `uv lock --check` — consistent (no new packages, T-01-SC).
- Seam-leakage guard green — the router + service import no driver.
- block_on=high gates: the sentinel credential is absent from all captured logs + event data (asserted by `test_bootconfig.py`); no long-lived PAT literal in the new code (grep confirms only pre-existing test sentinels in unrelated files).

## Threat Model Coverage
| Threat ID | Mitigation delivered |
|-----------|----------------------|
| T-01-17 (enumeration) | `int` path param + `[pool_start, pool_end]` gate + 404 with no echo of the probe; verified by `test_out_of_pool_vmid_404_without_echoing_probe` |
| T-01-18 (cred/token in logs) | log `{vmid, repo}` only; credential is a body field, never an extra; sentinel-token caplog + event-data assertion |
| T-01-19 (spoofing) | source-IP defense-in-depth (gated, NOT auth); verified by `test_source_ip_check_gate_blocks_a_mismatch` |
| T-01-20 (over-scoped credential) | pluggable `mint_repo_credential` short-lived/repo-scoped seam; no hard-coded PAT |
| T-01-21 (cred persisted to worker env) | endpoint returns the credential in the body only (fetch-and-discard contract); the Phase-3 consumer enforces the discard |

## Next Phase Readiness
- The bootconfig endpoint contract is frozen and CI-proven. Phase 3 (`burrow-boot.sh` reproducible workers) can build the live pull-step against a stable, enveloped, camelCase contract.
- Before Phase 3 wires the consumer, the operator must confirm the real credential-minting mechanism (A3) and replace the `mint_repo_credential` placeholder body. This is the only open item gating the live pull-step.

## Self-Check: PASSED

Both created files (`api/routers/internal.py`, `api/tests/integration/test_bootconfig.py`) and this SUMMARY exist on disk; all three task commits (`e1d143e`, `d48b43e`, `a4981e2`) are present in the git history.

---
*Phase: 01-control-plane-api*
*Completed: 2026-06-10*
