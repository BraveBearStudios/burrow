---
phase: 07-backlog-fixes-fast-reconcile-e2e-hardening
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - ui/src/components/WorkspaceLayout.tsx
  - ui/src/components/TerminalPanel.tsx
  - ui/src/components/WorkspaceLayout.test.tsx
  - ui/tests/e2e/stop-start.spec.ts
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the UI-12 fast-reconcile wiring and the CICD-09 e2e hardening for Burrow v1.2 Phase 7. The core implementation is correct: `LeafPanel` wires `onTerminalEvent` to `useInvalidateWorkspaces` exactly like `onTerminate`, the callback identity is stable, no infinite re-render is introduced, and no workspace status is mirrored into Zustand (server-truth preserved). The new vitest case genuinely proves the invalidation path (spy on `invalidateQueries` keyed to `WORKSPACES_KEY`, driven by a real socket close), not just the poll. The `panel-${id}` testid does not collide with `term-${id}`. SPDX headers are present on all four files.

The findings below are all in the e2e hardening (CICD-09) and one test-robustness gap in the vitest case. None are blockers, but three weaken the guarantees the phase claims to add.

## Warnings

### WR-01: `afterEach` cleanup is shared global state across all test files — leaks under non-serial sharding and masks per-test scope

**File:** `ui/tests/e2e/stop-start.spec.ts:37, 86-94`
**Issue:** `createdIds` is a single module-level array mutated by `createWorkspace` (push) and drained by `afterEach` (pop until empty). This works only because `test.describe.configure({ mode: "serial" })` forces in-file serial execution. The comment claims the scoping keeps the suite "order-independent / parallel-safe," but the design is the opposite of parallel-safe: a shared mutable array cannot isolate concurrent tests. If a future edit drops `mode: "serial"` (or Playwright runs describe blocks in parallel workers), two tests racing `createWorkspace` + `afterEach` will pop each other's ids, leaving rows alive and deleting the wrong workspace. The drain-to-empty `while` loop also means `afterEach` deletes EVERY tracked id, not "only this test's created ids" — across the serial file the array only ever holds the current test's ids by timing accident, not by construction.
**Fix:** Scope the tracking per test, not per module, so the invariant is structural rather than timing-dependent:
```ts
// Track ids per-test via a fixture or a Map keyed by test info, e.g.:
const createdByTest = new Map<string, string[]>();
// in createWorkspace: createdByTest.get(testInfo.testId)!.push(id)
// in afterEach: drain only createdByTest.get(testInfo.testId)
```
At minimum, add a comment that the cleanup correctness DEPENDS on `mode: "serial"` and assert it, so a later parallelization edit fails loudly instead of silently leaking rows.

### WR-02: `afterEach` swallows the DELETE result — a failing cleanup is invisible and can mask backend leaks

**File:** `ui/tests/e2e/stop-start.spec.ts:92`
**Issue:** `await request.delete(...)` discards the response. The comment says "A 404 is fine," but the code accepts ANY status — a 500, a 409, or a hung backend that returns an error body all pass silently. The stated goal of CICD-09 is that cleanup "can't leak/mask failures," yet a DELETE that returns 500 leaves the row alive AND reports nothing. The Fake backend then accumulates exactly the state this isolation was added to prevent, and because the global locators are now panel-scoped (`panel-${id}`), the leak is invisible until a much later, unrelated test fails on a stale list.
**Fix:** Assert the DELETE resolves to an acceptable status, treating only 404 as the benign "already terminated" case:
```ts
const res = await request.delete(`/api/v1/workspaces/${id}`);
expect(res.status() === 404 || res.ok(), `cleanup of ${id} failed: ${res.status()}`).toBeTruthy();
```

### WR-03: Round-trip Start is scoped to the placeholder, hiding the documented two-affordance behavior — but the header Start button is now never exercised

**File:** `ui/tests/e2e/stop-start.spec.ts:136-148`
**Issue:** The fix correctly resolves the strict-mode two-match problem by scoping the Start click to `panel.getByRole("status").filter({ hasText: "Workspace stopped" })`. That proves the placeholder CTA fires `/start`. However, the previous global assertion (`[data-testid^="term-"].toHaveCount(0)`) was the only check that the WHOLE panel had no terminal body while stopped; that is now panel-scoped (good), but no test anywhere asserts that the stopped panel renders exactly TWO "Start workspace" controls (header + placeholder). The vitest test (WorkspaceLayout.test.tsx:251-255) clicks `getAllByRole(...)[0]` and only documents "two affordances" in a comment — it never asserts the count is 2. So if a regression collapses the two Start affordances into one (e.g., the header Start button is dropped while stopped), every test still passes: the placeholder CTA alone satisfies both the e2e (`role=status` scope) and the vitest (`[0]`). The two-affordance invariant the comments lean on is unverified.
**Fix:** Add an explicit count assertion so the invariant bites. In vitest:
```ts
expect(screen.getAllByRole("button", { name: "Start workspace" })).toHaveLength(2);
```
Or in the e2e, before scoping the click, assert `await expect(panel.getByRole("button", { name: "Start workspace" })).toHaveCount(2)`.

## Info

### IN-01: Fast-reconcile invalidation fires on EVERY reconnect attempt, not only on a terminal state — comment is misleading

**File:** `ui/src/hooks/useTerminal.ts:267` (called via `onTerminalEvent` wired at `WorkspaceLayout.tsx:136`)
**Issue:** The UI-12 comment (TerminalPanel.tsx:39, WorkspaceLayout.tsx:66-69) and the prop JSDoc describe `onTerminalEvent` as firing "when the terminal hits a terminal state." In practice `scheduleReconnect` calls `onEventRef.current?.("closed")` on every retry (up to 5 attempts), each invalidating `WORKSPACES_KEY`. This is correct behavior (a dropped socket IS fresher than the poll and warrants a refetch), but it is NOT a "terminal state" — it is a transient one, and it can issue up to 5 list refetches during one reconnect storm. Not a correctness bug given the v1 list size, but the naming ("terminal state", event type `"closed"`/`"error"`) understates the fire frequency. Worth a one-line comment so a future reader does not assume single-fire semantics.
**Fix:** Update the JSDoc on `onTerminalEvent` to note it fires on each reconnect attempt as well as on the final error, or rename to reflect "any connection-loss event."

### IN-02: vitest invalidation test does not assert the spy fired exactly once / only with the workspaces key

**File:** `ui/src/components/WorkspaceLayout.test.tsx:297-301`
**Issue:** The test spies on `invalidateQueries` AFTER mount and asserts `toHaveBeenCalledWith({ queryKey: WORKSPACES_KEY })`. Because the spy is installed after the initial fetch, this correctly isolates the terminal-driven call. But `toHaveBeenCalledWith` only checks that SOME call matched; combined with IN-01 (the close handler can fire repeatedly) and the ~3s poll's own invalidations, the assertion would still pass if the wiring accidentally invalidated a different key too. The test proves "the right key was invalidated at least once" but not "only the right key was invalidated by the terminal event." This is acceptable for the phase's intent, noted for completeness.
**Fix:** Optionally tighten to assert the spy was called with the workspaces key and not with unrelated keys, or assert call count for the single emitted close.

## Verification notes (no defect)

- **UI-12 wiring correct:** `useInvalidateWorkspaces` (useWorkspaces.ts:31-36) returns a closure that calls `queryClient.invalidateQueries`; `useQueryClient` returns a stable client, so the callback is stable across renders. It is passed straight through as `onTerminalEvent` and stored in `onEventRef` (useTerminal.ts:139-140) without entering the effect deps `[workspaceId, status]`, so no re-render/effect-rerun loop. Confirmed.
- **No status mirrored into Zustand:** `LeafPanel` reads workspace status only from the server list (`workspace?.status`, WorkspaceLayout.tsx:132); the invalidation triggers a refetch only. Test asserts `layoutAfter` has no `status` property and `mosaicNode`/`activeWorkspaceId` are unchanged. Confirmed.
- **panel testid no collision:** `data-testid="panel-${id}"` is on the outer `<section>` (TerminalPanel.tsx:295); `data-testid="term-${id}"` is on the inner body div (line 483). Distinct attributes, nested, no overlap. `panel.locator('[data-testid^="term-"]')` resolves the body within the panel scope. Confirmed.
- **Panel-scoped term-gone assertion preserved:** `panel.locator('[data-testid^="term-"]').toHaveCount(0)` (stop-start.spec.ts:127) still proves the terminal body is gone while stopped, now scoped to one panel instead of the whole grid — strictly stronger isolation, not weaker. Confirmed.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
