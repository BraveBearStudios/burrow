---
phase: 05-stop-start-controls-drawer-polish
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - ui/src/components/TerminalPanel.tsx
  - ui/src/components/TerminalPanel.test.tsx
  - ui/src/components/WorkspaceLayout.tsx
  - ui/src/components/WorkspaceLayout.test.tsx
  - ui/src/components/ActivityDrawer.tsx
  - ui/src/components/ActivityDrawer.test.tsx
  - ui/src/hooks/useTerminal.test.tsx
  - ui/src/index.css
  - ui/tests/css-rules.test.ts
  - ui/tests/e2e/stop-start.spec.ts
  - ui/tests/msw/handlers.ts
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 5 Stop/Start lifecycle controls and drawer-polish slice across the
TerminalPanel/WorkspaceLayout/ActivityDrawer components, their tests, the index.css
token/focus/scrollbar rules, the CSS-source guard, the e2e journey, and the MSW
handlers. The core implementation is sound on the high-risk axes the review focus
called out: the Stop/Start gating is show-only-applicable; status is server-truth
(no optimistic Zustand mirror); the `stopped` placeholder branches BEFORE the
`termStatus` overlays so no transient error scrim flashes during tear-down; the
`useTerminal` effect cleanly closes the socket and clears the backoff timer on
`running→stopped` (proven by `useTerminal.test.tsx`); and the CSS uses tokens only
with no hex and no gold-as-status.

No BLOCKER-tier defects were found. The most material issue is a plumbed-but-unwired
`onTerminalEvent` / `useInvalidateWorkspaces` seam: the Pitfall-4 fast-reconcile is
documented end-to-end but never connected at the `WorkspaceLayout` integration point,
so a terminal error/close degrades silently to the 3s poll. The remainder are
robustness and test-strength observations.

Note on the Plan 05-02 `getByRole → getAllByRole` change: the duplicate
`Start workspace` accessible name (header button + placeholder CTA) is an explicit
05-UI-SPEC decision (UI-SPEC lines 142, 448-450), not a defect the test is masking.
The migrated tests still prove the gating contract (Stop-only-running, Start-only-
stopped, neither otherwise) and the pending-disable contract. See IN-01 for the one
strength regression in the assertion.

## Warnings

### WR-01: `onTerminalEvent` / `useInvalidateWorkspaces` plumbed end-to-end but never wired at the integration point (Pitfall-4 fast-reconcile is dead)

**File:** `ui/src/components/WorkspaceLayout.tsx:123-134` (also `ui/src/hooks/useWorkspaces.ts:9,31` and `ui/src/components/TerminalPanel.tsx:39-40,270,278`)
**Issue:** `TerminalPanel` declares `onTerminalEvent` and forwards it into
`useTerminal(id, status, { onTerminalEvent })`, and `useTerminal` invokes it on every
reconnect/close and on the terminal error/closed states. The `useWorkspaces` module
header (line 9) and the `TerminalPanel` prop docstring (line 39) both promise this
fires the WS-event reconciliation: "Fired when the terminal hits a terminal state
(Pitfall 4: invalidate list)." But `LeafPanel` in `WorkspaceLayout.tsx` — the only
production caller — never passes `onTerminalEvent`, and `useInvalidateWorkspaces` has
zero call sites outside its own unit test. The result: when a worker terminal errors
or dies, the workspace list is NOT invalidated; the UI only reconciles on the next ~3s
poll. The documented "WS events are fresher than the poll" behavior does not exist in
the shipped tree. Because `WorkspaceLayout.tsx` is a Phase-5 changed file and is the
integration seam, this is in scope. Not a BLOCKER (the 3s poll provides eventual
correctness), but the feature is silently absent and the dead export will mislead the
next reader.
**Fix:** Wire the invalidation at the leaf, e.g.:
```tsx
function LeafPanel({ id, workspace }: { id: string; workspace?: Workspace }) {
  // ...
  const invalidateWorkspaces = useInvalidateWorkspaces();
  // ...
  return (
    // ...
    <TerminalPanel
      // ...
      onTerminalEvent={(event) => {
        if (event === "error" || event === "closed") invalidateWorkspaces();
      }}
    />
  );
}
```
If the fast-reconcile is intentionally deferred to a later phase, delete
`useInvalidateWorkspaces` and the `onTerminalEvent` props (and their docstrings) so the
code does not advertise behavior it does not implement.

### WR-02: e2e Stop/Start journey relies on `.first()` over a non-isolated backend, so a stale panel can be targeted

**File:** `ui/tests/e2e/stop-start.spec.ts:30,52-105`
**Issue:** The spec runs `test.describe.configure({ mode: "serial" })` against a single
long-lived FastAPI + SQLite + FakeComputeProvider stack (`playwright.config.ts`
`reuseExistingServer: !CI`, `DATABASE_PATH: ./burrow-e2e.db`) with no per-test DB reset
and no `afterEach`/`afterAll` cleanup. Every Stop/Start/Activity interaction selects
`getByRole("button", { name: "Stop workspace" }).first()` /
`.getByText("Workspace stopped")` without scoping to the just-created panel. Per-test
localStorage isolation (fresh Playwright context → empty mosaic layout) means normally
only the newly created workspace's panel is open, which is what keeps `.first()`
working today. But that invariant is implicit: a leaked persisted layout, a reused
context, or a future test that opens two panels makes `.first()` target the wrong
panel and the assertions pass against the wrong workspace. The `Workspace stopped`
text assertion (line 76) and `term-` count assertion (line 80) are global, not
panel-scoped, so a second still-running panel would also break them.
**Fix:** Scope the lifecycle assertions to the panel under test. Capture the panel
section after create (e.g. by the workspace name in the header) and run the
Stop/placeholder/Start/term-count queries `within` that panel locator, and/or add a
`test.beforeAll` that resets the e2e DB so serial state is deterministic:
```ts
const panel = page.locator("section", { hasText: wsName });
await panel.getByRole("button", { name: "Stop workspace" }).click();
await expect(panel.getByText("Workspace stopped")).toBeVisible();
await expect(panel.locator('[data-testid^="term-"]')).toHaveCount(0);
```

### WR-03: Global `* { scrollbar-* }` + `* :focus-visible` apply to react-mosaic's own chrome, which Burrow does not own

**File:** `ui/src/index.css:295-298,307-328`
**Issue:** The new `:focus-visible` ring and the Firefox `* { scrollbar-width: thin;
scrollbar-color: ... }` rule are intentionally global. The focus ring is fine and
matches the `[data-active]` outline (different elements: the ring lands on the focused
`<button>`/`<input>`, the active outline on the non-focusable wrapper `<div>` that has
no `tabIndex`, so they never paint on the same element). The concern is the universal
`*` scrollbar selector: react-mosaic's imported base CSS and its internal scroll
containers (drop-target overlays, split panes) now inherit `scrollbar-width: thin` and
the token colors. That is almost certainly desired, but it is an un-scoped blast radius
on third-party chrome the project explicitly states it does not theme beyond
`.burrow-mosaic` (WorkspaceLayout header comment). No functional bug, but a
maintainability/scope risk: a future mosaic upgrade that ships its own scrollbar
styling will silently fight this rule.
**Fix:** If the intent is "every Burrow scroll surface," prefer scoping to the app root
(e.g. `#root *` or a `.burrow` class on `<body>`) rather than the bare universal
selector, so library-owned chrome is excluded. Low urgency; flag for the scope-
discipline convention in CLAUDE.md.

## Info

### IN-01: Gating test weakened the affordance-count assertion from exact to `>= 1`

**File:** `ui/src/components/TerminalPanel.test.tsx:254-256,324-326`
**Issue:** The Plan 05-02 migration to `getAllByRole("button", { name: "Start
workspace" }).length).toBeGreaterThanOrEqual(1)` proves "at least one Start affordance
exists when stopped," but a regression that accidentally dropped the header Start
button (leaving only the placeholder CTA, or vice-versa) would still pass. The
companion pending test (lines 351-352) does assert `>= 2`, so the two-affordance
contract is covered there — but the pure gating test no longer guards the count.
**Fix:** In the gating test assert the exact expected count for the stopped state
(`.length).toBe(2)`) so a dropped affordance is caught at the gating boundary, not only
in the pending path.

### IN-02: Duplicate `Start workspace` accessible name is spec-sanctioned but still a minor SR ergonomics cost

**File:** `ui/src/components/TerminalPanel.tsx:359-380,457-472`
**Issue:** When stopped, two buttons share the identical accessible name
`Start workspace` (header icon button + placeholder CTA). This is explicitly mandated
by 05-UI-SPEC (lines 142, 448-450), so it is NOT a defect introduced here, and both
fire the same idempotent mutation so a "wrong one" click is harmless. For a screen-
reader user navigating the buttons list, the two identical entries give no positional
hint. Recorded as Info (spec decision, low impact, both affordances functionally
equivalent), not a finding to block on.
**Fix:** Optional: differentiate via context, e.g. the placeholder CTA could carry
`aria-label="Start workspace"` while the header button uses
`aria-label="Start workspace (header)"`, or wrap the placeholder in a labelled region
so SR users get disambiguation. Coordinate any change with the UI-SPEC owner since the
copy is locked.

### IN-03: `aria-live="polite"` on the populated event `<ul>` will announce the entire reversed list on each poll

**File:** `ui/src/components/ActivityDrawer.tsx:395`
**Issue:** The newest-first list carries `aria-live="polite"` on the `<ul>` whose
children are re-rendered (reversed) on every 3s poll. Because the list is reversed
client-side and keyed by `event.id`, a new event prepends row 0 and shifts existing
rows; depending on the SR, this can re-announce more than just the new row. The intent
(announce newly-polled events) is reasonable but the live region is coarse.
**Fix:** Consider moving `aria-live` to a dedicated visually-hidden status node that
announces only the latest event delta, or use `aria-relevant="additions"`, so polls do
not re-read the full feed. Low priority; no functional bug.

### IN-04: `dataSummary` stringifies arbitrary `data` values, leaning on server redaction with no client guard

**File:** `ui/src/components/ActivityDrawer.tsx:156-160`
**Issue:** `dataSummary` renders every `key: value` from the event `data` object
verbatim (`JSON.stringify` for non-strings). The drawer header comment states the
`data` is server-redacted and the drawer is read-only (threat T-04-03A/B), so this is
by design — but there is no client-side length cap or key allow-list, so a large or
unexpectedly-unredacted `data` payload renders in full into the DOM. Not exploitable
on its own (it is text content, not HTML — React escapes it, so no XSS), and v1 is
LAN-only by design. Recorded as a defense-in-depth note.
**Fix:** Optional hardening: truncate very long values and/or render only a known set
of keys, so a backend redaction miss does not surface raw payload in the UI.

### IN-05: `formatTime` uses the browser locale/timezone with no test for the fallback branch

**File:** `ui/src/components/ActivityDrawer.tsx:163-169`
**Issue:** `formatTime` returns `d.toLocaleTimeString("en-GB", { hour12: false })`,
which renders in the viewer's local timezone — fine for a single-operator LAN tool, but
the displayed HH:MM:SS is implicitly TZ-dependent and untested for that. The
`Number.isNaN` guard returns the raw `createdAt` string on a bad date, which is a
sensible fallback but has no covering test. No bug; noting the untested branch and the
implicit-TZ behavior.
**Fix:** Optional: add a test for the invalid-date fallback, and decide whether the row
timestamp should be UTC or local (document it either way).

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
