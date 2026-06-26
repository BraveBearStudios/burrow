---
phase: 13-setup-wizard-ui-first-run-gate
plan: 04
subsystem: testing
tags: [playwright, e2e, setup-wizard, first-run-gate, fake-provider, chromium]

# Dependency graph
requires:
  - phase: 13-setup-wizard-ui-first-run-gate
    provides: "13-03 SetupWizard.tsx (the 4-step full-page gate) + App.tsx first-run gate wired on useSetupState().setupCompletedAt"
  - phase: 13-setup-wizard-ui-first-run-gate
    provides: "13-01 backend POST /setup/complete (idempotent setter) + GET /setup/state the spec drives the precondition over"
  - phase: 12-setup-wizard-backend
    provides: "Fake testConnection (success=true) / verifyTemplate (usable=true) + GET /health degrade-not-500 so the wizard auto-advances hermetically"
provides:
  - "ui/tests/e2e/setup-wizard.spec.ts — the Tier-3 Playwright gate journey proving SETUP-06 in real Chromium over the Fake"
  - "A shared-DB-deterministic e2e pattern: gate-visible walkthrough guarded on live /setup/state so the suite is green on a fresh CI DB and a persisted local DB"
affects: [14-acceptance, setup-wizard, first-run-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guarded gate-visible branch: the walkthrough test reads live /setup/state first and test.skip()s when already complete (no setup-reset endpoint exists), so the suite stays green on both a fresh and a persisted shared DB"
    - "Walkthrough-first ordering under mode:serial: the gate-walk test runs FIRST while the shared setup row is still null, then the configured-skip test runs SECOND and leaves setup complete for sibling suites"
    - "Server-truth gate-flip assertion: page.waitForResponse on the real POST /setup/complete (fired by the wizard's create→complete flow) before asserting the gate vanished — not an optimistic client flip"

key-files:
  created:
    - ui/tests/e2e/setup-wizard.spec.ts
  modified: []

key-decisions:
  - "The gate-walkthrough test runs FIRST (mode:serial → file order) so it observes the unconfigured shared setup row before any test marks it complete; the configured-skip test runs second and idempotently leaves setup complete for the sibling suites"
  - "The health step (step 3) auto-advances over the Fake (db+compute ok) with NO interaction; the spec does NOT click Re-check (that races the auto-advance and detaches the button mid-click) and instead waits for the step-4 Create workspace CTA"
  - "The sidebar assertion targets the per-workspace <li> landmark by exact name (getByRole listitem) — NOT a substring text match, because the repo row (github.com/acme/<name> · main) also contains the name"

patterns-established:
  - "First-run gate e2e: read /setup/state → (fresh) gate shown → walk 4 steps over the Fake → real create then complete → gate vanishes to the workspace-manager landmark + the new workspace in the Workspaces nav; (persisted) skip the walkthrough, the configured-skip test still proves the path"
  - "id-scoped afterAll cleanup with expect([200,404]).toContain(res.status()) (the 07r robustness pattern); the Fake DELETE soft-deletes (status→destroyed), the same behavior stop-start relies on"

requirements-completed: [SETUP-06]

# Metrics
duration: 14min
completed: 2026-06-26
---

# Phase 13 Plan 04: Setup Wizard First-Run Gate e2e Summary

**`ui/tests/e2e/setup-wizard.spec.ts` — the Tier-3 Playwright journey proving SETUP-06 in real Chromium: an unconfigured Burrow shows the `Set up Burrow` gate, walking the four steps over the Fake (connection → template → health → create) fires the real create→complete flow that marks setup complete and the gate vanishes to the workspace list; a configured Burrow skips the gate. Both tests pass on a fresh CI DB and a persisted local DB.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-26T03:29:00Z
- **Completed:** 2026-06-26T03:43:00Z
- **Tasks:** 1
- **Files modified:** 1 (1 created)

## Accomplishments

- `ui/tests/e2e/setup-wizard.spec.ts`: two serial Chromium tests over the existing 3-process Fake harness (stub ttyd + FastAPI/Fake + vite preview over the built `ui/dist`) — no new harness.
  - **Test A (unconfigured → gate → walk → complete → vanish):** reads live `/setup/state`; on a fresh DB asserts the `Set up Burrow` `role=dialog` blocks the app (the `Burrow workspace manager` main landmark is NOT mounted), then walks step 1 (Host/User/Token name + a literal `dummy` token → `Validate connection` → auto-advance), step 2 (VMID `9000`/Node `pve` → `Verify template` → auto-advance), step 3 (health auto-probes `GET /health` and auto-advances — no click), step 4 (`#setup-ws-name`/`#setup-ws-repo`, Node left Auto → `Create workspace`). It `waitForResponse`s the real `POST /setup/complete` the wizard fires on create-success, then asserts the gate reaches count 0, the workspace-manager landmark is visible, the new workspace appears in the `Workspaces` nav, and `/setup/state` now returns a non-null `setupCompletedAt`.
  - **Test B (configured → skips gate):** idempotently `POST /setup/complete` as a precondition, then asserts the normal shell (the `Burrow workspace manager` main + the `New workspace` button) renders and the `Set up Burrow` dialog has count 0.
- **Shared-DB determinism:** the gate-visible walkthrough is guarded by the live state — on a persisted local DB (already complete; no setup-reset endpoint exists) Test A `test.skip()`s its walkthrough (the gate is legitimately off) and Test B alone proves the configured-skip path. Verified green on BOTH a fresh DB (2 passed) and a persisted DB (1 skipped, 1 passed).
- **Hygiene:** unique workspace name per run via `Date.now()`; id-scoped `afterAll` cleanup with `expect([200,404]).toContain(res.status())`; only a literal `dummy` token touches the harness (no real PVE credential); the spec leaves setup complete so the sibling suites (stop-start, terminal, activity) stay unblocked.

## Task Commits

Each task was committed atomically:

1. **Task 1: Playwright gate-flow journey (unconfigured → walk → complete → gate off; configured skips)** - `9651a88` (test)

## Files Created/Modified

- `ui/tests/e2e/setup-wizard.spec.ts` - The Tier-3 gate journey: unconfigured-shows-gate→walk-4-steps→real-create→complete→gate-vanishes-to-list, plus configured-skips-gate. Guarded on live `/setup/state` for shared-DB determinism; SPDX header; biome-clean (tabs, double quotes).

## Decisions Made

- **Walkthrough-first ordering.** Under `mode: serial`, tests run in file order. setup-state is a single shared row, so once any test marks it complete the gate can never be observed again in that run. The gate-walk test therefore runs FIRST (against the still-null shared row) and the configured-skip test runs SECOND, leaving setup complete for the sibling suites.
- **No `Re-check` click on step 3.** The health step auto-probes `GET /health` on mount and auto-advances when db+compute are both "ok" (which they are over the Fake). The first authored attempt defensively clicked `Re-check`, which raced the auto-advance and detached the button mid-click (a 30s timeout). The fix: don't interact with step 3 — just wait for the step-4 `Create workspace` CTA.
- **Sidebar assertion by listitem, not text.** The workspace name appears in two spans in the sidebar (the name + the repo row `github.com/acme/<name> · main`). A `getByText(name)` hit strict-mode (2 matches); scoping to the per-workspace `<li aria-label={name}>` via `getByRole("listitem", { name })` is the precise landmark.

## Deviations from Plan

The plan's `<harness_notes>` referenced the create-modal field ids `#ws-name`/`#ws-repo` (the `NewWorkspaceModal` ids). The wizard's step-4 form uses its OWN ids — `#setup-ws-name` / `#setup-ws-repo` / `#setup-ws-branch` / `#setup-ws-node` (verified in `SetupWizard.tsx`). The spec uses the real wizard ids. This is a correction to the plan's illustrative note, not a code change — no deviation rule applies (the wizard DOM is the source of truth).

None - plan executed exactly as written (the two iterations below were in-task test authoring, not deviation-rule fixes).

## Issues Encountered

Two in-task test-authoring iterations (resolved before the task commit, not pre-existing bugs):

1. **Test B initially ran first and consumed the fresh-null state.** As authored, the configured-skip test ran first and idempotently marked setup complete, so the walkthrough test always observed a non-null state and skipped its gate journey. Resolved by reordering so the gate-walk test runs first (against the still-null shared row).
2. **The step-3 `Re-check` click raced the auto-advance** (30s timeout, button detached mid-click). Resolved by removing the click — the Fake health is always ok, so step 3 auto-advances with no interaction.

Both surfaced and were fixed during the verify loop; the committed spec passes on the exact plan verify command (`cd ui && npm run build && npx playwright test setup-wizard`).

## User Setup Required

None - no external service configuration required. The journey is fully CI-provable over the Fake provider; the real first-workspace-on-real-Proxmox walkthrough is the Phase 14 ACC-01 human UAT.

## Verification

- `cd ui && npm run build && npx playwright test setup-wizard` — **2 passed** (exit 0) on a fresh DB: the full gate walkthrough + the configured-skip.
- Re-run on the persisted (complete) DB — **1 skipped, 1 passed** (exit 0): the guarded gate-visible branch correctly skips, the configured-skip path still passes. Green on both DB starting states.
- `cd ui && npx biome check tests/e2e/setup-wizard.spec.ts` — clean (no fixes).
- Cleanup verified: the created `e2e-setup-*` workspace is soft-deleted (status `destroyed`) by the id-scoped `afterAll` — the same behavior the stop-start suite leaves; not a leak.
- The access log shows the real journey end-to-end: `POST /setup/test-connection` → `POST /setup/verify-template` → `GET /health` → `POST /workspaces` → `POST /setup/complete` → gate vanishes.

## Threat Surface Scan

No new security-relevant surface beyond the plan's `threat_model`. T-13-10 honored: the spec types ONLY the literal `dummy` token into the step-1 field — never a real PVE credential; the Fake ignores token values; no secret enters the repo/harness/fixture. T-13-11 honored: the spec leaves the benign `setupCompletedAt` timestamp in the complete state the sibling suites require. T-13-SC honored: no new npm packages — uses the existing `@playwright/test` already wired in the harness.

## Known Stubs

None - the spec drives the real built SPA end-to-end against the Phase 12 setup endpoints + the Phase 13-01 `/setup/complete` setter over the Fake. The literal `dummy` token is a deliberate harness value (T-13-10), not a stub.

## Next Phase Readiness

- SETUP-06 is proven in a real browser; Phase 13 is functionally complete (SETUP-04/05/06 + the WSX-02 UI half across Plans 01-04).
- The Phase 14 ACC-01 human UAT (the real first-workspace-on-real-Proxmox walkthrough) is the only remaining setup-wizard validation, and is out of scope here by design.

## Self-Check: PASSED

The created spec exists on disk and the task commit is in the git log (verified below).

---
*Phase: 13-setup-wizard-ui-first-run-gate*
*Completed: 2026-06-26*
