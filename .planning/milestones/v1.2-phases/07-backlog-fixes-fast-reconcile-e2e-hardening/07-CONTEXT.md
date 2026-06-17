<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening) - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning
**Mode:** Spec from backlog todos (WR-01, WR-02) — fully specified, no open grey areas

<domain>
## Phase Boundary

Close the two v1.1 code-review findings, both CI-provable over the Fake provider:
- **UI-12 (WR-01):** wire the `LeafPanel onTerminalEvent` fast-reconcile so the workspace
  list invalidates immediately on a terminal error/close instead of waiting for the ~3s poll.
- **CICD-09 (WR-02):** harden `stop-start.spec.ts` — panel-scoped locators (no unscoped
  `.first()` / global count assertions) + per-test backend isolation.

Frontend/test only. No new visual surface (UI-12 is callback wiring, not a new component) →
no UI-SPEC. Out of boundary: any new lifecycle behavior, Phase 8/9 work.
</domain>

<decisions>
## Implementation Decisions

### UI-12 — fast-reconcile wiring (from WR-01 todo)
- `WorkspaceLayout.LeafPanel` calls `useInvalidateWorkspaces()` and passes the resulting
  callback as `onTerminalEvent={invalidate}` to `TerminalPanel` — mirroring how it already
  wires `useDestroyWorkspace` → `onTerminate`. `TerminalPanel` already forwards
  `onTerminalEvent` into `useTerminal`, which fires it on terminal error/close (Pitfall 4).
- Land a **failing-first** vitest test in `WorkspaceLayout.test.tsx` (or `TerminalPanel.test.tsx`):
  a simulated terminal error/close event triggers a `WORKSPACES_KEY` invalidation (assert via
  a queryClient `invalidateQueries` spy or a refetch), and the list does NOT mirror status into
  Zustand. No production change to `useTerminal`/`useWorkspaces` beyond the wiring.

### CICD-09 — e2e hardening (from WR-02 todo)
- **Scope every locator to the panel under test.** Replace unscoped `.first()` / global
  `getByText(name)` / `[data-testid^="term-"]` selectors with a per-panel locator. Prefer a
  `data-testid` that includes the workspace id on the panel `<section>` (add it in
  `TerminalPanel` if needed — `data-testid={`panel-${id}`}`) and `within(panel)` the Stop/Start/
  Activity controls + the term body + the "Workspace stopped" placeholder.
- **Replace the global `toHaveCount(0)`** (the `[data-testid^="term-"]` count after Stop) with a
  panel-scoped assertion: the panel-under-test's term body is gone and its placeholder is shown.
- **Per-test isolation:** add an `afterEach` that destroys the workspace(s) the test created
  (DELETE `/api/v1/workspaces/{id}` via the UI terminate or a direct request), so the Fake
  backend doesn't accumulate and the suite is order-independent / parallel-safe. Keep
  `mode: serial` only if still needed after isolation; prefer removing the implicit
  single-panel dependency.

### Claude's Discretion
- Exact panel test-id shape + whether to add it to `TerminalPanel` or scope via the existing
  workspace-name heading.
- Cleanup mechanism: per-test terminate via the × confirm vs a direct `request.delete` to the
  API (recommend the direct request — faster, no UI flake).
- Whether `mode: serial` stays or the specs become independent.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets / Integration Points
- `ui/src/components/WorkspaceLayout.tsx` — `LeafPanel` already wires `useDestroyWorkspace` →
  `onTerminate`; add the `useInvalidateWorkspaces` → `onTerminalEvent` wiring the same way.
- `ui/src/hooks/useWorkspaces.ts` — `useInvalidateWorkspaces()` (exists, zero call sites today),
  `WORKSPACES_KEY`.
- `ui/src/components/TerminalPanel.tsx` — `onTerminalEvent?: (event) => void` prop (already
  forwarded into `useTerminal`); the panel `<section>` is the natural place for a `panel-${id}`
  test id.
- `ui/src/hooks/useTerminal.ts` — fires `onTerminalEvent("error"|"closed")` on terminal state.
- `ui/src/components/WorkspaceLayout.test.tsx` / `TerminalPanel.test.tsx` — existing vitest
  harnesses (`renderPanel` QueryClient wrapper, MSW) for the UI-12 failing-first test.
- `ui/tests/e2e/stop-start.spec.ts` — the WR-02 target (unscoped `.first()`, global
  `toHaveCount(0)` at line ~80, no `afterEach` cleanup). `terminal.spec.ts` has cleanup patterns.

### Established Patterns
- Server is source of truth; mutations invalidate `WORKSPACES_KEY`, the ~3s poll reconciles.
- Inline styles + tokens; SPDX header on every source file; failing-first regression test per fix.
- e2e over `BURROW_COMPUTE=fake` + stub ttyd; `npm run e2e` must stay green (currently 7/7).
</code_context>

<specifics>
## Specific Ideas
- The UI-12 test must prove the INVALIDATION path specifically (not just that the list refetches
  on its own poll) — drive a terminal error/close and assert the invalidation fired.
- The hardened e2e must remain green repeatably; the win is robustness (scoped + isolated), not
  new coverage.
</specifics>

<deferred>
## Deferred Ideas
- Phase 8 (release-please + harden-runner) and Phase 9 (WSX-01 auto node-select) — separate phases.
- Real-infra acceptance (ACC-01/02/03) — deferred.
</deferred>
