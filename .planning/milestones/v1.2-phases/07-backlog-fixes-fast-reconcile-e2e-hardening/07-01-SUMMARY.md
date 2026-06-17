<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 07-backlog-fixes-fast-reconcile-e2e-hardening
plan: 01
subsystem: ui
tags: [react, tanstack-query, zustand, playwright, vitest, react-mosaic, e2e]

# Dependency graph
requires:
  - phase: 02-ui-foundation
    provides: useTerminal onTerminalEvent seam, useInvalidateWorkspaces / WORKSPACES_KEY, layoutStore (status never mirrored)
  - phase: 05-frontend-stop-start-drawer-polish
    provides: LeafPanel onStop/onStart wiring, stopped-panel placeholder CTA, stop-start.spec.ts round-trip
provides:
  - "UI-12: LeafPanel wires onTerminalEvent -> useInvalidateWorkspaces so a terminal error/close fast-reconciles the workspace list (Pitfall 4) ahead of the ~3s poll"
  - "CICD-09: stop-start.spec.ts hardened with panel-scoped locators (data-testid=panel-${id}) + per-test id-scoped backend cleanup"
affects: [phase-09-auto-node-selection, future-e2e-specs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fast-reconcile is invalidation-only: a terminal event invalidates WORKSPACES_KEY; the server stays the single source of truth (no Zustand status mirror)"
    - "Per-panel e2e scoping via data-testid=panel-${id} on the TerminalPanel <section>; per-test id-scoped DELETE cleanup in afterEach"

key-files:
  created: []
  modified:
    - ui/src/components/WorkspaceLayout.tsx
    - ui/src/components/WorkspaceLayout.test.tsx
    - ui/src/components/TerminalPanel.tsx
    - ui/tests/e2e/stop-start.spec.ts

key-decisions:
  - "Drove the RED test via MockWebSocket.emitClose() -> useTerminal.onclose -> scheduleReconnect -> onTerminalEvent('closed'); spied the QueryClient.invalidateQueries for WORKSPACES_KEY and asserted layoutStore grew no status field"
  - "Scoped the stopped-panel Start click to the role=status placeholder region to disambiguate the two 'Start workspace' affordances (header icon button + placeholder CTA) under Playwright strict mode"
  - "Per-test cleanup deletes only the ids each test created (tracked in a module array, drained in afterEach) -- never a broad wipe (test-integrity threat mitigation)"

patterns-established:
  - "Pattern 1: e2e locators scope to the panel under test via getByTestId(`panel-${id}`); no unscoped .first(), no global [data-testid^=term-] count assertions"
  - "Pattern 2: e2e backend isolation tracks created workspace ids and DELETEs them id-scoped in afterEach, keeping a mode:serial Fake-backed suite order-independent"

requirements-completed: [UI-12, CICD-09]

# Metrics
duration: 10min
completed: 2026-06-15
---

# Phase 7 Plan 01: Fast-Reconcile Wiring (UI-12) + E2E Hardening (CICD-09) Summary

**LeafPanel now wires onTerminalEvent -> useInvalidateWorkspaces so a terminal error/close fast-reconciles the workspace list ahead of the ~3s poll, and stop-start.spec.ts is hardened with panel-scoped locators + per-test id-scoped backend cleanup.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-15T05:38:55Z
- **Completed:** 2026-06-15T05:49:31Z
- **Tasks:** 2 (Task 1 split RED/GREEN)
- **Files modified:** 4

## Accomplishments
- UI-12: closed the dead Pitfall-4 fast-reconcile seam — `LeafPanel` calls `useInvalidateWorkspaces()` and passes it as `onTerminalEvent` to `TerminalPanel`, mirroring the existing `onTerminate` wiring; a terminal error/close invalidates `WORKSPACES_KEY` immediately instead of waiting for the ~3s poll.
- UI-12: landed a failing-first vitest test that drives a real terminal close and asserts the invalidation fired AND that no workspace status leaked into the Zustand layoutStore (server stays source of truth).
- CICD-09: hardened `stop-start.spec.ts` — added `data-testid=panel-${id}` to the `TerminalPanel` `<section>`, scoped every locator to the panel under test, removed all unscoped `.first()` and the global `[data-testid^="term-"].toHaveCount(0)`, and added an `afterEach` that DELETEs only each test's created ids.
- All gates green: vitest 114/114, typecheck clean, lint clean, build clean, e2e 7/7 over the Fake + stub ttyd.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing-first fast-reconcile invalidation (UI-12)** - `54bc89c` (test)
2. **Task 1 (GREEN): wire LeafPanel onTerminalEvent fast-reconcile (UI-12)** - `492e4ce` (feat)
3. **Task 2: harden stop-start e2e — scoped locators + per-test isolation (CICD-09)** - `5332ea0` (test)

_Note: TDD Task 1 has the RED test commit followed by the GREEN production commit._

## Files Created/Modified
- `ui/src/components/WorkspaceLayout.tsx` - LeafPanel imports + calls `useInvalidateWorkspaces()` and passes it as `onTerminalEvent` to TerminalPanel (the UI-12 production change).
- `ui/src/components/WorkspaceLayout.test.tsx` - New UI-12 describe block: drives a terminal close, spies `QueryClient.invalidateQueries` for `WORKSPACES_KEY`, asserts no Zustand status mirror. `renderLayout` now returns the QueryClient for spying.
- `ui/src/components/TerminalPanel.tsx` - Added `data-testid={`panel-${id}`}` to the root `<section>` for stable per-panel e2e scoping.
- `ui/tests/e2e/stop-start.spec.ts` - Panel-scoped locators throughout; `createWorkspace` returns the panel locator and tracks the created id; `afterEach` id-scoped cleanup; round-trip Start click scoped to the `role=status` placeholder region.

## Decisions Made
- The fast-reconcile RED test asserts the INVALIDATION path specifically (spies `invalidateQueries({ queryKey: WORKSPACES_KEY })` after a driven terminal close), not the poll's own refetch — proving the wiring, per the plan's specifics.
- The "no status mirror" guarantee is asserted by snapshotting `layoutStore` before/after the close and checking `mosaicNode`/`activeWorkspaceId` are unchanged and the store has no `status` property.
- Chose `request.delete` (direct API) over UI-driven terminate for per-test cleanup — faster, no UI flake (Claude's-discretion option recommended in CONTEXT).
- Kept `mode: serial` — the suite shares one Fake backend across tests; id-scoped `afterEach` cleanup makes it order-independent without needing parallel isolation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Disambiguated the stopped panel's two `Start workspace` affordances**
- **Found during:** Task 2 (e2e attempt 1)
- **Issue:** Once locators were scoped to the panel, `panel.getByRole("button", { name: "Start workspace" })` matched 2 elements (the header icon button + the placeholder CTA, both `aria-label="Start workspace"`) and Playwright strict mode threw. The old spec hid this with an unscoped `.first()` — exactly the fragility CICD-09 targets.
- **Fix:** Scoped the Start click to the `role=status` placeholder region (`panel.getByRole("status").filter({ hasText: "Workspace stopped" })`), targeting the placeholder CTA unambiguously.
- **Files modified:** ui/tests/e2e/stop-start.spec.ts
- **Verification:** e2e attempt 2 green (7/7).
- **Committed in:** `5332ea0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix was required for the hardened spec to pass and directly furthers CICD-09's robustness goal. No scope creep.

## Issues Encountered
- First e2e run surfaced the two-`Start workspace`-affordance strict-mode violation (see Deviation 1); resolved by placeholder-region scoping and the suite went green on the second run. Ports 8000/7681/4173 were free both runs; no process-kill thrash needed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7 plan complete (1/1). UI-12 + CICD-09 closed and CI-provable over the Fake provider.
- The `data-testid=panel-${id}` per-panel scoping convention and the id-scoped `afterEach` cleanup are now available for future e2e specs.
- Phase 8 (release hardening) and Phase 9 (auto node selection) touch disjoint surfaces and have no dependency on this work.

---
*Phase: 07-backlog-fixes-fast-reconcile-e2e-hardening*
*Completed: 2026-06-15*

## Self-Check: PASSED

- All 4 modified source files + the SUMMARY.md exist on disk.
- All 3 task commits (54bc89c, 492e4ce, 5332ea0) present in git history.
