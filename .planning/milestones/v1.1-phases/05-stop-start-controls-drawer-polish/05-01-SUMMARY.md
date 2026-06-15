<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 05-stop-start-controls-drawer-polish
plan: 01
subsystem: testing
tags: [vitest, msw, playwright, react, css-source-assert, tdd-red, ui-polish]

# Dependency graph
requires:
  - phase: 02-ui-foundation-terminal
    provides: "TerminalPanel/WorkspaceLayout/useTerminal, the MSW envelope+seed, the MockWebSocket registry, the e2e Fake+stub-ttyd harness"
  - phase: 04-reconciler-drawer-release
    provides: "ActivityDrawer (UI-06) + its renderDrawer MSW harness; the useStopWorkspace/useStartWorkspace hooks (v1.0)"
provides:
  - "POST /api/v1/workspaces/:id/stop and /start MSW handlers ({data,meta,error} envelope + shared 404 shape)"
  - "Failing-first (RED) unit tests for Stop/Start gating, pending+no-double-fire, the stopped placeholder, and the ActivityDrawer width token"
  - "Confirming (GREEN) useTerminal stopped-gate tests (no socket while stopped, teardown on running->stopped, reconnect on stopped->running)"
  - "ui/tests/css-rules.test.ts — CSS-source asserts for the V2 --w-drawer token+375px media override, the V3 :focus-visible ring, the V4 custom scrollbar"
  - "ui/tests/e2e/stop-start.spec.ts — Playwright create->stop->start round-trip + a 375px full-width-drawer viewport test"
  - "Type-only onStop/onStart/stopPending/startPending props on TerminalPanelProps (the locked LeafPanel->panel seam, declared so the Wave-0 tests compile)"
affects: [05-02-stop-start-controls, 05-03-drawer-css-polish, 05-04-e2e-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-0 failing-first: author the RED unit/e2e tests + the MSW handlers before the feature lands in 05-02/05-03"
    - "CSS-source assertion (readFileSync of src/index.css) for jsdom-un-evaluable rules (:focus-visible / ::-webkit-scrollbar / @media width) — the tokens.test.ts precedent"
    - "jsdom inline-style readability: assert the drawer .style.width === 'var(--w-drawer)' (readable) NOT getComputedStyle (un-computable)"
    - "Type-only prop forward-declaration to keep tsc green while the consuming render lands in a later plan"

key-files:
  created:
    - "ui/tests/css-rules.test.ts"
    - "ui/tests/e2e/stop-start.spec.ts"
  modified:
    - "ui/tests/msw/handlers.ts"
    - "ui/src/components/WorkspaceLayout.test.tsx"
    - "ui/src/components/TerminalPanel.test.tsx"
    - "ui/src/components/TerminalPanel.tsx"
    - "ui/src/hooks/useTerminal.test.tsx"
    - "ui/src/components/ActivityDrawer.test.tsx"

key-decisions:
  - "The Stop/Start mutation seam is locked: LeafPanel owns useStop/useStartWorkspace and passes onStop/onStart/stopPending/startPending into TerminalPanel (RESEARCH A2 / UI-SPEC §1). The props were declared (type-only) in this plan so the failing-first tests compile."
  - "useTerminal needs NO production change for the stopped gate — the existing `status !== \"running\"` early-return (line 178) + the [workspaceId,status] teardown already satisfy UI-07/UI-08; the 3 hook tests CONFIRM (GREEN) the contract rather than drive new code (RESEARCH A1)."
  - "V2/V3/V4 are CSS-source asserts in vitest (jsdom cannot evaluate :focus-visible/::-webkit-scrollbar/@media-width); the live-paint proofs live in the Plan-04 Playwright leg, not here."

patterns-established:
  - "Failing-first Wave 0: RED feature tests + live MSW handlers committed as test(05-01) BEFORE the implementation plans turn them GREEN"
  - "Server-truth posture encoded in tests: assert the mutation fired + the pending state, never an immediate optimistic Stop->Start swap on click (Pitfall 1)"

requirements-completed: []  # Wave-0 infra: UI-07..UI-11 are PARTIAL (RED tests authored); they complete in 05-02/05-03/05-04.

# Metrics
duration: 16min
completed: 2026-06-14
---

# Phase 5 Plan 01: Wave-0 Stop/Start Test Infrastructure Summary

**Two stop/start MSW lifecycle handlers + the failing-first RED tests for UI-07..UI-11 (Stop/Start gating, pending, the stopped placeholder, the V2/V3/V4 CSS-source rules, the drawer width token) + a Playwright stop->start + 375px-drawer e2e scaffold — the locked Wave 0 that the 05-02/05-03 feature plans turn green.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-06-14T05:17:38Z (plan load)
- **Completed:** 2026-06-14T05:33:44Z (Task 3 commit)
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- Added the two missing MSW lifecycle handlers (`POST /workspaces/:id/stop` → `stopped`, `/start` → `running`) returning the `{data,meta,error}` envelope and the shared inlined 404 shape, so every gating/pending/round-trip test has a live handler (no `onUnhandledRequest: "error"` hard-fail).
- Authored the failing-first (RED-by-design) unit tests for UI-07/UI-08 (Stop/Start gating by status, immediate-no-confirm Stop, disabled+`aria-busy`+no-double-fire pending, the `Workspace stopped` placeholder with `role="status"`, both-Start-affordances-disable), UI-09 (the ActivityDrawer `width: var(--w-drawer)` token), and the V2/V3/V4 CSS-source rules.
- Confirmed (GREEN) the `useTerminal` stopped gate: 0 sockets while stopped, socket teardown on `running→stopped`, fresh socket on `stopped→running` — the existing line-178 gate already holds, so these lock the contract without new hook code.
- Scaffolded `ui/tests/e2e/stop-start.spec.ts` (the create→stop→placeholder→start→reconnect journey via `waitForResponse` POST asserts + a 375px full-width-drawer viewport test), wired into the existing Playwright harness with no harness change.

## Task Commits

Each task was committed atomically:

1. **Task 1: MSW stop/start handlers + WorkspaceLayout mutation tests** - `15b0f2e` (test)
2. **Task 2: Failing-first TerminalPanel + useTerminal stopped-gate tests** - `91a39e8` (test)
3. **Task 3: CSS-source V2/V3/V4 test, drawer width-token test, e2e scaffold** - `7638a55` (test)

**Plan metadata:** _(this commit — docs(05-01))_

## Files Created/Modified

- `ui/tests/msw/handlers.ts` - Added `POST /workspaces/:id/stop` and `/start` handlers (envelope + shared 404 on a missing id).
- `ui/src/components/WorkspaceLayout.test.tsx` - Two RED integration tests asserting Stop/Start fire `POST /workspaces/{id}/stop|start` (captured id) and keep the panel mounted (not pruned like terminate).
- `ui/src/components/TerminalPanel.test.tsx` - Five RED tests: gating, immediate-no-confirm Stop, pending disable+`aria-busy`+no-double-fire, the `Workspace stopped` placeholder (heading+copy+CTA+`role=status`, no overlays), both-Start-affordances-disable.
- `ui/src/components/TerminalPanel.tsx` - Declared optional `onStop`/`onStart`/`stopPending`/`startPending` props on `TerminalPanelProps` (type-only forward decl of the locked seam; no behavior change).
- `ui/src/hooks/useTerminal.test.tsx` - Three GREEN stopped-gate tests over the `MockWebSocket` registry (no socket while stopped, teardown on flip, reconnect).
- `ui/tests/css-rules.test.ts` - **New.** `readFileSync` of `src/index.css`; RED asserts for the V2 `--w-drawer` token + 375px media override, the V3 `:focus-visible` ring, the V4 `::-webkit-scrollbar-thumb` + Firefox scrollbar tokens.
- `ui/src/components/ActivityDrawer.test.tsx` - One RED test asserting the dialog `<aside>` reads `width: var(--w-drawer)` (inline `.style.width`).
- `ui/tests/e2e/stop-start.spec.ts` - **New.** The Playwright stop→start round-trip + 375px drawer-width viewport test (runs only in the Plan-04 e2e gate; excluded from vitest).

## Decisions Made

- **Mutation seam locked to `LeafPanel`-owns-the-mutations** (RESEARCH A2 / UI-SPEC §1): the `onStop`/`onStart`/`stopPending`/`startPending` props were declared on `TerminalPanelProps` in this plan (type-only) so the Wave-0 tests compile against the contract 05-02 will render against.
- **`useTerminal` is test-only this plan** (RESEARCH A1): the stopped gate already holds in production, so the three hook tests are GREEN confirmations, not RED drivers. No production hook change was made.
- **V2/V3/V4 stay CSS-source asserts in vitest** (jsdom boundary): the live-paint / media-width proofs are deferred to the Plan-04 Playwright leg, honoring the locked jsdom-vs-Playwright split.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Declared the not-yet-rendered Stop/Start props on `TerminalPanelProps`**
- **Found during:** Task 2 (Failing-first TerminalPanel tests)
- **Issue:** The failing-first tests pass `onStop`/`onStart`/`stopPending`/`startPending` to `<TerminalPanel>`, but those props did not exist on `TerminalPanelProps`. The plan's verify requires `tsc --noEmit` to exit 0; passing unknown props fails the excess-property check, so the test file would not compile.
- **Fix:** Added the four props as **optional, type-only** members of `TerminalPanelProps` (no destructure, no behavior), matching the locked `LeafPanel`→panel seam (RESEARCH A2). The component still renders nothing for them, so the tests stay RED at runtime (the intended Wave-0 state) while compiling cleanly.
- **Files modified:** `ui/src/components/TerminalPanel.tsx`
- **Verification:** `cd ui && npm run typecheck` exits 0; the five TerminalPanel feature tests are RED for the right reason ("Unable to find … role 'button' and name 'Stop workspace'"), not a compile error.
- **Committed in:** `91a39e8` (Task 2 commit)

**2. [Rule 3 - Blocking] biome import-order + format fixes on the new/edited test files**
- **Found during:** Tasks 2 and 3 (lint gate)
- **Issue:** `biome ci` flagged the inserted `import type { WorkspaceStatus }` (out of the sorted relative-import order) in `useTerminal.test.tsx`, and three single-call `expect(...)` blocks biome collapses to one line (`TerminalPanel.test.tsx`, `css-rules.test.ts`).
- **Fix:** Reordered the import to the biome-sorted position and collapsed the over-wrapped `expect` calls — formatting-only, no logic change.
- **Files modified:** `ui/src/hooks/useTerminal.test.tsx`, `ui/src/components/TerminalPanel.test.tsx`, `ui/tests/css-rules.test.ts`
- **Verification:** `cd ui && npm run lint` (biome ci) clean across all 50 files.
- **Committed in:** `91a39e8` and `7638a55` (part of the respective task commits)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking: one type-only forward-decl to unblock `tsc`, one lint/format cleanup).
**Impact on plan:** Both were required to satisfy the plan's own lint+typecheck gates. No scope creep; no production behavior was added (the props are inert until 05-02 renders against them).

## Issues Encountered

None. Every RED test failed for its intended reason (missing button / missing CSS rule / un-swapped token), and the MSW handlers resolved (no `onUnhandledRequest` error). The `useTerminal` stopped-gate tests passed first try (the gate already holds, per RESEARCH A1).

## Known Stubs

None. This is a Wave-0 test-infrastructure plan — the RED feature tests are intentional failing-first specs (not stubs); they go green when 05-02/05-03 land the feature. No hardcoded UI value, placeholder copy, or unwired data source was introduced in shipped source (the only source touched, `TerminalPanel.tsx`, gained inert type-only props).

## Test Results (expected Wave-0 state)

- **vitest:** 100 passed, 13 RED-by-design (2 WorkspaceLayout stop/start, 5 TerminalPanel gating/pending/placeholder, 5 css-rules V2/V3/V4, 1 ActivityDrawer width token). The 3 `useTerminal` stopped-gate tests are GREEN (confirming the already-holding gate).
- **lint:** `biome ci .` clean (50 files).
- **typecheck:** `tsc --noEmit` exits 0 (including the new e2e spec).
- **e2e:** not run here (the `stop-start.spec.ts` scaffold runs in the Plan-04 `npm run e2e` gate over the built UI).

## Next Phase Readiness

- **05-02 (Stop/Start controls)** can now turn the WorkspaceLayout + TerminalPanel RED tests GREEN: render the gated Stop/Start header buttons + the `stopped` placeholder + wire `LeafPanel`'s `useStop/useStartWorkspace` into the declared `onStop`/`onStart`/`stopPending`/`startPending` props.
- **05-03 (Drawer CSS polish)** can turn the `css-rules.test.ts` + ActivityDrawer-width RED tests GREEN: add the `--w-drawer` token + 375px media override, the `:focus-visible` ring, and the custom scrollbar to `index.css`, and swap `ActivityDrawer`'s `DRAWER_WIDTH` literal for `var(--w-drawer)`.
- **05-04 (e2e gate)** runs the authored `stop-start.spec.ts` over the built UI.
- No blockers. No production behavior shipped that could regress the 100 passing tests.

## Self-Check: PASSED

All 9 created/modified files exist on disk and all 3 task commits (`15b0f2e`, `91a39e8`, `7638a55`) are in the git history.

---
*Phase: 05-stop-start-controls-drawer-polish*
*Completed: 2026-06-14*
