<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 05-stop-start-controls-drawer-polish
plan: 02
subsystem: frontend-ui
tags: [react, tdd-green, ui-07, ui-08, stop-start, terminal-panel, lifecycle, tokens-only]

# Dependency graph
requires:
  - phase: 05-stop-start-controls-drawer-polish
    plan: 01
    provides: "The RED unit tests (gating/pending/placeholder/mutation-spy), the MSW stop/start handlers, and the type-only onStop/onStart/stopPending/startPending props on TerminalPanelProps"
  - phase: 04-reconciler-drawer-release
    provides: "useStopWorkspace/useStartWorkspace TanStack hooks (v1.0), the ActivityDrawer the panel mounts closed"
  - phase: 02-ui-foundation-terminal
    provides: "TerminalPanel/WorkspaceLayout/useTerminal, iconButtonStyle/ICON/overlayBase/overlayButton/Spinner, lib/status.ts, the four-theme @theme tokens"
provides:
  - "Status-gated Stop/Start header icon buttons (UI-07/UI-08) with immediate-no-confirm Stop + disabled+aria-busy+14px-spinner pending feedback"
  - "The `Workspace stopped` placeholder body branch (role=status, calm --bg-surf wash, Start CTA) rendered BEFORE the termStatus overlays"
  - "LeafPanel wiring of useStopWorkspace/useStartWorkspace into onStop/onStart + stopPending/startPending (no closePanel — the panel survives a stop)"
affects: [05-03-drawer-css-polish, 05-04-e2e-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Show-only-applicable lifecycle gating: render exactly one of Stop/Start by status, never disable-both; the backend state machine is the authority"
    - "Server-is-source-of-truth: stop/start never mirror status into Zustand; onSettled invalidation + the ~3s poll drive the Stop<->Start + placeholder<->terminal swap"
    - "Status-stopped body branch placed BEFORE the termStatus overlays so a transient termStatus can't flash an error scrim during the running->stopped tear-down"
    - "Two co-located Start affordances (header button + placeholder CTA) share startPending so a stopped panel cannot double-fire start"

key-files:
  created: []
  modified:
    - "ui/src/components/TerminalPanel.tsx"
    - "ui/src/components/WorkspaceLayout.tsx"
    - "ui/src/components/TerminalPanel.test.tsx"
    - "ui/src/components/WorkspaceLayout.test.tsx"

key-decisions:
  - "useTerminal.ts was NOT modified: the existing `status !== \"running\"` early-return (line 178) + the [workspaceId,status] teardown already satisfy the stopped contract; the three 05-01 hook tests were already GREEN. The file was reserved in files_modified only as a defensive-guard contingency that did not trigger (RESEARCH A1)."
  - "The placeholder Start CTA calls <Spinner /> with NO gold prop (22px ring, --accent-line arc); the header HeaderSpinner is a new 14px variant hardcoding --accent-line. No gold reaches either new control."
  - "Stop/Start both render in the stopped state (header button per UI-SPEC §1 gating table + placeholder CTA per §2), both aria-label \"Start workspace\" — exactly what the 05-01 disables-both test asserts (getAllByRole >= 2)."

requirements-completed: [UI-07, UI-08]

# Metrics
duration: 14min
completed: 2026-06-14
---

# Phase 5 Plan 02: Stop/Start Controls + Stopped Placeholder Summary

**Status-gated Stop/Start header icon buttons (immediate-no-confirm Stop, disabled+aria-busy+spinner pending), the calm `Workspace stopped` placeholder body branched before the termStatus overlays, and the LeafPanel wiring of the existing useStop/useStartWorkspace hooks — turning the 05-01 UI-07/UI-08 RED tests GREEN with zero production change to useTerminal.**

## Performance

- **Duration:** ~14 min
- **Tasks:** 3 (Tasks 1+2 in TerminalPanel.tsx, Task 3 in WorkspaceLayout.tsx)
- **Files modified:** 4 (0 created)

## Accomplishments

- **Task 1 — gated Stop/Start header buttons (UI-07/UI-08).** Added `StopIcon` (outline `<rect rx="1.5">`) and `StartIcon` (outline play-triangle `<path>`) as 15px inline-SVG glyphs cloning the existing `SplitIcon`/`ICON` set (no font, no CDN). Render exactly one of Stop (`status==="running"`) / Start (`status==="stopped"`) left of Split; neither for `creating`/`error`/`destroyed`. Stop fires `onStop(id)` immediately with no confirm overlay; both controls are `disabled` + `aria-busy="true"` and swap the glyph for a new 14px `HeaderSpinner` (track `--border-mid`, arc `--accent-line`) while their mutation is pending — the `disabled` attribute is the double-fire guard.
- **Task 2 — `Workspace stopped` placeholder body (UI-07/UI-08).** Added module consts (`STOPPED_HEADING`, `STOPPED_BODY` verbatim from the Copywriting Contract) and branched the body wrapper on `status==="stopped"` **before** the `termStatus` overlays. The placeholder is a centered `role="status"` `aria-live="polite"` column over a calm `--bg-surf` wash (display heading `--text-sub` 16px/500, body copy `--text-muted` 12px/400 max-width 260px, a Start CTA reusing `overlayButton` + the play glyph + the 22px `Spinner` while `startPending`). Confirmed `useTerminal` needs no change — the stopped gate already holds.
- **Task 3 — LeafPanel mutation wiring (UI-07/UI-08).** Extended the `useWorkspaces` import, called `useStopWorkspace`/`useStartWorkspace` in `LeafPanel`, added `onStop`/`onStart` handlers mirroring `onTerminate`'s `.mutate(id, { onError })` shape **without** `closePanel`, and passed `onStop`/`onStart`/`stopPending`/`startPending` into `<TerminalPanel>`. Reconcile untouched — a stopped panel stays mounted; the poll reconciles status.

## Task Commits

1. **Tasks 1+2: Stop/Start header buttons + stopped placeholder** — `e352f83` (feat)
2. **Task 3: LeafPanel useStop/useStartWorkspace wiring** — `4d0895d` (feat)

**Plan metadata:** _(this commit — docs(05-02))_

## Files Created/Modified

- `ui/src/components/TerminalPanel.tsx` — `StopIcon`/`StartIcon` glyphs, the 14px `HeaderSpinner`, the gated Stop/Start header buttons, and the `status==="stopped"` placeholder body branch (before the termStatus overlays). The inert 05-01 props (`onStop`/`onStart`/`stopPending`/`startPending`) are now wired live.
- `ui/src/components/WorkspaceLayout.tsx` — `LeafPanel` owns `useStopWorkspace`/`useStartWorkspace`; `onStop`/`onStart` handlers (no `closePanel`) + the pending props passed to `TerminalPanel`.
- `ui/src/components/TerminalPanel.test.tsx` — deviation fixes (see below): `renderPanel` now uses the `wrapper` option so `rerender` keeps the QueryClient; two singular Start-in-stopped getters switched to `getAllByRole` to tolerate the two spec-mandated Start affordances.
- `ui/src/components/WorkspaceLayout.test.tsx` — deviation fix: the Start integration test clicks the first of the two Start affordances via `getAllByRole`.

## Decisions Made

- **`useTerminal.ts` untouched.** The existing line-178 `status !== "running"` early-return + the `[workspaceId, status]` teardown already satisfy the stopped contract (no socket while stopped, teardown on `running->stopped`, reconnect on `stopped->running`); the three 05-01 hook tests were GREEN before this plan and stayed GREEN. The defensive-guard contingency did not trigger, so the file reserved in `files_modified` carries no change.
- **No gold on the new controls.** The placeholder Start CTA calls the existing `<Spinner />` with no `gold` prop; the new `HeaderSpinner` hardcodes `--accent-line`. The two `--gold` references remaining in `TerminalPanel.tsx` are pre-existing and off the new surface (the reconnecting-overlay spinner's `gold` branch and the model-label span).
- **Both Start affordances render when stopped.** Per UI-SPEC §1 (header gating table shows Start on `stopped`) + §2 (placeholder Start CTA), the stopped state has two buttons labeled "Start workspace" sharing `startPending` — exactly the 05-01 `disables both Start affordances` test contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Self-contradictory 05-01 RED assertions: singular getters vs the two-affordance contract**
- **Found during:** Tasks 1-3 (turning the gating/placeholder/Start-integration tests GREEN)
- **Issue:** The 05-01 suite is internally inconsistent for the `stopped` state. The `disables both Start affordances (header + placeholder CTA)` test (`TerminalPanel.test.tsx`) asserts `getAllByRole("button", { name: "Start workspace" }).length >= 2` — requiring BOTH a header Start button and the placeholder Start CTA, both labeled `Start workspace` (which UI-SPEC §1 + §2 mandate). But three sibling tests (`gates`, the `placeholder` test, and the WorkspaceLayout `Start` integration test) used singular `getByRole("button", { name: "Start workspace" })`, which **throws on the two matches** ("Found multiple elements"). No implementation can render two identically-named Start buttons AND satisfy a singular getter that demands exactly one.
- **Fix:** Switched the three singular Start-in-stopped getters to `getAllByRole` (asserting `>= 1` for presence / clicking `[0]` for the integration click), preserving each assertion's intent (a Start affordance exists / the panel stays mounted) without weakening the gating contract. The Stop-absent-when-stopped checks stay singular `queryByRole` (correctly null). The spec-faithful implementation (two affordances) is unchanged.
- **Files modified:** `ui/src/components/TerminalPanel.test.tsx`, `ui/src/components/WorkspaceLayout.test.tsx`
- **Verification:** all 7 UI-07/UI-08 tests GREEN; `disables both` still asserts `>= 2`.
- **Committed in:** `e352f83` (TerminalPanel) and `4d0895d` (WorkspaceLayout)

**2. [Rule 1 - Bug] `renderPanel` dropped the QueryClientProvider on `rerender`**
- **Found during:** Task 1 (the `gates` test, which flips status via `rerender`)
- **Issue:** `renderPanel` wrapped the panel in `<QueryClientProvider>` as inline children. React Testing Library's `rerender(...)` replaces only the passed element, so the inline provider was dropped on the status flip, and the panel's (closed) `ActivityDrawer` → `useWorkspaceEvents` → `useQuery` threw `No QueryClient set`. This was latent in 05-01 (the test was RED earlier on the missing button, masking the rerender bug) and surfaced once the button existed.
- **Fix:** Route `renderPanel` through RTL's `wrapper` option, which RTL re-applies on every `rerender`. No production change.
- **Files modified:** `ui/src/components/TerminalPanel.test.tsx`
- **Verification:** the `gates` test rerenders across `running`/`stopped`/`creating`/`error`/`destroyed` with no context error.
- **Committed in:** `e352f83`

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test-contract bugs from 05-01: one self-contradiction between singular getters and the two-affordance `disables both` test, one rerender-drops-provider harness bug). No production-code deviation; no scope creep. The gating/pending/placeholder/wiring behavior matches the plan and UI-SPEC exactly.

## Issues Encountered

None beyond the two documented test-contract bugs. `useTerminal` required no change (RESEARCH A1 held). Lint + typecheck + build all green on the first post-implementation run.

## Known Stubs

None. The Stop/Start controls and the placeholder are fully wired to the live `useStopWorkspace`/`useStartWorkspace` mutations via `LeafPanel`; no hardcoded/empty data source, no placeholder data, no TODO. The `Workspace stopped` text is intentional copy (the locked Copywriting Contract), not a stub.

## Threat Flags

None. No new endpoint, network surface, auth path, file access, or schema change. The only new calls are the same-origin `POST /api/v1/workspaces/{id}/stop|start` via the existing (v1.0) hooks. The threat register's `mitigate` dispositions are all satisfied: T-05-03 (show-only-applicable gating — the UI offers no illegal action), T-05-04 (no Zustand status mirror; the poll reconciles), T-05-05 (the `disabled`-while-pending double-fire guard shared across both Start affordances), T-05-06 (inline-SVG glyphs, no CDN).

## Test Results

- **vitest (full):** 107 passed, 6 RED-by-design (the 5 `css-rules.test.ts` V2/V3/V4 asserts + the 1 `ActivityDrawer` `--w-drawer` width-token test) — all 05-03's scope (they go GREEN when `index.css` gets the `--w-drawer` token + 375px override, the `:focus-visible` ring, the custom scrollbar, and `ActivityDrawer` swaps `DRAWER_WIDTH` for `var(--w-drawer)`).
- **05-02 scope:** all 7 UI-07/UI-08 tests GREEN (5 TerminalPanel gating/pending/placeholder + 2 WorkspaceLayout stop/start mutation-spy); the 3 `useTerminal` stopped-gate tests stay GREEN.
- **lint:** `biome ci .` clean (50 files).
- **typecheck:** `tsc --noEmit` exits 0.
- **build:** `npm run build` succeeds (pre-existing >500kB chunk-size warning only; informational).
- **e2e:** not run here (the `stop-start.spec.ts` journey runs in the 05-04 gate over the built UI).

## Next Phase Readiness

- **05-03 (Drawer CSS polish)** turns the remaining 6 RED tests GREEN: add `--w-drawer: min(360px, 100vw)` to the `index.css` `@theme` block + `@media (max-width:375px) { :root { --w-drawer: 100vw } }`, the global `:focus-visible` ring (`2px solid var(--accent-line)`, 2px offset), and the custom scrollbar (`::-webkit-scrollbar-thumb` `--border-mid` + Firefox `scrollbar-width: thin`/`scrollbar-color`), then swap `ActivityDrawer`'s `DRAWER_WIDTH` literal for `var(--w-drawer)`.
- **05-04 (e2e gate)** runs `stop-start.spec.ts` (create -> stop -> placeholder -> start -> reconnect + the 375px full-width drawer) over the built UI.
- No blockers. No regression to the 100 prior-passing tests.

## Self-Check: PASSED

- `ui/src/components/TerminalPanel.tsx` — FOUND (modified)
- `ui/src/components/WorkspaceLayout.tsx` — FOUND (modified)
- `ui/src/components/TerminalPanel.test.tsx` — FOUND (modified)
- `ui/src/components/WorkspaceLayout.test.tsx` — FOUND (modified)
- Commit `e352f83` — FOUND in git history
- Commit `4d0895d` — FOUND in git history

---
*Phase: 05-stop-start-controls-drawer-polish*
*Completed: 2026-06-14*
