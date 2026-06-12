<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 05
subsystem: ui
tags: [react, tanstack-query, zustand, vitest, msw, react-mosaic, ui-spec]

# Dependency graph
requires:
  - phase: 02-04
    provides: layoutStore (openPanel/setActive/activeWorkspaceId), WorkspaceLayout mosaic grid, App tiling shell
  - phase: 02-03
    provides: useWorkspaces poll + create/stop/start/destroy mutations, TerminalPanel, MSW harness, four-theme tokens
  - phase: 02-01
    provides: GET /api/v1/nodes per-node capacity backend (memoryUsedFraction/overThreshold)
provides:
  - WorkspaceList sidebar (UI-01) — live-polled rows, status→color dots, pulse, active-row sync, empty/error states
  - Navbar (top bar) — brand mark, per-node capacity chips (real memoryUsedFraction %), four theme swatches, + New workspace
  - NewWorkspaceModal (UI-03) — create form + validation + cosmetic 4-step boot-progress + open-panel-on-success + capacity-error
  - StatusBar (UI-04) — running/stopped/error counts, session uptime, peak node mem %
  - useNodes hook — TanStack Query poll of GET /api/v1/nodes
  - assembled themed App shell — Navbar + sidebar + Mosaic grid + status bar + modal, data-theme root, inner-scroll columns
affects: [02-06, phase-4-event-drawer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "lib/status.ts — single source of the binding status→color-token map shared by sidebar + status bar"
    - "lib/themes.ts — four-theme registry (data) shared by Navbar swatches + App data-theme root"
    - "Cosmetic boot-progress saga: time-driven checklist over a SYNCHRONOUS create (no fake per-step API claim)"
    - "Tests assert real layoutStore state (mosaicNode), not spy call-counts, for leak-proof cross-test isolation"

key-files:
  created:
    - ui/src/components/WorkspaceList.tsx
    - ui/src/components/Navbar.tsx
    - ui/src/components/NewWorkspaceModal.tsx
    - ui/src/components/StatusBar.tsx
    - ui/src/hooks/useNodes.ts
    - ui/src/lib/status.ts
    - ui/src/lib/themes.ts
    - ui/src/components/WorkspaceList.test.tsx
    - ui/src/components/NewWorkspaceModal.test.tsx
    - ui/src/components/StatusBar.test.tsx
    - ui/src/App.test.tsx
  modified:
    - ui/src/App.tsx

key-decisions:
  - "App kept at ui/src/App.tsx (not the plan's components/App.tsx) so main.tsx's ./App import keeps resolving — Rule 3, consistent with the 02-03 decision"
  - "Node capacity rendered as the REAL memoryUsedFraction percent (Navbar chip + StatusBar peak), never an invented GB-free"
  - "Boot-progress is COSMETIC (synchronous create, A3/Pitfall 5); async 202+poll migration noted as a deferred v1.x improvement"
  - "Status→color map + four-theme registry extracted to lib/ as single sources of truth (DRY across surfaces)"

patterns-established:
  - "Status discipline: dots/overlines/counts use --ok/--warn/--err/--text-muted via lib/status; gold is prestige-only (counts/uptime/capacity/overline/spinner)"
  - "Modal saga single-shot: synchronous submit latch + isMounted/completed guards prevent double-open and post-unmount leaks"
  - "Store-state test assertions (mosaicNode) over singleton-method spies for deterministic cross-test isolation"

requirements-completed: [UI-01, UI-03, UI-04]

# Metrics
duration: 51min
completed: 2026-06-10
---

# Phase 2 Plan 05: Surfaces + Full Themed App Shell Summary

**The operator-facing UI surfaces — live-polled WorkspaceList sidebar (UI-01), Navbar with real per-node capacity chips, NewWorkspaceModal create flow with cosmetic boot-progress (UI-03), and StatusBar counts/uptime/capacity (UI-04) — assembled into the complete four-theme App shell, all to the binding 02-UI-SPEC contract.**

## Performance

- **Duration:** ~51 min
- **Started:** 2026-06-10T20:00:00Z
- **Completed:** 2026-06-10T20:48:46Z
- **Tasks:** 3 (TDD: RED + GREEN per task)
- **Files modified:** 12 (11 created, 1 modified)

## Accomplishments
- **WorkspaceList sidebar (UI-01):** live `useWorkspaces` rows with status→color dots (criterion 7), `repo · branch` mono line, non-running overlines, pulsing `creating` dot, `destroyed` filtered out, active-row `--accent-bg` fill + 2px `--accent-line` left bar + `aria-current` two-way synced to `layoutStore.activeWorkspaceId` (criterion 8), and the loading/empty (`No workspaces yet`)/poll-error (`Couldn't reach the control plane. Retrying…`) states + static self-host footer.
- **Navbar:** brand mark (accent square + gold hex SVG) + gold `Workspaces` overline, one capacity chip per node from `useNodes` (running count grouped from the live list + the real `memoryUsedFraction` %, gold mono), four theme swatches (`aria-pressed`), and the green `+ New workspace` button.
- **NewWorkspaceModal (UI-03):** Name/Git repo/Branch(`main`)/Node(from `useNodes`) form, required-field validation with verbatim `{Field} is required.` copy gating a green `Create`; submit drives the cosmetic 4-step boot-progress checklist (`✓/⟳/○` + gold-top spinner + `→ 202 · polling status…` footnote) during the synchronous create, then `openPanel(id)` + close on the resolved `running` row; a capacity envelope error (CAP-01) shows a red `✕` step + the message verbatim + `Close`.
- **StatusBar (UI-04):** running/stopped/error counts derived from the live list (gold mono + status dots + text labels), a client session-uptime timer (`Xh Ym`, gold mono), peak node memory %, loading `—`/zero `0`/hold-on-error states, fixed 32px never-grow.
- **useNodes:** TanStack Query ~3s poll of `GET /api/v1/nodes`.
- **App shell:** `data-theme` root (default `dark`) + `Burrow workspace manager` landmark; Navbar (52px) / sidebar (228px) / Mosaic grid / StatusBar (32px) with inner-scroll-only columns; `+ New workspace` opens the modal; swatches switch all four themes (criterion 1, 15).

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: WorkspaceList + Navbar + useNodes (UI-01)** — `2f40dfb` (test, RED), `40372f8` (feat, GREEN)
2. **Task 2: NewWorkspaceModal (UI-03)** — `40b81d8` (test, RED), `9b99d7f` (feat, GREEN)
3. **Task 3: StatusBar + App shell (UI-04)** — `9b57aa4` (test, RED), `850c6cf` (feat, GREEN)

**Plan metadata:** committed separately (docs: complete plan).

## Files Created/Modified
- `ui/src/components/WorkspaceList.tsx` — sidebar (UI-01): rows, status dots/overlines, pulse, active-row sync, empty/error, footer
- `ui/src/components/Navbar.tsx` — top bar: brand, per-node capacity chips, theme swatches, + New workspace
- `ui/src/components/NewWorkspaceModal.tsx` — create form + validation + cosmetic boot-progress saga + capacity error
- `ui/src/components/StatusBar.tsx` — counts + uptime + peak-mem, 32px never-grow
- `ui/src/hooks/useNodes.ts` — GET /api/v1/nodes poll
- `ui/src/lib/status.ts` — single-source status→color-token map + visible-status filter
- `ui/src/lib/themes.ts` — four-theme registry (name/label/swatch)
- `ui/src/App.tsx` — assembled themed shell (Navbar + sidebar + grid + status bar + modal)
- `ui/src/components/{WorkspaceList,NewWorkspaceModal,StatusBar}.test.tsx`, `ui/src/App.test.tsx` — MSW-backed Tier-2 tests

## Decisions Made
- **App location:** kept at `ui/src/App.tsx` rather than the plan's `ui/src/components/App.tsx` so `main.tsx`'s `./App` import keeps resolving (Rule 3 blocking; consistent with the 02-03 decision).
- **Capacity readout:** the real `memoryUsedFraction` as a percent in both the Navbar chip and the StatusBar peak-mem, never a fabricated "GB free" (per the 02-01 backend contract).
- **Cosmetic boot-progress:** the 4-step saga is a time-driven cosmetic animation over the SYNCHRONOUS create (A3/Pitfall 5) — no real per-step status is claimed; the async-202 + status-poll migration is a deferred v1.x improvement.
- **Shared single-sources:** `lib/status.ts` (status→color) and `lib/themes.ts` (four themes) keep the binding contracts DRY across the sidebar/status-bar and the Navbar/App respectively.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] App kept at `ui/src/App.tsx`**
- **Found during:** Task 3 (App shell assembly)
- **Issue:** The plan's `files_modified` lists `ui/src/components/App.tsx`, but the live App is at `ui/src/App.tsx` (the 02-03 Rule-3 decision so `main.tsx`'s `./App` import resolves). Creating a second App in `components/` would orphan the real entry point.
- **Fix:** Assembled the full shell in the existing `ui/src/App.tsx`; authored `ui/src/App.test.tsx` alongside it.
- **Files modified:** ui/src/App.tsx, ui/src/App.test.tsx
- **Verification:** `npm run build` + full vitest green; App shell test proves the four surfaces + modal + theme switch.
- **Committed in:** 850c6cf (Task 3 commit)

**2. [Rule 2 - Missing Critical] Single-shot guards on the modal saga**
- **Found during:** Task 2 (NewWorkspaceModal)
- **Issue:** A double-submit (two clicks in one tick) or a create resolving after the modal unmounts would call `openPanel` twice / after teardown.
- **Fix:** Added a synchronous submit latch (`submittingRef`) plus `isMounted`/`completed` guards so create opens the panel exactly once and never after unmount.
- **Files modified:** ui/src/components/NewWorkspaceModal.tsx
- **Verification:** Dedicated `does not double-open` test + store-state assertions pass.
- **Committed in:** 9b99d7f (Task 2 commit)

**3. [Rule 3 - Blocking] Extracted `lib/status.ts` + `lib/themes.ts`**
- **Found during:** Tasks 1 + 3
- **Issue:** The status→color map is needed by both the sidebar and the status bar; the four-theme list (incl. swatch hex) is needed by both the Navbar and the App. Duplicating either would risk drift and put theme-identity hex into components (criterion 1 violation).
- **Fix:** Single-source `lib/status.ts` (token map) and `lib/themes.ts` (theme registry; swatch hex is theme-identity DATA in a lib module, not component styling — components stay hex-free).
- **Files modified:** ui/src/lib/status.ts, ui/src/lib/themes.ts
- **Verification:** Component hex grep returns none; biome ci + tsc green.
- **Committed in:** 40372f8 (Task 1), 850c6cf (Task 3)

---

**Total deviations:** 3 auto-fixed (1 missing-critical, 2 blocking)
**Impact on plan:** All necessary for correctness and the UI-SPEC token/criterion contract. No scope creep.

## Issues Encountered
- **Cross-test `openPanel` spy leakage (Task 2):** spying the singleton `layoutStore.openPanel` made a stray async call from one test attributable to the next (shared spy identity). **Resolved** by asserting real, per-test-reset store state (`mosaicNode === "ws-created"` / `null`) instead of spy call-counts — leak-proof and tests actual behavior. The cosmetic completion pause was also made part of the awaited chain (no detached post-unmount timer).
- **Fake timers vs MSW (Task 3):** `vi.useFakeTimers()` froze the query/microtask resolution and timed out the data waits. **Resolved** by using real timers (the uptime test only needs the initial `0h 0m` render).

## Deferred Items
- **Async-202 create migration:** moving create to an async `202` + real status poll so the boot-progress reflects true per-step worker progress (currently cosmetic). v1.x improvement, out of scope (A3/Pitfall 5).
- **Responsive drawer:** the full off-canvas sidebar drawer (640–1023px) + single-panel phone mode (<640px) from the 02-UI-SPEC Responsive Behavior are structurally supported (inner-scroll columns, fixed chrome) but the media-query drawer toggle is not yet wired — desktop full shell is complete. Carry to 02-06 / a follow-up.
- **Self-hosted fonts:** still the `_ds` system-stack fallback (no woff2 vendorable) per the 02-02 decision; activation is the documented `ui/public/fonts/README.md` drop-in.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UI-01, UI-03, UI-04 complete; the full themed operator shell is assembled and builds green.
- Ready for 02-06 (Playwright phase e2e: create→terminal→split→detach→reconnect→terminate + UI-05 restore) and the gsd-ui-auditor visual grade against the 15 UI-SPEC criteria.
- Carried: async-202 create migration (deferred), responsive drawer (partial), self-hosted fonts (fallback active).

## Self-Check: PASSED

All 8 created source files + the SUMMARY exist on disk; all 6 task commits (3 RED + 3 GREEN) are present in git history. Full gate green: 77 vitest + tsc + biome ci (39 files) + `npm run build` + REUSE 212/212 + no CDN refs + no hex in components.

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
