<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 01
subsystem: api
tags: [websockets, ttyd, terminal-proxy, fastapi, capacity, ssrf, cswsh]

# Dependency graph
requires:
  - phase: 01-control-plane-api
    provides: "DbProvider.getWorkspace/logEvent, ComputeProvider.getNodeMemory, the {data,meta,error} envelope, the get_compute/get_db DI seams, Settings (default_node, capacity_threshold, allowed_origin), the integration tier (ASGITransport + real temp SQLite + Fake + respx stub-ttyd)"
provides:
  - "tty-subprotocol WebSocket terminal bridge at /ws/workspaces/{id}/terminal — opaque, type-preserving relay (TERM-01..04)"
  - "Protocol-accurate stub_ttyd_ws test fixture (websockets.serve, tty subprotocol, JSON init, '0'-prefixed echo) that makes the SC-7 .encode() regression fail CI"
  - "GET /api/v1/nodes — read-only per-node capacity endpoint (memoryUsedFraction + capacityThreshold + overThreshold) for UI-04"
  - "websockets==16.0 pinned + locked"
affects: [02-02, 02-03, 02-05, 02-06]

# Tech tracking
tech-stack:
  added: [websockets==16.0]
  patterns:
    - "Opaque type-preserving WS relay: forward each frame verbatim (str→send_text, bytes→send_bytes), NEVER .encode() — preserve text-vs-binary on BOTH legs (SC-7)"
    - "FIRST_COMPLETED teardown: race the two pump directions, cancel + gather(return_exceptions=True) the loser, ping_interval keepalive bounds FD growth (no half-open leak)"
    - "Pre-accept access gate: getWorkspace + status==running + lxc_ip checked BEFORE accept; close(1008) on reject (no upstream dial)"
    - "Explicit Origin gate (CSWSH): Starlette WS bypass CORS, so the Origin header is checked vs settings.allowed_origin and closed 1008 before accept"
    - "SSRF source discipline: the upstream ttyd URL is built ONLY from the DB row's lxc_ip via a single _ttyd_url() function (the test-only seam tests monkeypatch to redirect the dial)"
    - "Degrade-not-500 capacity read: getNodeMemory behind a try/except returns a null fraction + overThreshold=false at HTTP 200 (mirrors health.py _safe)"
    - "Protocol-accurate stub over a bare echo: the stub asserts the tty subprotocol + JSON init and echoes preserving frame type, so a relay that drops the subprotocol or re-encodes a text frame fails CI"

key-files:
  created:
    - api/routers/terminal.py
    - api/routers/nodes.py
    - api/tests/integration/test_terminal_proxy.py
    - api/tests/integration/test_nodes.py
  modified:
    - api/pyproject.toml
    - api/uv.lock
    - api/main.py
    - api/tests/integration/conftest.py

key-decisions:
  - "The terminal bridge lives OUTSIDE /api/v1 (prefix /ws) per the CLAUDE.md /ws/* WS convention; the nodes endpoint is a standard /api/v1 envelope route."
  - "overThreshold is the strict CAP-01 guard (fraction > threshold); the boundary (== threshold) is deliberately NOT over, mirroring the Phase-1 capacity guard."
  - "GET /api/v1/nodes exposes only what getNodeMemory can actually supply (the real used-memory FRACTION + the configured threshold) — no fabricated 'free GB'; the UI derives its chip text from these real numbers (UI-04)."
  - "settings.capacity_threshold is read LIVE per request so a runtime override is honored (the over-threshold test monkeypatches it)."
  - "The nodes endpoint iterates a single-element node list (settings.default_node) so the per-node-chips contract already holds when the config grows."

patterns-established:
  - "WS bridge teardown: asyncio.wait(FIRST_COMPLETED) + cancel pending + gather(return_exceptions=True)"
  - "Degrade-not-500 read endpoint: per-item try/except around the provider call, null the failed field, never raise 500"

requirements-completed: [TERM-01, TERM-02, TERM-03, TERM-04, UI-04]

# Metrics
duration: 14min
completed: 2026-06-10
---

# Phase 2 Plan 01: Terminal Proxy Backend + Nodes Capacity Summary

**tty-subprotocol WebSocket terminal bridge (opaque, type-preserving, FIRST_COMPLETED teardown, SSRF + CSWSH + pre-accept gates) proven against a protocol-accurate stub ttyd, plus a degrade-not-500 GET /api/v1/nodes capacity endpoint for UI-04; websockets pinned to 16.0.**

## Performance

- **Duration:** 14 min (this resume session; Task 3 + tracking)
- **Completed:** 2026-06-10
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- **TERM-01..04 WS bridge** (`api/routers/terminal.py`): an opaque, type-preserving relay between the browser xterm and the worker ttyd. Negotiates the `tty` subprotocol on the upstream leg, forwards every frame verbatim preserving text-vs-binary on BOTH legs (never `.encode()` — the SC-7 corruption bug), tears down with `FIRST_COMPLETED` + cancel + `gather` (no half-open upstream leak), rejects a non-running/missing workspace with WS close `1008` before accept, emits a typed `{type:error, code:LXC_NOT_READY}` frame when ttyd is unreachable, gates the Origin header against `settings.allowed_origin` (CSWSH), builds the upstream URL ONLY from the DB row's `lxc_ip` (SSRF), and logs `terminal.connected`/`terminal.disconnected` with `{}` data only (no content leak).
- **Protocol-accurate stub ttyd fixture** (`stub_ttyd_ws` in `conftest.py`): a real in-process `websockets.serve` server that asserts the `tty` subprotocol, requires the JSON init (`AuthToken/columns/rows`), and echoes `'0'`-prefixed INPUT as `'0'`-prefixed OUTPUT preserving frame type — so a relay that drops the subprotocol or re-encodes a text frame FAILS CI (not a hideable bug).
- **GET /api/v1/nodes capacity endpoint** (`api/routers/nodes.py`): a thin, envelope-wrapped, read-only per-node view returning `{node, memoryUsedFraction, capacityThreshold, overThreshold}` over the Fake provider. `overThreshold` is the strict `fraction > threshold` flag (boundary `==` is NOT over, mirrors CAP-01). Degrades to a null fraction + `overThreshold=false` at HTTP 200 when `getNodeMemory` raises — never a 500 error oracle (T-02-06). Wired in `create_app()` via the deferred-import seam; no driver leak.
- **websockets==16.0** pinned in `pyproject.toml` + re-locked, replacing the stale 14.1.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin websockets + protocol-accurate stub-ttyd fixture** - `dbb3bfe` (test)
2. **Task 2: tty-subprotocol WS bridge + TERM-01..04 tests** - RED `7297e98` (test) → GREEN `a53d640` (feat)
3. **Task 3: GET /api/v1/nodes capacity endpoint (UI-04 backend)** - RED was authored with Task 2's RED set; GREEN `7a9e644` (feat)

**Plan metadata:** committed with this SUMMARY + STATE/ROADMAP/REQUIREMENTS updates (docs).

_Note: this plan was resumed mid-execution; Tasks 1–2 and the RED for Task 3 landed in a prior session (commits above), and this session implemented the nodes GREEN + tracking._

## Files Created/Modified

- `api/routers/terminal.py` - tty-subprotocol WS bridge (Origin gate, pre-accept access gate, SSRF-safe upstream dial, FIRST_COMPLETED teardown, LXC_NOT_READY error frame)
- `api/routers/nodes.py` - GET /api/v1/nodes per-node capacity (fraction + threshold + over flag), degrade-not-500
- `api/tests/integration/test_terminal_proxy.py` - TERM-01..04 bridge tests over the stub ttyd (both-directions, text-preservation SC-7 gate, unreachable error frame, no-halfopen teardown, non-running 1008, Origin gate, connect/disconnect logging)
- `api/tests/integration/test_nodes.py` - the four UI-04 capacity contract tests (list, envelope camelCase, strict over-threshold boundary, degrade-not-500)
- `api/main.py` - registered `nodes.router` (and `terminal.router`) in create_app()
- `api/tests/integration/conftest.py` - added the protocol-accurate `stub_ttyd_ws` fixture + `StubTtyd` handle
- `api/pyproject.toml` - `websockets==16.0` pin
- `api/uv.lock` - re-locked with websockets 16.0

## Decisions Made

- The terminal bridge lives OUTSIDE `/api/v1` (prefix `/ws`) per the CLAUDE.md `/ws/*` convention; the nodes endpoint is a standard `/api/v1` envelope route.
- `overThreshold` is the strict CAP-01 guard (`fraction > threshold`); the boundary (`== threshold`) is deliberately NOT over.
- The nodes endpoint exposes only the real fraction + threshold the provider can supply (no fabricated "free GB"); the UI derives its capacity chip from these real numbers.
- `settings.capacity_threshold` is read live per request so a runtime override is honored.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed an orphan `.planning/ROADMAP.md.tmp` artifact**
- **Found during:** Task 3 (full-gate run before SUMMARY)
- **Issue:** A 1-byte untracked `.planning/ROADMAP.md.tmp` (a leftover from the prior interrupted run's `roadmap.update`) made the repo-wide `reuse lint` SPDX gate fail (1 file without a header).
- **Fix:** Deleted the stray temp file. `ROADMAP.md` itself was intact (19 KB); the temp was an orphan never committed.
- **Files modified:** removed `.planning/ROADMAP.md.tmp` (untracked, no commit)
- **Verification:** `uvx --with charset-normalizer reuse lint` → "168/168 files with copyright + license; compliant."

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The temp-file removal was cleanup of a prior-run artifact blocking the SPDX gate. No scope creep, no source change.

## Issues Encountered

None for the nodes implementation — the RED contract in `test_nodes.py` fully specified the response shape (exactly `{node, memoryUsedFraction, capacityThreshold, overThreshold}`, strict over-threshold boundary, and the degrade-not-500 path), so the endpoint went green on first run.

## Validation

Full api gate green (Windows, `uv`):

- `cd api && uv run pytest` — **127 passed** (4 new `test_nodes` + 9 `test_terminal_proxy` + all prior tiers).
- `uv run ruff check .` — All checks passed.
- `uv run ruff format --check .` — 54 files already formatted.
- `uv run mypy . --strict` — Success: no issues found in 54 source files.
- `uvx --with charset-normalizer reuse lint` — compliant (168/168).
- Seam-leakage stays green: `routers/nodes.py` imports no concrete driver (Fake/Proxmox/SQLite).

SC-7 self-check (from the prior GREEN of Task 2): substituting `send_bytes(msg.encode())` on the down leg makes `test_preserves_text_frame` FAIL against the protocol-accurate stub.

## User Setup Required

None - no external service configuration required (v1 is LAN-only no-auth by design; the bridge is CI-provable over the Fake provider + stub ttyd with zero real Proxmox).

## Next Phase Readiness

- The server contract the entire Phase-2 UI consumes is now in place and CI-green: the WS bridge (consumed by `02-03` useTerminal/TerminalPanel) and `GET /api/v1/nodes` (consumed by `02-05` Navbar capacity chips + StatusBar).
- The UI half of UI-04 (rendering the capacity chip from `memoryUsedFraction`/`overThreshold`) lands in **02-05**; this plan delivered only the backend half.
- Plan 02-02 (UI foundation: pinned stack, typed envelope client + ttyd frame lib) is the next plan and has no dependency blockers from this plan.

## Self-Check: PASSED

- Files: `api/routers/terminal.py`, `api/routers/nodes.py`, `api/tests/integration/test_terminal_proxy.py`, `api/tests/integration/test_nodes.py`, `02-01-SUMMARY.md` — all FOUND.
- Commits: `dbb3bfe`, `7297e98`, `a53d640`, `7a9e644` — all FOUND.

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
