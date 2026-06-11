<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
plan: 03
subsystem: ui
tags: [react, tanstack-query, activity-drawer, events, a11y, playwright, vitest]

# Dependency graph
requires:
  - phase: 02-terminal-proxy-react-ui
    provides: the React shell, the design tokens, useWorkspaces/status.ts/WorkspaceList/TerminalPanel/NewWorkspaceModal analogs, the Playwright Fake+stub-ttyd e2e harness
  - phase: 01-foundation
    provides: GET /api/v1/workspaces/{id}/events (the drawer's data source) + the camelCase event JSON
provides:
  - WorkspaceEvent TS type mirroring the camelCase event JSON
  - useWorkspaceEvents — an enabled-gated TanStack poll (runs only while the drawer is open)
  - EVENT_BADGE map + badgeFor — namespaced-type → token/label, reaper.* prefix, unknown→raw-mono fallback, reason:idle special case
  - ActivityDrawer — right-anchored 360px slide-in, 4 data states, boot.error emphasis, full a11y (dialog/Esc/focus-trap/focus-return)
  - the TerminalPanel Activity-log trigger (ephemeral activeEventsWorkspaceId, one drawer at a time)
  - a vitest component suite + a Playwright e2e drawer journey over the Fake
affects: [04-01 reconciler (emits reaper.* + workspace.stopped reason:idle the badge map renders), future UI work consuming the events surface]

# Tech tracking
tech-stack:
  added: []  # no new runtime dependency — hand-built on the Phase-2 tokens (FROZEN guardrail 7)
  patterns:
    - "enabled-gated TanStack poll: a hook takes (id, enabled) and gates refetchInterval on `enabled && !!id` so polling stops when the surface is closed"
    - "EVENT_BADGE single-source map mirroring status.ts (tokens only, no hex), with a badgeFor() resolver for prefix/special-case/unknown-fallback logic"
    - "drawer a11y: role=dialog + focus trap + Esc + focus-return-to-trigger via a useEffect that stashes document.activeElement on open and restores it on close"

key-files:
  created:
    - ui/src/types/event.ts
    - ui/src/hooks/useWorkspaceEvents.ts
    - ui/src/lib/events.ts
    - ui/src/components/ActivityDrawer.tsx
    - ui/src/components/ActivityDrawer.test.tsx
    - ui/tests/e2e/activity-drawer.spec.ts
  modified:
    - ui/src/components/TerminalPanel.tsx
    - ui/src/components/TerminalPanel.test.tsx

key-decisions:
  - "badgeFor() owns all non-static badge logic (reaper.* prefix, workspace.stopped reason:idle, unknown→raw-mono); EVENT_BADGE stays a flat literal map for the verified namespaced types"
  - "the drawer renders the server-redacted `data` verbatim as compact `key: value · …` mono text and makes ONLY the same-origin events poll — no second/un-redact request (threat T-04-03A/B)"
  - "focus-return-to-trigger is implemented as a cleanup in the open-effect (stash document.activeElement on open, restore on close) — the contract NewWorkspaceModal omits"

patterns-established:
  - "Pattern: enabled-gated poll hook (id, enabled) → useQuery refetchInterval gated on enabled && !!id"
  - "Pattern: a tokens-only badge map + a resolver function for forward-compatible fallback rendering"

requirements-completed: [UI-06]

# Metrics
duration: 12min
completed: 2026-06-11
---

# Phase 4 Plan 03: Activity Drawer (UI-06) Summary

**A per-workspace right-side activity drawer that enabled-gate-polls the events endpoint, renders the log newest-first with a namespaced-type badge map (reaper.* + unknown handled) and a boot.error-emphasized row, hand-built on the Phase-2 tokens with full a11y (dialog/Esc/focus-trap/focus-return).**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-11T23:14:24Z
- **Completed:** 2026-06-11T23:26:58Z
- **Tasks:** 3
- **Files modified:** 8 (6 created, 2 modified)

## Accomplishments
- `WorkspaceEvent` type + `useWorkspaceEvents` enabled-gated poll + `EVENT_BADGE`/`badgeFor` map — the three contract files, tokens-only, mirroring `workspace.ts`/`useWorkspaces`/`status.ts`
- `ActivityDrawer` to the binding 04-UI-SPEC: right-anchored 360px slide-in, four data states (loading shimmer / empty / poll-error strip over kept rows / populated newest-first), the `boot.error` emphasis (2px `--err` left bar + tint + redacted reason in red mono), and the a11y contract (role=dialog, focus trap, Esc, focus-return, aria-live=polite)
- The `TerminalPanel` Activity-log trigger left of Split (terminate stays rightmost), driving a single ephemeral `activeEventsWorkspaceId`
- An 11-test vitest suite (states, reverse, badges, emphasis, unknown fallback, idle label, poll-gating, dialog, Esc, focus-return) + a Playwright e2e drawer journey that **passed green end-to-end** over the Fake + stub ttyd (1.8s test, 17.6s incl. harness)

## Task Commits

Each task was committed atomically:

1. **Task 1: Event contracts (type + hook + badge map)** - `1326546` (feat)
2. **Task 2: ActivityDrawer component + vitest coverage** - `97a82b6` (feat)
3. **Task 3: Panel trigger + Playwright e2e (+ test-harness fix)** - `cacc99c` (feat)

**Plan metadata:** _(this docs commit)_

## Files Created/Modified
- `ui/src/types/event.ts` - `WorkspaceEvent` camelCase type mirroring `api/models/event.py`
- `ui/src/hooks/useWorkspaceEvents.ts` - the ~3s events poll, gated `enabled: enabled && !!id`
- `ui/src/lib/events.ts` - `EVENT_BADGE` (verified namespaced types) + `badgeFor` (reaper.* prefix, reason:idle, unknown→raw-mono)
- `ui/src/components/ActivityDrawer.tsx` - the right-anchored drawer (4 states, boot.error emphasis, a11y), reads `data` verbatim, only the events poll
- `ui/src/components/ActivityDrawer.test.tsx` - the MSW + QueryClient vitest suite (11 tests)
- `ui/tests/e2e/activity-drawer.spec.ts` - the Playwright create→open→see-rows→close(×/Esc) journey
- `ui/src/components/TerminalPanel.tsx` - the Activity-log trigger + the ephemeral `activeEventsWorkspaceId` + the rendered `ActivityDrawer`
- `ui/src/components/TerminalPanel.test.tsx` - wrapped renders in `QueryClientProvider` (deviation, below)

## Decisions Made
- `badgeFor()` is the single resolver for all non-static badge logic; `EVENT_BADGE` is a flat literal map for the verified types only — keeps the binding table 1:1 with the source while the prefix/special-case/fallback logic lives in one tested function.
- The drawer's `data` summary renders the already-`_safe()`-redacted object verbatim (`key: value · …` mono); the drawer issues only the same-origin events poll and never re-fetches or un-redacts (threat register T-04-03A/B mitigations).
- Focus-return-to-trigger is the open-effect's cleanup (stash `document.activeElement` on open, restore on close) — added per the UI-SPEC a11y contract, which `NewWorkspaceModal` does not implement.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wrapped TerminalPanel.test.tsx renders in a QueryClientProvider**
- **Found during:** Task 3 (wiring the trigger into `TerminalPanel`)
- **Issue:** `TerminalPanel` now renders the (closed) `ActivityDrawer`, whose `useWorkspaceEvents` calls `useQuery`. `useQuery` requires a `QueryClient` in context even when `enabled: false`, so the 9 existing `TerminalPanel.test.tsx` tests began failing with "No QueryClient set".
- **Fix:** Added a local `renderPanel(ui)` helper that wraps the render in a `QueryClientProvider` (retry:false) and replaced the 9 bare `render(<TerminalPanel … />)` call sites with it.
- **Files modified:** `ui/src/components/TerminalPanel.test.tsx`
- **Verification:** full vitest 92/92 green; tsc + biome ci (47 files) clean.
- **Committed in:** `cacc99c` (Task 3 commit)

### Minor in-task adjustment (not a scope deviation)
- The boot.error-emphasis vitest assertion was switched from `toHaveStyle({ borderLeft: … })` to a raw `row.style.borderLeft` equality check: jsdom keeps the `borderLeft` shorthand inline-style value un-expanded, so `toHaveStyle` against the shorthand reported "Expected/Received" empty. The component is unchanged; only the assertion form changed. Committed in `97a82b6`.

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The fix is mechanical and necessary (a provider-context requirement introduced by the planned wiring). No scope creep — no production behavior changed, only the test harness.

## Issues Encountered
- None beyond the deviation above. tsc, biome, the full vitest suite, the SPA build, and the Playwright e2e all ran green locally.

## Known Stubs
None. The drawer is wired to the real `useWorkspaceEvents` poll of the live endpoint; no placeholder/empty-data path ships. The empty state ("No activity yet") is an intentional, spec'd data state, not a stub.

## Threat Flags
None. The drawer introduces no new network surface — it reuses the shipped `GET /api/v1/workspaces/{id}/events` read, renders the server-redacted `data` verbatim (no un-redact, no second request), uses inline outline SVG only (no CDN), and adds no runtime dependency. This matches the plan's `<threat_model>` dispositions (T-04-03A/B/C mitigated, T-04-SC accept).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UI-06 is complete and CI-provable (vitest + Playwright + tsc + biome + build all green); the drawer is ready for the Phase-4 reconciler (04-01) to emit `reaper.*` and `workspace.stopped` `reason:idle` events, which the badge map already renders.
- One e2e caveat consistent with the phase posture: the Playwright drawer journey ran green locally over the Fake + standalone stub ttyd; the real-ttyd / live-claude path stays the deferred dev-homelab smoke. CI is the standing authority for the e2e tier.

## Self-Check: PASSED

All 6 created files + the SUMMARY exist on disk; all 3 task commits (`1326546`, `97a82b6`, `cacc99c`) are present in the git history.

---
*Phase: 04-hardening-release*
*Completed: 2026-06-11*
