<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 01-control-plane-api
plan: 03
subsystem: api
tags: [saga, state-machine, compensation, vmid-reservation, capacity-guard, asyncio-lock, workspace-service]

# Dependency graph
requires:
  - phase: 01-control-plane-api (Plan 01)
    provides: "DbProvider.createWorkspace partial-unique INSERT + VmidTakenError, updateWorkspace/softDeleteWorkspace/logEvent/getEvents/getByVmid, listWorkspaces; all Phase-1 Settings keys (capacity_threshold, ttyd/clone/task timeouts, pool range, template_vmid, default_node, config_repo/branch)"
  - phase: 00-contracts-seams-golden-template
    provides: "ComputeProvider ABC + FakeComputeProvider with FakeFailures injection, Workspace/WorkspaceCreate/BootConfig DTOs, lib/envelope, seam-leakage guard"
provides:
  - "WorkspaceService.createWorkspace — the SC-corrected 8-step create saga (capacity guard -> reserve VMID + creating row BEFORE clone -> clone -> injectBootConfig -> start -> resolve IP -> ttyd health -> running), over the two provider ABCs only"
  - "Per-step compensation tree (SC-11): any post-reservation failure runs idempotent stop+destroy, frees the VMID, logs a redacted boot.error, lands the row in error (never stuck creating, no orphan)"
  - "lib/statemachine.py TRANSITIONS table + assert_transition guard (SC-12); creating is internal-only, error exits only via destroy (A4)"
  - "lib/errors.py service-tier typed errors with stable .code (IllegalTransitionError, CapacityError, NoFreeVmidError, WorkspaceBootError, WorkspaceNotFoundError) for deterministic router envelope mapping"
  - "stopWorkspace/startWorkspace/destroyWorkspace — state-guarded, per-workspace-locked, UPID-blocked, event-logged lifecycle mutations"
  - "VMID reservation policy: union(compute.usedVmids, DB-used) -> getNextVmid -> INSERT; VmidTakenError -> rescan+retry (bounded), exhaustion -> NoFreeVmidError"
  - "_safe() secret redactor for event/log text (git/CI tokens, URL userinfo, long opaque tokens)"
affects: [01-04-routers, 01-05-bootconfig, phase-02-terminal-proxy, phase-04-reaper]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persist-before-clone saga with reverse compensation: the creating row + reserved VMID are durable before any Proxmox mutation, so every failure is reaper-recoverable and lands in error (SC-2/SC-11)"
    - "Service-owned state machine: a single TRANSITIONS table is the policy authority; stop/start/destroy call assert_transition BEFORE mutating, rejecting illegal transitions at the boundary"
    - "Per-workspace asyncio.Lock (lazily created, keyed by id) serializes concurrent mutations in-process; the transition read happens inside the lock so the DB state is the cross-process backstop (A2)"
    - "Service-tier typed errors carry a stable .code class attribute so the Plan-04 router maps error.code without an isinstance ladder"
    - "Secret redaction at the event/log boundary (_safe): exception type preserved, message scrubbed of token-shaped substrings and capped (ASVS V7)"

key-files:
  created:
    - api/lib/statemachine.py
    - api/lib/errors.py
    - api/services/__init__.py
    - api/services/workspaceService.py
    - api/tests/unit/test_state_machine.py
    - api/tests/unit/test_create_saga.py
    - api/tests/unit/test_compensation.py
    - api/tests/unit/test_capacity_guard.py
  modified: []

key-decisions:
  - "NoFreeVmidError is a distinct service-tier error (not a re-export of the compute one) so it carries the policy .code='no_free_vmid' the router maps; documented in lib/errors.py"
  - "Capacity guard refuses strictly ABOVE the threshold (> 0.80); a node at exactly 0.80 is allowed (proven by test_create_allowed_at_exactly_threshold)"
  - "The per-workspace lock + in-lock transition read is the in-process guard; the DB partial-unique index (create-create) and the status read-then-act (stop/destroy double-fire) are the cross-process backstop (A2). A status-CAS UPDATE is deferred to the router/DB layer if --workers >1 is confirmed at deploy."
  - "_compensate swallows errors from stop/destroy so the original failure and the row->error landing are never masked; destroyCt is idempotent (no-op on a missing CT) so a clone-step failure and a ttyd-step failure both clean up safely"
  - "Lifecycle tests live in test_state_machine.py (table + service layers) per the plan's <files>; saga/compensation/capacity tests are their own files"

patterns-established:
  - "Saga orchestration with reverse compensation over provider ABCs — the one genuinely novel piece of logic in the phase; everything else is wiring"
  - "TDD RED->GREEN per task: failing test committed first (test:), implementation second (feat:)"

requirements-completed: [WS-01, WS-02, WS-03, WS-06, WS-07, WS-08, WS-09, CAP-01, CAP-04, CICD-03]

# Metrics
duration: 11min
completed: 2026-06-10
---

# Phase 1 Plan 03: WorkspaceService Saga Summary

**The SC-corrected create -> stop -> start -> destroy lifecycle engine: an 8-step persist-before-clone saga with per-step idempotent compensation, a server-enforced transition table, a per-workspace in-flight lock, race-safe VMID reservation, and the capacity guard — depending only on the two provider ABCs and fully unit-proven over the FakeComputeProvider.**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-06-10T15:49:18Z
- **Completed:** 2026-06-10T16:00:38Z
- **Tasks:** 3 (TDD, 6 task commits)
- **Files modified:** 8 created, 0 modified

## Accomplishments

- `WorkspaceService.createWorkspace` runs the SC-corrected 8-step saga over the Fake to `running` with a pool-range VMID, a resolved `lxc_ip`, and a `workspace.created` event — capacity guard, then reserve-row-before-clone, then clone/inject/start/resolve-IP/ttyd-health/mark-running (SC-1/2, WS-01/02).
- Per-step compensation (SC-11) proven at clone, start, getIp, and ttyd-health: a forced `FakeFailures` failure tears down the partial clone (idempotent stop+destroy), frees the VMID (zero leftover containers), logs a redacted `boot.error`, and lands the row in `error` — never stuck `creating`, no orphan (WS-03, T-01-09/10).
- `lib/statemachine.py` TRANSITIONS table + `assert_transition` guard: the five legal transitions resolve and every illegal pair (stop-on-creating, start-on-destroyed, double-destroy, running->start, error->start/stop) raises `IllegalTransitionError` (SC-12, WS-09).
- `lib/errors.py` five service-tier typed errors, each with a stable `.code`, so Plan 04's router maps `error.code` deterministically onto the envelope.
- `stop/start/destroy` are state-guarded (assert_transition before mutating), serialized by a per-workspace `asyncio.Lock`, UPID-blocked inside the provider, and event-logged; `destroy` stops-if-running then idempotently destroys then soft-deletes (WS-06/07/08).
- Race-safe VMID reservation policy: union of `compute.usedVmids()` and DB-used VMIDs feeds `getNextVmid`, the DB partial-unique INSERT is the arbiter, `VmidTakenError` triggers a bounded rescan+retry, and pool exhaustion raises `NoFreeVmidError`.

## Task Commits

Each task was committed atomically (Conventional Commits + `Signed-off-by`), TDD RED -> GREEN:

1. **Task 1: State machine + service-tier errors**
   - `30227c6` (test) failing state-machine guard tests (WS-09)
   - `3db5d16` (feat) TRANSITIONS table + assert_transition + lib/errors
2. **Task 2: Create saga, VMID reservation, capacity guard, compensation**
   - `0ba555f` (test) failing saga/compensation/capacity tests (WS-02/03, CAP-01)
   - `b5d1226` (feat) createWorkspace saga + _reserve_vmid_and_row + _compensate + _safe
3. **Task 3: stop/start/destroy with state guards, lock, events**
   - `999c64f` (test) failing lifecycle guard tests (WS-06/07/08/09)
   - `e0e87b7` (feat) stopWorkspace/startWorkspace/destroyWorkspace + per-workspace lock

**Plan metadata:** (this commit) `docs(01-03): complete WorkspaceService saga plan`

## Files Created/Modified

- `api/lib/statemachine.py` - TRANSITIONS table + assert_transition guard (SC-12); creating internal-only, error->destroy only.
- `api/lib/errors.py` - IllegalTransitionError, CapacityError, NoFreeVmidError, WorkspaceBootError, WorkspaceNotFoundError, each with a stable `.code`.
- `api/services/__init__.py` - Service-tier package (SPDX + seam-discipline note).
- `api/services/workspaceService.py` - The create saga, VMID reservation, capacity guard, compensation, stop/start/destroy, per-workspace lock, `_safe` redactor.
- `api/tests/unit/test_state_machine.py` - WS-09 table cases + WS-06/07/08/09 service-level lifecycle cases (incl. the in-flight lock).
- `api/tests/unit/test_create_saga.py` - WS-01/02 happy path over a clean Fake.
- `api/tests/unit/test_compensation.py` - WS-03 per-step FakeFailures compensation + no-secret-in-event assertion.
- `api/tests/unit/test_capacity_guard.py` - CAP-01/04 refusal + operator-node honoring + at-threshold boundary.

## Decisions Made

- **`NoFreeVmidError` is a distinct service-tier error**, not a re-export of the compute seam's, so it carries the router-mapped `.code='no_free_vmid'` (documented inline). The compute one stays a driver-adjacent concern.
- **Capacity guard refuses strictly above the threshold** (`> 0.80`): a node at exactly `0.80` is allowed (matches "refuse when exceeds", pinned by a boundary test).
- **In-flight serialization = per-workspace `asyncio.Lock` + in-lock transition read.** The DB partial-unique index is the create-create arbiter; the in-lock read-then-act is the stop/destroy double-fire backstop. A cross-process status-CAS `UPDATE` is left to the DB/router layer if `--workers >1` is confirmed at deploy (A2) — the in-process guard is honest for the single-worker dev case and the DB is authoritative regardless.
- **`_compensate` is best-effort and swallows teardown errors** so the original failure and the `row->error` landing are never masked; `destroyCt` idempotence means a clone-step and a ttyd-step failure both clean up via the same path.

## Deviations from Plan

None - plan executed exactly as written. The three tasks, their TDD RED/GREEN structure, the file set, and the behavior/acceptance criteria were implemented as specified. No bugs, missing-critical-functionality, or blocking issues required auto-fixing; no architectural decisions arose.

## Issues Encountered

- `ruff format` reflowed two test files (`test_compensation.py`, `test_state_machine.py`) after they were written; reformatted and folded into the relevant task commits before gating. Not a behavior change.

## Known Stubs

None in this plan's deliverables. The git-credential minting seam (Assumption A3) belongs to the bootconfig router (Plan 05), not the service; the service's `injectBootConfig` consumes the non-secret `BootConfig` only (no credential), which is correct by design (ADR-0002 pull-at-boot). `_wait_ttyd` is a real httpx poll, monkeypatched only in the unit tier per the plan's execution_note (the real poll + stub-ttyd is the Plan 04 integration tier).

## User Setup Required

None - no external service configuration required. The service reads existing `Settings` keys (added by Plan 01) and depends only on the provider ABCs.

## Next Phase Readiness

- The MVP orchestration core is complete: a create -> running -> stop -> start -> destroy slice runs end-to-end over the FakeComputeProvider with zero Proxmox, fully unit-tested.
- Plan 04 (routers) can now wire `/api/v1/workspaces` to `WorkspaceService`, mapping `error.code` (illegal_transition / capacity_exceeded / no_free_vmid / boot_failed / not_found) onto the envelope, and exercise the saga + compensation + state machine in the integration tier against real SQLite + a stub ttyd.
- Plan 05 (bootconfig) reads `getByVmid` (Plan 01) and is unaffected by this plan.
- No blockers. Full gate green: 81 pytest passed, ruff + ruff format + mypy --strict (37 files) + `uv lock --check` + REUSE (135/135); seam-leakage guard green (the service imports neither `aiosqlite` nor `proxmoxer`).

---
*Phase: 01-control-plane-api*
*Completed: 2026-06-10*

## Self-Check: PASSED

- Created files verified present: `statemachine.py`, `errors.py`, `services/__init__.py`, `workspaceService.py`, four unit test files, and `01-03-SUMMARY.md`.
- Task commits verified in git history: `30227c6`, `3db5d16` (Task 1), `0ba555f`, `b5d1226` (Task 2), `999c64f`, `e0e87b7` (Task 3).
- Full gate re-run green: 81 pytest passed, ruff + format + mypy --strict + uv lock --check + REUSE 135/135; seam-leakage guard green.
