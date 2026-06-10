---
phase: 01-control-plane-api
verified: 2026-06-10T00:00:00Z
status: human_needed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Real --full clone + start against a live Proxmox node; UPID blocks to OK; net0 static IP (computed from VMID) is set on the clone"
    expected: "CT clones from the golden template, boots, and receives its VMID-derived static IP; GET /api/v1/health reports compute: ok"
    why_human: "No Proxmox node reachable from the dev box; proxmoxer is mocked with `responses` in CI by design (hermetic). Real UPID semantics + net0 set only provable on real infra."
  - test: "Compensation tears down a REAL partial clone (force a mid-saga failure on a live node)"
    expected: "No orphaned CT remains; the reserved VMID is freed; the row lands in error"
    why_human: "Requires a real Proxmox CT to orphan and reap; the Fake proves the orchestration, not the live teardown."
  - test: "Real ttyd health reachable on the worker LAN interface; create reaches running end-to-end"
    expected: "Saga step 6 (_wait_ttyd) succeeds against a real worker's ttyd on :7681; workspace marked running"
    why_human: "Needs a booted worker LXC on the LAN; stub ttyd proves the poll path, not real ttyd reachability."
  - test: "Five-step create -> live terminal -> stop -> start -> destroy against real Proxmox + golden template (PRIMING.md STEP 4)"
    expected: "Full lifecycle succeeds on real infra; no orphan CTs; VMID pool clean afterward"
    why_human: "The full real-infra acceptance gate; CI cannot prove it (Out of Scope: 'Real Proxmox exercised in CI')."
deferred: []
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 1: Control Plane API Verification Report

**Phase Goal:** The full workspace lifecycle (create/list/get/stop/start/destroy) runs as a saga over both real providers, with a server-enforced state machine, capacity guard, race-safe allocation, and the `/api/v1` contract, all CI-green over the Fake provider.
**Verified:** 2026-06-10
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

The CI-provable core of Phase 1 is fully achieved and proven by behavior, not just existence. Every one of the six roadmap Success Criteria maps to substantive, wired code and a passing behavior test. The only outstanding work is the real-Proxmox infra acceptance (live clone/start/IP/boot of `ProxmoxComputeProvider`), which is deferred to the dev-homelab smoke gate by design (no Proxmox reachable from this box; CI is hermetic per the Out-of-Scope contract). That makes the status **human_needed**, not a failure: the automated set is green and only live-infra remains.

### CI Gate Evidence (run during verification)

| Gate | Command | Result |
|------|---------|--------|
| Test pyramid | `cd api && uv run pytest -q` | **99 passed** in ~11s |
| Type check | `uv run mypy . --strict` | Success: no issues in 49 source files |
| Lint | `uv run ruff check .` | All checks passed |
| SPDX/REUSE | `uvx --with charset-normalizer reuse lint` | Compliant; 150/150 files carry copyright + license |

### Observable Truths (the 6 roadmap Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Create runs the full saga (persist `creating`+reserved VMID **before** clone, await UPID, inject boot config, start, resolve static IP, await ttyd, mark `running`); a forced post-clone failure leaves NO orphan, frees the VMID, lands row in `error` | VERIFIED | `workspaceService.py:94-133` orders capacity→reserve(L108)→clone(L114); `except` (L129-133) compensates + `boot.error` + `status=error`. Tests: `test_create_persists_creating_row_before_clone`, `test_compensation_on_{clone,start,getip,ttyd}_failure`, `test_failed_create_does_not_leave_stuck_creating_row` (all pass) |
| 2 | Two concurrent creates never collide on a VMID (DB partial unique reservation, soft-deleted excluded → one success + one clean retryable error); destroy-then-recreate reuses a VMID | VERIFIED | `002_vmid_unique.sql`: `CREATE UNIQUE INDEX ... WHERE deletedAt IS NULL AND vmid IS NOT NULL` (partial, not plain UNIQUE); `sqliteProvider.py:128-139` maps IntegrityError→`VmidTakenError`; service retries (L151-159). Tests: `test_duplicate_active_vmid_raises_vmid_taken`, `test_destroy_then_recreate_reuses_vmid`, `test_partial_unique_index_exists_after_migrate` |
| 3 | State machine rejects illegal transitions server-side with an envelope error (stop-on-creating, start-on-destroyed, double-destroy); in-flight lock blocks concurrent mutations | VERIFIED | `statemachine.py:25-43` table omits `creating` on left + `destroyed` terminal; `IllegalTransitionError`→409 (`main.py:46`); per-workspace `asyncio.Lock` (`workspaceService.py:285-291`). Tests: `test_illegal_transitions_raise[creating-stop/destroyed-start/destroyed-destroy]`, `test_in_flight_lock_serializes_concurrent_stops` |
| 4 | Every route under `/api/v1` with the envelope; `/health` reports overall+db+compute and degrades (200, not 500); security headers + non-`*` CORS; structured JSON logs with no secrets | VERIFIED | All 4 routers `prefix="/api/v1"` + `respond()`; `health.py:41-48` degrade-not-500; `middleware.py` 4 security headers; CORS `allow_origins=[settings.allowed_origin]` (non-`*`, `main.py:177`); `logging.py` allow-list formatter. Tests: `test_health_degrades_not_500_when_compute_down`, `test_headers_present_on_{success,error}`, `test_cors_allows_configured_origin_not_wildcard`, `test_sentinel_secret_never_reaches_json_log` |
| 5 | Create refused when node RAM > threshold; operator selects node at create time; event log records created/started/stopped/destroyed/boot.error | VERIFIED | `workspaceService.py:104-105` `getNodeMemory > capacity_threshold(0.80)`→`CapacityError`; `node` is operator input on `WorkspaceCreate`; `logEvent` calls for each lifecycle event. Tests: `test_create_refused_when_node_over_threshold`, `test_capacity_guard_queries_the_operator_selected_node`, `test_event_log_oldest_first` |
| 6 | Test pyramid runs in CI — unit (saga/state machine over Fake) → integration (real SQLite, mocked Proxmox HTTP via `responses`, stub ttyd) → e2e (Fake); every bug fix lands a failing-first regression test | VERIFIED | 99 tests across `tests/unit` + `tests/integration`; Proxmox mocked with `responses` (NOT respx) per validation contract (`test_proxmox_provider.py:32`); e2e lifecycle over Fake in `test_workspaces_api.py` (create→stop→start→destroy). Full suite green |

**Score:** 6/6 truths verified (all CI-provable; real-infra acceptance deferred to human smoke)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `api/services/workspaceService.py` | create/stop/start/destroy saga + compensation + capacity + VMID policy + event logging | VERIFIED | 338 lines; 8-step saga, persist-before-clone, idempotent `_compensate`, `_safe` redactor, `mint_repo_credential` seam |
| `api/lib/statemachine.py` | TRANSITIONS table + assert_transition (SC-12) | VERIFIED | 5 legal pairs; `creating` internal-only; `destroyed` terminal; `error`→destroy only |
| `api/lib/errors.py` | Typed service errors with stable `.code` | VERIFIED | CapacityError, IllegalTransitionError, NoFreeVmidError, WorkspaceBootError, WorkspaceNotFoundError, IllegalVmidError |
| `api/compute/proxmoxProvider.py` | Real proxmoxer impl (UPID waits, net0, pool-add, node mem) | VERIFIED | 239 lines; every mutation `_block(upid)` asserts `exitstatus==OK`; every call in `asyncio.to_thread`; `verify_ssl=ca_path` |
| `api/db/sqliteProvider.py` | Ordered migration runner, VmidTakenError, getEvents, getByVmid | VERIFIED | `schema_migrations` ledger applies 001+002; IntegrityError→VmidTakenError; soft-delete-aware reads |
| `api/db/migrations/002_vmid_unique.sql` | Partial unique index `WHERE deletedAt IS NULL` | VERIFIED | `CREATE UNIQUE INDEX ... WHERE deletedAt IS NULL AND vmid IS NOT NULL` |
| `api/routers/{workspaces,health,templates,internal}.py` | `/api/v1` CRUD + lifecycle + health + bootconfig, envelope-wrapped | VERIFIED | All `prefix="/api/v1"`; thin over service/DB; `respond()` envelope |
| `api/routers/internal.py` | Pull-at-boot bootconfig (vmid-in-pool gate, no-cred-in-logs) | VERIFIED | In-pool gate→404 no-echo; source-IP defense-in-depth; logs only `{vmid, repo}` |
| `api/lib/{middleware,logging}.py` | Security headers + JSON formatter | VERIFIED | 4 headers; allow-list JSON formatter drops non-whitelisted extras |
| `api/main.py` | App factory wiring routers + middleware + DI | VERIFIED | `include_router`x4; SecurityHeaders inner / CORS outer; `get_service` seam |
| `api/config.py` | All Phase-1 Settings keys, safe defaults, no hard-coded PAT | VERIFIED | `git_credential_token=""`, `proxmox_token_value=""`, `proxmox_ca_cert_path` is a CA path |
| `api/tests/**` (12 files) | Unit + integration tiers, `responses` for Proxmox | VERIFIED | 99 passing; `responses` (not respx) for Proxmox |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| sqliteProvider.migrate() | 002_vmid_unique.sql | ordered loop applies 002 after 001 | WIRED | gsd-sdk verified; ledger-based runner |
| sqliteProvider.createWorkspace | VmidTakenError | catch IntegrityError on vmid index | WIRED | Read-confirmed L128-139; `test_duplicate_active_vmid_raises_vmid_taken` passes. (gsd-sdk reported "source not found" — false negative: the link `from` string carries a `createWorkspace` method suffix the path-parser mis-reads; the code + test prove the wiring) |
| proxmoxProvider | Tasks.blocking_status | UPID block in to_thread, assert OK | WIRED | gsd-sdk verified; `_block` L67-80 |
| proxmoxProvider | settings.proxmox_ca_cert_path | ProxmoxAPI(verify_ssl=ca path) | WIRED | gsd-sdk verified; `main.py` L63 |
| workspaceService | db.createWorkspace / compute.cloneCt / assert_transition | reserve INSERT + 8-step saga + guard | WIRED | gsd-sdk verified all 3 |
| main.py | routers + middleware + get_service | include_router + add_middleware | WIRED | gsd-sdk verified all 3 |
| internal.py | worker_pool_start/end + mint_repo_credential | in-pool gate + per-fetch mint | WIRED | gsd-sdk verified all 2 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `routers/internal.py` bootconfig | `payload` (configRepo/projectRepo + gitCredential) | `service.get_by_vmid` (real SQLite row) + `mint_repo_credential` (settings seam) | Yes — DB-backed lookup; credential from settings seam (placeholder marked when unset) | FLOWING |
| `routers/workspaces.py` list/get/events | workspace rows / events | `db.listWorkspaces` / `getWorkspace` / `getEvents` (real SQLite SELECT) | Yes — parameterized SELECTs against migrated SQLite | FLOWING |
| `routers/health.py` | db/compute status | provider `healthcheck()` | Yes — real provider calls behind `_safe` | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full backend test suite | `uv run pytest -q` | 99 passed in 10.96s | PASS |
| Must-have proof subset | `pytest <60 saga/compensation/sm/vmid/bootconfig/health/security/proxmox tests>` | 60 passed | PASS |
| CRUD lifecycle e2e over Fake | `pytest tests/integration/test_workspaces_api.py -v` | 7 passed (create→stop→start→destroy→events) | PASS |
| mypy strict | `uv run mypy . --strict` | no issues, 49 files | PASS |
| ruff | `uv run ruff check .` | All checks passed | PASS |
| REUSE/SPDX | `uvx ... reuse lint` | Compliant, 150/150 | PASS |
| Proxmox mock library | grep `import respx` in proxmox test | absent; uses `responses` | PASS |
| Security gate: `verify_ssl=False` | grep across `api/**.py` | No matches | PASS |
| Security gate: secrets in log formatter | grep cred keys in `logging.py` allow-list | absent (cannot serialize) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| PLAT-01 | 01-04 | All routes under `/api/v1` | SATISFIED | All routers `prefix="/api/v1"` |
| PLAT-03 | 01-04 | `/health` reports overall+db+compute | SATISFIED | `health.py`; degrade-not-500 test |
| PLAT-04 | 01-04 | Structured JSON logs | SATISFIED | `logging.py` JsonFormatter + allow-list |
| PLAT-05 | 01-04 | Security headers | SATISFIED | `middleware.py`; headers-on-success/error tests |
| WS-01 | 01-03/04 | Create from name/repo/branch/plugin/node | SATISFIED | `WorkspaceCreate` + create saga |
| WS-02 | 01-02/03 | Full saga, persist-before-clone, await UPID | SATISFIED | saga L94-133; UPID `_block` |
| WS-03 | 01-03 | Compensate on failure, no orphan | SATISFIED | `_compensate`; 4 per-step compensation tests |
| WS-04 | 01-04 | List, filter by status | SATISFIED | `list_workspaces`; filter test |
| WS-05 | 01-04 | Fetch by id | SATISFIED | `get_workspace`; 404 test |
| WS-06 | 01-03/04 | Stop running (state preserved) | SATISFIED | `stopWorkspace` + guard |
| WS-07 | 01-03/04 | Start stopped (await ttyd) | SATISFIED | `startWorkspace` + `_wait_ttyd` |
| WS-08 | 01-03/04 | Destroy (stop+destroy+soft-delete) | SATISFIED | `destroyWorkspace`; soft-delete test |
| WS-09 | 01-03 | Enforced state machine | SATISFIED | `statemachine.py`; illegal-transition tests |
| WS-10 | 01-01 | Race-safe VMID via partial unique index | SATISFIED | `002_vmid_unique.sql`; reservation tests |
| WS-11 | 01-01/04 | Read event log | SATISFIED | `getEvents` + `/events`; oldest-first test |
| WORK-03 | 01-05 | Bootconfig endpoint (pull-at-boot, no cred in logs) | SATISFIED (endpoint contract) | `internal.py`; no-cred-in-logs sentinel test. Live `burrow-boot.sh` consumer pull-step is Phase 3 (per ROADMAP/REQUIREMENTS) |
| CAP-01 | 01-02/03 | Refuse create over capacity threshold | SATISFIED | capacity guard L104-105; refusal test |
| CAP-04 | 01-03 | Operator selects node at create | SATISFIED | `node` on `WorkspaceCreate`; guard queries selected node |
| CICD-02 | 01-04 | Test pyramid in CI | SATISFIED | unit→integration→e2e-over-Fake; 99 green |
| CICD-03 | 01-02..05 | Failing-first regression tests | SATISFIED | per-req tests in correct tiers; `responses` for Proxmox |

All 20 declared requirement IDs SATISFIED at the CI-provable level. No orphaned requirements (REQUIREMENTS.md maps exactly these IDs to Phase 1).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | - | TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER scan of `api/**.py` | - | Zero debt markers found |

`mint_repo_credential` returns a `placeholder-credential-for:{repo}` string when `git_credential_token` is unset. This is NOT a stub: it is the documented, pluggable A3 issuance seam (RESEARCH Open Question 1), the contract is exercisable, the real issuer is an explicit Phase-3 operator action, and the value is clearly marked (never a real credential). No debt marker, no rendering of empty/hardcoded user data.

### Human Verification Required (dev-homelab smoke gate)

The real-Proxmox path of `ProxmoxComputeProvider` is mocked in CI by design (`responses`), and no Proxmox node is reachable from this box. Per the operator's full-autonomous choice and the Phase-1 CONTEXT/VALIDATION deferral, the following are **human_needed**, not phase-blocking:

1. **Real `--full` clone + start + net0 static IP** — create against a live node; confirm CT clones from the golden template, UPID blocks to OK, and the VMID-derived static IP is set on `net0`.
2. **Real compensation** — force a mid-saga failure on a live node; confirm no orphan CT, the VMID is freed, the row lands `error`.
3. **Real ttyd health on the worker LAN** — confirm `_wait_ttyd` reaches a real worker's ttyd on `:7681` and the saga reaches `running`; `/health` shows `compute: ok`.
4. **Five-step acceptance (PRIMING.md STEP 4)** — full create → live terminal → stop → start → destroy against real Proxmox + golden template; no orphans, VMID pool clean.

### Gaps Summary

No CI-provable gaps. The create saga (persist-before-clone + per-step compensation), the partial-unique-index race-safe VMID reservation, the server-enforced state machine + in-flight lock, the capacity guard + node selection, the full `/api/v1` envelope contract, `/health` degrade-not-500, security headers + non-`*` CORS, secret-safe JSON logging, and the pull-at-boot bootconfig endpoint are all implemented substantively, wired end-to-end, and proven by 99 passing tests with mypy-strict, ruff, and REUSE all green. The block_on=high security gates (no `verify_ssl=False`, no secret in logs, no hard-coded PAT) are clear.

The single outstanding item is real-Proxmox infra acceptance, deferred to the dev-homelab smoke gate by explicit design (Out of Scope: "Real Proxmox exercised in CI"). Status is therefore **human_needed** — the automated set passes and only live infra remains.

---

_Verified: 2026-06-10_
_Verifier: Claude (gsd-verifier)_
