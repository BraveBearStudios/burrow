<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 09-auto-node-selection
plan: 03
subsystem: ui
tags: [new-workspace-modal, auto-node-selection, react, vitest, msw, form-validation, optional-type]

# Dependency graph
requires:
  - phase: 09-auto-node-selection
    plan: 02
    provides: "WorkspaceCreate.node Optional[str]=None backend contract (null/omitted = auto-select least-loaded; string = manual pick); create response echoes the chosen node on the row"
provides:
  - "ui WorkspaceCreate.node is optional (node?: string | null) mirroring the backend Optional[str]=None"
  - "NewWorkspaceModal defaults to an Auto (least-loaded) option, drops the first-node-on-mount default, accepts Auto as a valid form state, and submits node: null for Auto (a node string for a manual pick)"
  - "MSW POST /api/v1/workspaces handler derives the least-loaded seed node when the request omits node, mirroring the backend auto-fill"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Empty-string select sentinel as the Auto signal: the default <option value=\"\">Auto (least-loaded)</option> maps to node: null at submit (node || null) with no separate flag/state"
    - "Optional UI request field (node?: string | null) tracks the backend Optional[str]=None so the auto/manual signal is one field on both sides"
    - "MSW handler mirrors the backend auto-fill (least-loaded, tie by name asc) via a single autoSelectedNode() derivation so the auto-path response carries a real node string"
    - "Failing-first vitest captures the POST body via a server.use override to assert node null (Auto) vs node string (manual) at the trust boundary"

key-files:
  created: []
  modified:
    - ui/src/types/workspace.ts
    - ui/src/components/NewWorkspaceModal.tsx
    - ui/tests/msw/handlers.ts
    - ui/src/components/NewWorkspaceModal.test.tsx

key-decisions:
  - "The empty string \"\" is the Auto sentinel (the modal's existing node state default); the first-node-on-mount useEffect is removed so \"\" persists, and submit sends node || null so Auto becomes node: null"
  - "isValid drops the node requirement entirely (name + projectRepo only) so Auto is a valid form state; the Node select keeps its onBlur touched-marker but no required helper renders for it"
  - "MSW autoSelectedNode() reuses the seed node capacity (least-loaded among at/under-threshold, tie by name asc) so the fake's auto-fill matches the backend selectNode rule and the round trip is realistic"
  - "Auto and manual share the same select; manual pick remains byte-for-byte the prior path (node string sent verbatim) so the existing manual-path tests stay green unchanged"

requirements-completed: [WSX-01]

# Metrics
duration: ~7min
completed: 2026-06-16
---

# Phase 9 Plan 03: Create-Modal Auto (Least-Loaded) Option Summary

**`NewWorkspaceModal` now defaults to an "Auto (least-loaded)" node option (the first-node-on-mount default removed), accepts Auto as a valid form state, and submits `node: null` so the backend auto-selects — while a manual pick still sends the chosen node string unchanged; `WorkspaceCreate.node` becomes optional to mirror the backend `Optional[str]=None`, and three failing-first vitest cases prove Auto-default + null-payload + manual-still-works.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-06-16T07:40Z
- **Completed:** 2026-06-16
- **Tasks:** 2 (Task 1 impl; Task 2 TDD failing-first tests)
- **Files modified:** 4 (3 source + 1 test, all pre-existing)

## Accomplishments
- Made `WorkspaceCreate.node` optional in the UI types (`node?: string | null`), mirroring the Plan 02 backend `Optional[str] = None` contract (null/omitted = auto, a string = manual). camelCase + SPDX header preserved.
- Added the operator-facing Auto path to `NewWorkspaceModal`:
  - Prepended `<option value="">Auto (least-loaded)</option>` as the first option and the selected default.
  - Removed the first-node-on-mount `useEffect` (`if (!node && nodes?.length) setNode(nodes[0].node)`) so the empty-string Auto sentinel persists as the default.
  - Dropped `node` from `isValid` (`name + projectRepo` only) so Auto is a valid form state and Create enables without a manual node pick.
  - Changed the submit payload to `node: node || null` so the Auto sentinel sends `node: null` (backend auto-selects) and a manual pick sends the chosen node string (unchanged path).
- Updated the MSW POST `/api/v1/workspaces` handler to derive the least-loaded seed node (via a single `autoSelectedNode()` mirroring the backend's least-loaded/tie-by-name-asc rule) when `body.node` is absent, so the auto-path response row carries a real node string like the backend.
- Added three failing-first vitest cases: Auto is the default + Create is enabled with only Name + Git repo; Auto submits with `node: null` (captured via an MSW body-capture override) and opens the panel + closes; manual pick still submits `node: "node1"`.

## Task Commits

1. **Task 1 (optional type + Auto default modal + MSW auto-fill)** — `a742662` (feat)
2. **Task 2 (failing-first vitest: Auto default + null payload + manual unchanged)** — `b630430` (test)

**Plan metadata:** (final commit) `docs(09-03): complete create-modal auto option plan`

## Files Created/Modified
- `ui/src/types/workspace.ts` — `WorkspaceCreate.node` is now `node?: string | null` (auto/manual signal mirroring the backend Optional).
- `ui/src/components/NewWorkspaceModal.tsx` — Auto default `<option>`, first-node-on-mount effect removed, `isValid` no longer references `node`, submit sends `node: node || null`.
- `ui/tests/msw/handlers.ts` — `autoSelectedNode()` helper + the POST handler derives the least-loaded node when `body.node` is absent.
- `ui/src/components/NewWorkspaceModal.test.tsx` — three new tests (Auto default + valid, Auto submits null, manual submits node string) under a new `WSX-01` describe block; imports `WorkspaceCreate` for the body-capture override.

## Test Results
- **Modal suite** (`npx vitest run src/components/NewWorkspaceModal.test.tsx`): **9 passed** (6 existing manual-path/validation/error tests unchanged + 3 new Auto tests).
- **Full ui suite** (`npx vitest run`): **117 passed / 15 files** — zero regressions.
- **Typecheck** (`npx tsc --noEmit`): **0 errors** — the optional `node?: string | null` type-checks across the modal, hook, and MSW consumers.
- **Lint** (`npx biome ci .`, the repo's CI lint command): **clean** (50 files checked).

## TDD Gate Compliance
Task 2 was TDD failing-first. The load-bearing RED-vs-pre-Task-1 assertions are verifiable from the prior modal source: the pre-Task-1 modal's first-node-on-mount effect set the select to `node1` (so `expect(select.value).toBe("")` fails RED) and sent `node` as the `"node1"` string (so the Auto-submit `node` null assertion fails RED). After Task 1 both turn GREEN. Per the plan's structure (impl Task 1 before test Task 2 in one wave), the gate commits are `feat` (`a742662`) followed by `test` (`b630430`); both were committed only with the full modal + full ui suite GREEN.

## Decisions Made
None beyond the LOCKED contract — the plan and 09-CONTEXT dictated the Auto-default, the first-node-default removal, the `node?: string | null` optional type, the `node: null` Auto payload, and the MSW auto-fill. Implemented exactly. The empty-string Auto sentinel reuses the modal's existing `node` state default (no new state), and the MSW `autoSelectedNode()` mirrors the backend least-loaded/tie-by-name rule for a realistic round trip.

## Deviations from Plan
None - plan executed exactly as written.

One minor self-introduced lint fix (Rule 3, blocking): biome's import-organize ordering required the `import type { WorkspaceCreate }` line to follow `useLayoutStore` alphabetically in the test file; reordered before the Task 2 commit so `biome ci .` is clean.

## Issues Encountered
None. Task 1 typecheck + the existing modal tests passed on the first run (manual path preserved); the three new Task 2 tests passed first run against the Task-1 modal.

## Known Stubs
None. The Auto path is wired end-to-end in the UI: the empty-string sentinel submits `node: null`, the MSW handler (and the real backend per Plan 02) auto-selects the least-loaded node and returns it on the created row, and the panel opens on the resolved row. Manual pick is the unchanged path. No placeholder text, no empty-data render, no unwired component.

## Threat Surface Scan
No new security-relevant surface beyond the plan's `<threat_model>`. The change is a UI convenience layer (T-09-03): the modal sends either `node: null` (Auto) or a node string the operator picked from the `useNodes` list — it does not let the operator type an arbitrary node string into the payload, and the authoritative validation stays server-side (Plan 02 `selectNode` + the step-0 guard over `worker_nodes`). No new endpoint, auth path, or trust boundary; no npm packages added (T-09-SC).

## User Setup Required
None — no external service configuration. The Auto default is the new one-click create path; manual node selection remains available in the same select.

## Next Phase Readiness
- WSX-01 is now complete end-to-end: backend auto-select (Plans 01–02) + the create-modal Auto option (this plan). An operator can create a workspace without picking a node and the control plane auto-selects the least-loaded fitting node; manual pick stays available and unchanged.

## Self-Check: PASSED

All modified files verified present on disk and the two task commits (`a742662`, `b630430`) verified in git log.

---
*Phase: 09-auto-node-selection*
*Completed: 2026-06-16*
