<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 01-control-plane-api
plan: 02
subsystem: infra
tags: [proxmox, proxmoxer, asyncio-to-thread, upid-blocking, ca-pinned-tls, responses, requests-mock, net0, capacity]

# Dependency graph
requires:
  - phase: 00-contracts-seams-golden-template
    provides: "ComputeProvider ABC + typed ComputeError hierarchy, ProxmoxComputeProvider skeleton, ComputeTask/ComputeStatus/BootConfig DTOs, proxmoxer.* mypy override, seam-leakage guard"
  - phase: 01-control-plane-api
    provides: "All Phase-1 Settings keys (proxmox host/user/token/ca path, pool range, net0 params, clone/task timeouts), tests/integration/ package"
provides:
  - "Real ProxmoxComputeProvider behind the ABC: clone/start/stop/destroy each block on the Proxmox UPID (Tasks.blocking_status, assert exitstatus OK) before returning (SC-1)"
  - "Every blocking proxmoxer call wrapped in asyncio.to_thread — no synchronous proxmoxer call runs on the event loop (Pitfall 2)"
  - "cloneCt: full clone + pool-add to burrow-workers (ADR-0003) + static net0 from VMID (ADR-0004), then UPID-block"
  - "_block() helper: None->TaskFailedError (timeout), non-OK->TaskFailedError; only typed ComputeError subclasses cross the seam"
  - "getNodeMemory mem/maxmem fraction (CAP-01 data source); getIp computed from VMID (ADR-0004, SC-6, no DHCP/agent poll); idempotent destroyCt (404->no-op success)"
  - "CA-pinned TLS via verify_ssl=proxmox_ca_cert_path (verification never disabled; block_on=high gate)"
  - "responses + respx dev deps; responses-mocked integration proof (test_proxmox_provider.py) of UPID-block + pool-add + net0 + node-memory + failure paths"
affects: [01-03-workspace-saga, 01-04-routers, 01-05-bootconfig]

# Tech tracking
tech-stack:
  added: [responses==0.26.1, respx==0.23.1]
  patterns:
    - "UPID-blocking provider over a synchronous proxmoxer client: each mutating call returns a UPID; _block() polls Tasks.blocking_status in asyncio.to_thread and asserts exitstatus OK before returning (SC-1)"
    - "Mock proxmoxer's requests leg with responses (NOT respx — respx is httpx-only and cannot intercept proxmoxer); respx reserved for the httpx ttyd-health leg (Plan 04)"
    - "Single VMID->IP formula (ipaddress over worker_subnet) drives both the net0 set at clone and getIp, so control-plane and worker addresses cannot drift (ADR-0004)"
    - "Idempotent compensation: destroyCt of an absent CT (404/not-found) reads as no-op success so a partial-clone teardown is always safe"

key-files:
  created:
    - api/tests/integration/test_proxmox_provider.py
  modified:
    - api/compute/proxmoxProvider.py
    - api/pyproject.toml
    - api/uv.lock

key-decisions:
  - "destroyCt swallows a 404/not-found (idempotent no-op success) but re-raises every other error as LxcNotReadyError — a not-yet-cloned VMID teardown must not fail the saga compensation"
  - "_is_not_found() inspects the error's status_code/message defensively rather than importing a proxmoxer exception type — keeps the driver confined and the seam guard green"
  - "_ip_for() raises CloneError when a VMID maps outside the worker subnet (config error surfaced, not a silently-wrong address)"
  - "Timeout path tested with clone_timeout=0 + a never-'stopped' status so blocking_status returns None on the first poll — no real wait, deterministic TaskFailedError"

patterns-established:
  - "Every async ABC method that calls proxmoxer wraps the call in asyncio.to_thread (sync-client-in-async discipline)"
  - "responses (requests-mock) is the Proxmox HTTP mock; assert on responses.calls to prove ADR wiring (pool-add PUT, net0 PUT) actually fired"

requirements-completed: [PLAT-07, CAP-01, CICD-02, CICD-03]

# Metrics
duration: 21min
completed: 2026-06-10
---

# Phase 1 Plan 02: Real ProxmoxComputeProvider Summary

**The frozen Phase-0 Proxmox skeleton filled with real `proxmoxer` bodies behind the ABC — UPID-blocked clone/start/stop/destroy run in `asyncio.to_thread`, CA-pinned TLS, static `net0` + pool-add at clone, node-memory + computed IP — proven hermetically in CI with the `responses` (requests-mock) library.**

## Performance

- **Duration:** 21 min
- **Started:** 2026-06-10T15:19:24Z
- **Completed:** 2026-06-10T15:40:39Z
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `ProxmoxComputeProvider` is fully implemented: no method raises `NotImplementedError`. Every blocking `proxmoxer` call runs inside `asyncio.to_thread`, so a multi-second clone never stalls the event loop (Pitfall 2).
- Each mutating call (clone/start/stop/destroy) returns a Proxmox UPID immediately; `_block()` polls `Tasks.blocking_status` in a worker thread and asserts `exitstatus == "OK"` before returning — `None` (timeout) and non-OK both raise `TaskFailedError` (SC-1). Only typed `ComputeError` subclasses cross the seam.
- `cloneCt` does a `--full` clone, adds the new VMID to `/pool/burrow-workers` (ADR-0003 pool-scoped token), and sets the static `net0` IP from the VMID (ADR-0004) — all before blocking on the clone UPID. proxmoxer request errors map to `CloneError`.
- `getNodeMemory` returns the `mem/maxmem` fraction (CAP-01 data source); `getIp` computes the address from the VMID via `ipaddress` (ADR-0004, SC-6 — no DHCP poll, no guest agent); `destroyCt` of an absent CT is an idempotent no-op success (compensation-safe).
- CA-pinned TLS: the client is constructed with `verify_ssl=settings.proxmox_ca_cert_path`; verification is never disabled (the comment-stripped `verify_ssl=False` grep returns 0; block_on=high gate satisfied).
- `responses` + `respx` added as dev deps; `responses`-mocked integration test proves UPID-block + pool-add PUT + net0 PUT + node-memory + the non-OK/timeout failure paths, with zero outbound network.
- All `proxmoxer`/`ProxmoxAPI` symbols stay confined to `proxmoxProvider.py` — the seam-leakage guard stays green.

## Task Commits

Each task was committed atomically (Conventional Commits + `Signed-off-by`):

1. **Task 1: Add responses + respx dev deps + carry pytest config forward** - `bd99ddc` (chore)
2. **Task 2: Implement the real ProxmoxComputeProvider bodies (TDD GREEN)** - `cd55054` (feat)
3. **Task 3: Integration test — UPID block, net0, node memory via responses (TDD)** - `40bf765` (test)

**Plan metadata:** docs commit (this SUMMARY + STATE + ROADMAP).

_Note: Task 2 is `tdd="true"`; its behavioral RED/GREEN proof is delivered by the Task 3 `responses` integration test (the plan splits the impl and its hermetic proof into Task 2 and Task 3). Task 2's own gate (mypy --strict + seam guard) passed at commit time._

## Files Created/Modified

- `api/compute/proxmoxProvider.py` - Real proxmoxer implementation: `_block()` UPID waiter, `_ip_for()`/`_net0_for()` (ADR-0004), `cloneCt` (full clone + pool-add + net0), start/stop/destroy (idempotent destroy), getStatus/getIp/getNodeMemory/usedVmids/getNextVmid/waitTask/healthcheck — all `asyncio.to_thread`-wrapped, CA-pinned.
- `api/pyproject.toml` - `responses==0.26.1` + `respx==0.23.1` in the dev group (runtime deps unchanged).
- `api/uv.lock` - Lockfile updated for the two dev deps + their transitive requests/urllib3/charset-normalizer chain; `uv lock --check` consistent.
- `api/tests/integration/test_proxmox_provider.py` - 7-case `responses`-mocked proof (UPID-block, pool-add + net0 PUTs, non-OK + timeout `TaskFailedError`, node-memory fraction, CA-path construction, computed IP, exhausted-pool `NoFreeVmidError`).

## Decisions Made

- **`destroyCt` is idempotent on a missing CT.** A 404/"not found"/"does not exist" error reads as a no-op success (`ComputeTask(status="ok")`); every other error re-raises as `LxcNotReadyError`. The saga's compensation may call destroy on a VMID that was never cloned (failure before/at clone), so destroy of an absent CT must not fail (Pitfall 7).
- **`_is_not_found()` inspects status code/message, not a proxmoxer exception type.** Importing the driver's exception class to catch a 404 would either leak the driver past the seam or be brittle; a defensive `status_code`/message check keeps `proxmoxer` confined and the seam guard green.
- **`_ip_for()` raises `CloneError` for an out-of-subnet VMID.** A VMID whose computed address falls outside `worker_subnet` is a configuration error surfaced loudly rather than a silently-wrong `net0`/IP.
- **Timeout proof uses `clone_timeout=0` + a never-`stopped` status.** `Tasks.blocking_status` returns `None` only when the task never reaches `stopped` and the deadline passes; `timeout=0` trips the deadline on the first poll, so the `TaskFailedError` timeout path is proven deterministically with no real wait.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] net0 PUT-body assertion compared against the un-encoded form**
- **Found during:** Task 3 (the success-clone net0 assertion)
- **Issue:** The first cut of `test_clone_blocks_on_upid_and_wires_pool_and_net0` asserted `"ip=10.99.0.201/24" in net0_put.request.body`. proxmoxer (`requests`) form-URL-encodes the PUT body, so the recorded body is `...ip%3D10.99.0.201%2F24...` and the raw-substring assertion failed — a test bug, not a provider bug (the provider sent the correct net0 string).
- **Fix:** Decode the body with `urllib.parse.unquote` before asserting; the decoded body contains `ip=10.99.0.201/24`, `gw=10.99.0.1`, `bridge=vmbr0`.
- **Files modified:** api/tests/integration/test_proxmox_provider.py
- **Verification:** `pytest tests/integration/test_proxmox_provider.py` → 7 passed.
- **Committed in:** 40bf765 (Task 3 commit — broken assertion never shipped)

**2. [Rule 3 - Blocking] mypy --strict on the request body/url union types**
- **Found during:** Task 3 (gate sweep)
- **Issue:** `responses` types `request.url` as `str | None` and `request.body` as `bytes | Iterable | None`; the test's `.endswith(...)` and `unquote(...)` calls failed `mypy --strict` with `union-attr`/`arg-type` errors.
- **Fix:** Narrowed with `str(c.request.url)` for the URL and a `body.decode() if isinstance(body, bytes) else str(body)` guard before `unquote`.
- **Files modified:** api/tests/integration/test_proxmox_provider.py
- **Verification:** `mypy . --strict` → no issues (29 files).
- **Committed in:** 40bf765 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 test bug, 1 blocking type-check). Both were in the test file; the provider implementation shipped clean.
**Impact on plan:** No scope creep — no new packages beyond the two planned dev deps, no architecture change. Both fixes were necessary to land the required test and gate green.

## Issues Encountered

- proxmoxer URL/return shapes had to be confirmed empirically (clone POST returns the bare UPID string after `data`-unwrap; `Tasks.blocking_status` polls `GET .../nodes/{node}/tasks/{upid}/status` and decodes the node from the UPID's 2nd field; the form body is URL-encoded). A throwaway `responses`-backed probe established the exact mock registrations before writing the test — no real network involved.

## User Setup Required

None — no external service configuration required. The provider reads existing `Settings` keys (all shipped in Plan 01-01 with safe placeholder defaults); operators set the real Proxmox host/token/CA path and net0 LAN params in the gitignored `.env` when they reach the dev-homelab smoke gate.

## Real-Proxmox Acceptance: DEFERRED

The provider code is authored and CI-proven only against `responses` HTTP mocks (hermetic, zero network). Real clone/start/stop/destroy/IP against a live Proxmox node (`:8006`) is the **dev-homelab smoke gate** — `human_needed`, NOT phase-blocking (no Proxmox reachable from this box; CONTEXT.md Deferred Ideas, RESEARCH Environment Availability). Pool-add ordering vs the clone task (ADR-0003 Open Question 3) is the one detail to verify against the real cluster in that smoke run.

## Next Phase Readiness

- The compute seam is now real-backed and CI-proven: 01-03 (saga) can call `cloneCt`/`startCt`/`stopCt`/`destroyCt` (each UPID-blocked), `getNodeMemory` (capacity guard), `getIp` (computed), and `waitTask` against either the Fake (unit) or the real provider (homelab) with identical observable behavior.
- No blockers. Full gate green: 45 pytest passed, ruff + ruff format + mypy --strict (29 files) + `uv lock --check` + reuse lint (125/125 source files).

---
*Phase: 01-control-plane-api*
*Completed: 2026-06-10*

## Self-Check: PASSED

- Created files verified present: `api/tests/integration/test_proxmox_provider.py`, `api/compute/proxmoxProvider.py` (modified), `.planning/phases/01-control-plane-api/01-02-SUMMARY.md`.
- Task commits verified in git history: `bd99ddc` (chore), `cd55054` (feat), `40bf765` (test).
