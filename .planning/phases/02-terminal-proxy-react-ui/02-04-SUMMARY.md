<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 04
subsystem: ui
tags: [react-mosaic, zustand, persist, tiling, layout, reconcile, restore-after-refresh, react, tdd, mvp]

# Dependency graph
requires:
  - phase: 02-terminal-proxy-react-ui (plan 03)
    provides: "TerminalPanel (the leaf this layout renders per tile, owning useTerminal) + useWorkspaces (the live TanStack Query list the layout reconciles against) + the reusable mock WebSocket/xterm/ResizeObserver test doubles"
  - phase: 02-terminal-proxy-react-ui (plan 02)
    provides: "the four-theme @theme token sheet (--accent-line/--bg/--border etc.) the mosaic chrome + active-panel ring read, and the MSW /api/v1 harness the layout test renders over"
provides:
  - "layoutStore (Zustand 5 + persist) — owns the react-mosaic MosaicNode<string> tree + activeWorkspaceId, with openPanel/closePanel/splitPanel/setActive/setNode + reconcile(liveIds); persists ONLY the two view-state keys to localStorage (UI-02/UI-05 state, no server-status mirroring)"
  - "WorkspaceLayout — <Mosaic 6.2.0> bound to layoutStore rendering a TerminalPanel per leaf, Burrow-styled hairline splitters (no Blueprint blue), 'No open terminals' empty state, active-panel 1px --accent-line ring synced to activeWorkspaceId, and restore-after-refresh reconcile on first useWorkspaces success"
  - "the App shell now renders the react-mosaic tiling layout (open/split/drag/resize) replacing the Wave-2 single panel"
  - ".burrow-mosaic chrome override block in index.css (flat hairline gutters, --accent-line low-emphasis on hover, --accent-bg drop-targets)"
  - "react/react-dom@19.2.7 overrides + vite/vitest dedupe collapsing react-mosaic's nested react-dom@18 onto a single React runtime"
affects: [02-05, 02-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "layoutStore is the ONLY persisted client state (zustand persist, key burrow-layout) and is partialized to mosaicNode + activeWorkspaceId only — workspace status stays in TanStack Query (Pitfall 11, no drift)"
    - "Tree mutations are pure helpers over react-mosaic's getLeaves + createBalancedTreeFromLeaves (add/prune/rebalance) imported from the deep util path (react-mosaic-component/lib/util/mosaicUtilities) to keep the store free of the React component graph / nested react-dom"
    - "reconcile(liveIds) is the single UI-05 primitive: drop leaves not in the live set, rebalance, retarget activeWorkspaceId to a survivor or null; WorkspaceLayout calls it in a useEffect on every useWorkspaces success so a later destroy also drops its panel"
    - "<Mosaic> 6.2.0 bundles its own react-dnd DndProvider (MultiBackend) — used directly, never double-wrapped (Pitfall 6); its Blueprint chrome is suppressed by passing className='burrow-mosaic' (not mosaic-blueprint-theme) and importing only the base layout CSS"
    - "active-panel sync is focus-driven (onFocusCapture/onPointerDownCapture → setActive) on a non-interactive wrapper, so the real controls inside (xterm body, header buttons) own keyboard focus + a11y"
    - "single React runtime enforced via package.json overrides (react/react-dom 19.2.7) so react-mosaic's react-dnd-multi-backend (peer excludes 19) can't nest an older react-dom that crashes against React 19"

key-files:
  created:
    - ui/src/store/layoutStore.ts
    - ui/src/store/layoutStore.test.ts
    - ui/src/components/WorkspaceLayout.tsx
    - ui/src/components/WorkspaceLayout.test.tsx
  modified:
    - ui/src/App.tsx
    - ui/src/index.css
    - ui/package.json
    - ui/package-lock.json
    - ui/vite.config.ts
    - ui/vitest.config.ts
    - ui/tests/setup.ts

key-decisions:
  - "layoutStore imports the mosaic tree utilities from the deep util path (react-mosaic-component/lib/util/mosaicUtilities), not the package barrel — the barrel re-exports the <Mosaic> React components and transitively pulls react-mosaic's bundled react-dom, which crashes in a pure (non-React) store/test context."
  - "Pinned react/react-dom to 19.2.7 via package.json overrides to collapse react-mosaic's nested react-dom@18 (pulled by react-dnd-multi-backend, whose peer excludes React 19) — without it <Mosaic> crashes on `ReactCurrentDispatcher` (two React runtimes). vite.config + vitest.config also dedupe for defense in depth."
  - "Active-panel sync is focus-driven (onFocusCapture + onPointerDownCapture) rather than an onClick handler on the wrapper div — keeps the wrapper non-interactive (a11y: the real terminal/buttons own keyboard focus) and still two-way-syncs activeWorkspaceId for the Wave-4 sidebar."
  - "splitPanel re-balances the existing leaves along the requested direction (a lone panel stays a single leaf — nothing to split against); it is the header split affordance's hook and is a no-op for an unopened id."
  - "tests/setup.ts installs an in-memory Storage polyfill when the active localStorage lacks getItem — Node 25 auto-exposes a non-functional built-in localStorage that shadows jsdom's, breaking zustand persist round-trips."

patterns-established:
  - "Pure, React-free tree helpers (addLeaf/treeFromLeaves/retargetActive) over react-mosaic's getLeaves + createBalancedTreeFromLeaves — unit-testable with no renderer"
  - "Restore-after-refresh = persist the tree + reconcile against the authoritative live list on load (drop gone leaves, retarget active), the UI-05 contract the Wave-4 sidebar and the e2e (02-06) build on"
  - "react-mosaic Blueprint-chrome suppression via a Burrow className + .burrow-mosaic token overrides (no Blueprint CSS import) — the visual-fidelity baseline for the UI auditor"

requirements-completed: [UI-02, UI-05]

# Metrics
duration: 23min
completed: 2026-06-10
---

# Phase 2 Plan 04: Tiling — layoutStore + WorkspaceLayout + restore-after-refresh Summary

**Multi-panel terminal tiling: a Zustand `layoutStore` owning the react-mosaic tree + active workspace (persisted to localStorage, partialized to just the two view keys, reconciled against the live list on load), and a `WorkspaceLayout` binding `react-mosaic-component@6.2.0` to it — open/split/drag/resize Burrow-styled panels that survive a refresh and reconnect their live terminals while dropping gone ones (UI-02 + UI-05).**

## Performance

- **Duration:** ~23 min
- **Started:** 2026-06-10T19:30:56Z
- **Completed:** 2026-06-10T19:54:00Z
- **Tasks:** 2 (both TDD)
- **Files:** 4 created, 7 modified

## Accomplishments

- **`layoutStore` (UI-02/UI-05 state)** — a Zustand 5 store with `persist` (localStorage key `burrow-layout`) holding the `MosaicNode<string>` tree + `activeWorkspaceId`. `openPanel` (empty→leaf, else balanced split, marks active), `closePanel` (prune + rebalance, last→null + retarget active), `splitPanel(id, "row"|"column")` (re-orient existing leaves; lone panel stays single; no-op for an unopened id), `setActive`, `setNode` (the `<Mosaic onChange>` path), and `reconcile(liveIds)` (drop leaves not in the live set, rebalance, retarget the active id to a survivor or null). `partialize` persists ONLY `mosaicNode` + `activeWorkspaceId` — workspace status never enters the store (Pitfall 11, no poll-vs-store drift). Pure React-free tree helpers over react-mosaic's `getLeaves` + `createBalancedTreeFromLeaves`.
- **`WorkspaceLayout` (UI-02)** — a `<Mosaic<string>>` bound to the store (`value`/`onChange`/`renderTile`), each leaf mounting a `TerminalPanel` resolved against the live `useWorkspaces` list. Burrow-styled splitters/drop-targets (`.burrow-mosaic`, flat hairline gutters showing `--accent-line` low-emphasis on hover, `--accent-bg` drop-targets) with the Blueprint theme fully suppressed (own className, base layout CSS only, no Blueprint import). The `No open terminals` empty state when the tree is null. The active panel carries a 1px `--accent-line` ring synced to `activeWorkspaceId`, focus-driven (`onFocusCapture`/`onPointerDownCapture` → `setActive`) for the Wave-4 sidebar two-way sync. `<Mosaic>` 6.2.0's bundled `DndProvider` is used directly (never double-wrapped, Pitfall 6).
- **Restore-after-refresh (UI-05)** — on every `useWorkspaces` success, `WorkspaceLayout` calls `layoutStore.reconcile(new Set(liveIds))`: a persisted leaf whose workspace is gone/destroyed drops and the tree rebalances; still-running leaves keep their panel, which remounts and its terminal reconnects to the live session via `useTerminal` (no fresh process, no scrollback in v1 — the documented limitation). Re-running on each poll means a later destroy also drops its panel.
- **App shell** — swapped the Wave-2 single `TerminalPanel` for `<WorkspaceLayout>`; an operator can now open/split/drag/resize several terminals and keep that arrangement across a refresh.

## Task Commits

Each task was committed atomically (both TDD: test + impl authored together, committed as the GREEN feat):

1. **Task 1: layoutStore — tree mutations + persist + reconcile** - `56052cb` (feat) — 17 vitest cases (open/split/close/reconcile/persist)
2. **Task 2: WorkspaceLayout + restore-after-refresh + App wiring** - `d433202` (feat) — 4 vitest cases (empty state, panel-per-leaf, reconcile-on-load, clear-to-empty)

**Plan metadata:** committed with this SUMMARY + STATE/ROADMAP/REQUIREMENTS updates (docs).

## Files Created/Modified

- `ui/src/store/layoutStore.ts` — Zustand layoutStore: mosaic tree + active id, open/close/split/setActive/setNode + persist (partialized) + reconcile
- `ui/src/store/layoutStore.test.ts` — 17 tests: tree mutations, reconcile-vs-live, persist partialize
- `ui/src/components/WorkspaceLayout.tsx` — `<Mosaic>` bound to the store, TerminalPanel per leaf, reconcile-on-load, active ring, empty state
- `ui/src/components/WorkspaceLayout.test.tsx` — 4 MSW-backed tests: empty state, panel-per-leaf, reconcile drops a ghost leaf on load, clear-to-empty
- `ui/src/App.tsx` — renders `<WorkspaceLayout>` (tiling) instead of the single panel
- `ui/src/index.css` — `.burrow-mosaic` chrome overrides (hairline gutters, `--accent-line` hover, `--accent-bg` drop-targets; no Blueprint blue)
- `ui/package.json` + `ui/package-lock.json` — `overrides` pinning react/react-dom 19.2.7 (collapses the nested react-dom@18)
- `ui/vite.config.ts` + `ui/vitest.config.ts` — `resolve.dedupe` react/react-dom (single runtime, build + test parity)
- `ui/tests/setup.ts` — in-memory Storage polyfill (Node 25's built-in localStorage shadows jsdom's)

## Decisions Made

- **Deep-import the mosaic tree utilities** (`react-mosaic-component/lib/util/mosaicUtilities`) in the store, not the barrel — the barrel drags in the `<Mosaic>` React components + react-mosaic's nested react-dom, which crash in the pure store/test context.
- **Pin react/react-dom via overrides** to collapse react-mosaic's nested react-dom@18 (pulled by `react-dnd-multi-backend`, whose peer range excludes React 19) onto the single root React 19 — the durable fix that `npm ci` reproduces.
- **Focus-driven active sync** (not an onClick on a static wrapper) keeps the panel container a11y-clean while still two-way-syncing `activeWorkspaceId`.
- **`splitPanel` re-balances existing leaves** along the requested direction (lone panel = single leaf), matching the header split affordance and the plan's "id appears once, balanced" contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] react-mosaic's nested react-dom@18 crashes <Mosaic> against React 19**
- **Found during:** Task 2 (first WorkspaceLayout render)
- **Issue:** `react-dnd-multi-backend` (a react-mosaic dep) peer-requires `react-dom ^16||^17||^18`, so npm nested a `react-dom@18.3.1` under `react-mosaic-component`. Loading it alongside root React 19 threw `Cannot read properties of undefined (reading 'ReactCurrentDispatcher')` at import — two React runtimes.
- **Fix:** Added `overrides: { react, react-dom: 19.2.7 }` to `package.json` and reinstalled (the nested copy was removed; `npm ci` reproduces the deduped tree). Added `resolve.dedupe` to `vite.config.ts` + `vitest.config.ts` for defense in depth.
- **Files modified:** ui/package.json, ui/package-lock.json, ui/vite.config.ts, ui/vitest.config.ts
- **Verification:** `<Mosaic>` renders; all WorkspaceLayout tests pass; `npm ci` keeps the nested copy gone; production `vite build` succeeds.
- **Committed in:** d433202 (Task 2 commit)

**2. [Rule 3 - Blocking] Node 25's built-in localStorage shadows jsdom's (zustand persist can't round-trip)**
- **Found during:** Task 1 (first layoutStore persist test)
- **Issue:** Node 25 auto-exposes a non-functional global `localStorage` (no `getItem`/`setItem`/`clear`) that overrides jsdom's Web Storage, so `zustand` `persist` and the persistence test failed.
- **Fix:** `tests/setup.ts` installs a spec-compliant in-memory `Storage` on `globalThis`/`window` when the active one lacks `getItem`.
- **Files modified:** ui/tests/setup.ts
- **Verification:** persist partialize test passes; the full suite (53 tests) stays green.
- **Committed in:** 56052cb (Task 1 commit)

**3. [Rule 3 - Blocking] layoutStore barrel import pulls react-mosaic's React/react-dom graph into a pure store**
- **Found during:** Task 1 (first GREEN run)
- **Issue:** Importing `getLeaves`/`createBalancedTreeFromLeaves` from `react-mosaic-component` (barrel) re-exported the `<Mosaic>` components and crashed the pure store test with the same `ReactCurrentDispatcher` error.
- **Fix:** Import the utilities from the deep util path `react-mosaic-component/lib/util/mosaicUtilities` (lodash-only, no React) + types from `lib/types`.
- **Files modified:** ui/src/store/layoutStore.ts, ui/src/store/layoutStore.test.ts
- **Verification:** layoutStore tests run + pass; tsc clean.
- **Committed in:** 56052cb (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 3 blocking — React-runtime / test-env plumbing). No scope creep: each unblocked the plan's own verification. No architectural change, no library swap.

## Issues Encountered

- A test-authoring error (a Mosaic tree with a duplicate leaf id — Mosaic forbids duplicates) was caught by `<Mosaic>`'s own validation and fixed to use two distinct live workspaces; resolved within Task 2.

## User Setup Required

None — no external service configuration required (v1 is LAN-only no-auth). Visual fidelity of the WorkspaceLayout against 02-UI-SPEC is graded later by the UI auditor; this plan implements the contract (Burrow hairline splitters, no Blueprint blue, `No open terminals` empty state, active-panel `--accent-line` ring).

## Next Phase Readiness

- `layoutStore` is the shared layout surface the Wave-4 sidebar (02-05) reads/writes for two-way active sync (`activeWorkspaceId`) and to `openPanel` on row click; the New Workspace modal calls `openPanel(id)` on create success.
- `WorkspaceLayout` + the reconcile/restore primitive is what the phase e2e (02-06) exercises for the create→split→detach→reconnect→terminate + UI-05 restore flow.
- The `.burrow-mosaic` chrome + active ring are the visual baseline the UI auditor grades; the real drag/resize affordances are react-mosaic native (proven by render; full interaction is the Playwright tier in 02-06).
- UI-02 and UI-05 are complete; the remaining Phase-2 plans are the sidebar/modal/status-bar shell (02-05) and the e2e gate (02-06).

## Self-Check: PASSED

(see appended self-check below)

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
