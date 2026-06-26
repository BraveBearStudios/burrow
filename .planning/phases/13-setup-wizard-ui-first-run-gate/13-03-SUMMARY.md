---
phase: 13-setup-wizard-ui-first-run-gate
plan: 03
subsystem: ui
tags: [react, tanstack-query, vitest, msw, setup-wizard, first-run-gate, a11y]

# Dependency graph
requires:
  - phase: 13-setup-wizard-ui-first-run-gate
    provides: "13-02 setup hooks (useSetupState/useTestConnection/useVerifyTemplate/useCompleteSetup) + setup.ts types + WorkspaceCreate.persistent"
  - phase: 12-setup-wizard-backend
    provides: "POST /setup/test-connection + /verify-template (FIXED token-free _SAFE_ERROR_MESSAGES) + GET /api/v1/health degrade-not-500 {status,db,compute}"
  - phase: 13-setup-wizard-ui-first-run-gate
    provides: "13-01 backend POST /setup/complete (idempotent setter) the create step targets"
provides:
  - "SetupWizard.tsx — the full-page first-run GATE: 4 auto-advancing steps, re-probe-to-first-failing, complete-after-create, hard-gate a11y"
  - "App.tsx first-run gate: setupCompletedAt==null renders ONLY the wizard; set renders the normal shell; loading renders a themed blank"
  - "default MSW /setup/state handler (configured Burrow) so the App-shell test harness renders the normal surface"
affects: [setup-wizard, first-run-gate, 14-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stateless re-probe gate: step position derived from live state via setStep(1..4) only — NO persisted checkpoint machine (localStorage/Zustand)"
    - "complete-after-create: useCompleteSetup fires ONLY inside the step-4 createWorkspace onSuccess path"
    - "Transient-secret discipline carried into the UI: the Proxmox token lives ONLY in step-1 form state, passed to useTestConnection.mutate, never stored/logged"
    - "Hard-gate a11y: role=dialog + aria-modal + focus-on-mount + Enter-submits but Escape-DOES-NOTHING (overrides the dismissible NewWorkspaceModal idiom)"
    - "Dialog-level Enter-submit wired via an ActiveSubmitContext ref the active step registers (no module-level singleton)"

key-files:
  created:
    - ui/src/components/SetupWizard.tsx
    - ui/src/components/SetupWizard.test.tsx
  modified:
    - ui/src/App.tsx
    - ui/tests/msw/handlers.ts
    - ui/src/App.test.tsx

key-decisions:
  - "The wizard derives its starting step from live state only (an unconfigured Burrow opens on step 1); it reads NO persisted checkpoint (CONTEXT.md criterion 3)"
  - "Step 3 health auto-probes on mount via api<{status,db,compute}>('/health'); both db+compute must read 'ok' to auto-advance, else a degraded two-row readout + Re-check"
  - "The default MSW /setup/state double reports a CONFIGURED Burrow so every existing <App /> test renders the normal shell; gate-on tests override via server.use(...) and render <SetupWizard /> directly"

patterns-established:
  - "First-run gate: App reads useSetupState and renders loading-blank / wizard-only / normal-shell; the gate flips off when useCompleteSetup invalidates ['setupState']"
  - "Stateless multi-step wizard: internal setStep + auto-advance on each mutation success, inline error+retry with inputs preserved, no resume machine"

requirements-completed: [SETUP-04, SETUP-06]

# Metrics
duration: 17min
completed: 2026-06-26
---

# Phase 13 Plan 03: Setup Wizard + First-Run Gate Summary

**The full-page first-run GATE: `SetupWizard.tsx` (four auto-advancing steps — token validation → template verify → health → create first workspace, re-probe-to-first-failing, complete-after-create, hard-gate a11y) wired into `App.tsx` as a hard block on `useSetupState().setupCompletedAt === null`, proven by a vitest suite over MSW.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-26T02:58:37Z
- **Completed:** 2026-06-26T03:15:22Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `SetupWizard.tsx`: the full-page gate to the binding 13-UI-SPEC. Overlay + 400px card idiom lifted from `NewWorkspaceModal` but WITHOUT click-to-dismiss and WITHOUT a `✕` close (hard gate). `role="dialog"` + `aria-modal="true"` + `aria-label="Set up Burrow"`, focused on mount. The vertical 4-row checklist reuses the glyph contract (pending `○`, active `StepSpinner` with the gold top-arc, passed `✓`).
- Four auto-advancing steps:
  - **Step 1 (connection):** Host/User/Token name/Token value fields (token = `<input type="password">` + the always-visible "Validated in memory only" helper). success → advance; `success=false` renders the mono missing-privilege list (NOT an error strip); `setup_unreachable`/`setup_auth_failed` map to the verbatim UI-SPEC copy + inline retry (inputs preserved).
  - **Step 2 (template):** Template VMID / Node fields → `usable=true` advances; `exists&&!usable` → "not a template" guidance; `setup_template_not_found`/`exists=false` → the not-found guidance.
  - **Step 3 (health):** auto-probes `GET /api/v1/health` on mount; `db==="ok" && compute==="ok"` advances, else two status-dot rows (Database/Compute, `--ok` "ok" / `--err` "unreachable") + a degraded strip + Re-check.
  - **Step 4 (create):** reuses the create-form fields incl. the persistent checkbox → `useCreateWorkspace` → on success `useCompleteSetup.mutate()` (complete-AFTER-create); a create envelope error surfaces `error.message` verbatim, CTA stays "Create workspace".
- Re-probe: position derived from live state via `setStep` only — an unconfigured Burrow opens on step 1; NO persisted checkpoint machine.
- Hard-gate a11y: `Escape` does NOTHING (overridden), focus on the card on mount, `Enter` submits the active step's CTA (wired via an `ActiveSubmitContext` ref the active step registers), `aria-live="polite"` status region.
- Tokens-only (no hex): green (`--accent`) for the CTA + `✓` rows; gold (`--gold`) reserved to the `StepSpinner` top-arc ONLY; `--err` for the error strip + invalid borders.
- `App.tsx`: reads `useSetupState()`; `isLoading` → themed `--bg` blank root (no workspace-list flash); `setupCompletedAt == null` → renders ONLY `<SetupWizard />`; set → the existing Navbar + WorkspaceList + WorkspaceLayout + StatusBar shell, unchanged. The gate flips off when `useCompleteSetup` invalidates `["setupState"]`.
- vitest (`SetupWizard.test.tsx`): 6 cases — gate render, step-1 auto-advance, mapped `setup_auth_failed` + inline retry, missing-privilege list, the full 1→2→3→4 walk asserting `/setup/complete` POSTed AFTER `/workspaces` (call-order capture), and Escape-is-inert.

## Task Commits

Each task was committed atomically:

1. **Task 1: SetupWizard.tsx — the 4-step full-page gate** - `13052e6` (feat)
2. **Task 2: App.tsx first-run gate** - `050a9f1` (feat)
3. **Task 3: vitest gate suite + App-shell harness fix** - `11d9d5c` (test)

## Files Created/Modified

- `ui/src/components/SetupWizard.tsx` - The full-page first-run gate: 4 auto-advancing steps, re-probe-to-first-failing, complete-after-create, mapped token-free errors, missing-priv list, hard-gate a11y. Tokens-only; token never stored/logged.
- `ui/src/components/SetupWizard.test.tsx` - The vitest suite locking gate render / auto-advance / mapped error + inline retry / missing-priv list / complete-after-create ordering / Escape-is-inert.
- `ui/src/App.tsx` - The first-run gate conditioned on `useSetupState()`: loading-blank / wizard-only / normal-shell.
- `ui/tests/msw/handlers.ts` - Added the default `GET /api/v1/setup/state` handler (configured Burrow) so the existing `<App />` tests render the normal surface.
- `ui/src/App.test.tsx` - The four App-shell tests now await the gate resolving to the configured shell before asserting (the gate adds a loading phase before the shell).

## Decisions Made

- The wizard is a stateless re-probe gate: its step position comes from live state via an internal `setStep(1..4)` only, never a persisted checkpoint (CONTEXT.md criterion 3, deferred "resume machine" explicitly rejected).
- Step 3 health auto-probes on mount (a small `useEffect` calling `api<{status,db,compute}>("/health")`) so the health step self-checks without a manual click; both `db` and `compute` must read `"ok"` to advance. The backend reports `"error"` (not `"unreachable"`) per dependency; the UI renders the literal "ok"/"unreachable" text against the dot (status is never color-only).
- The dialog-level Enter-submit is wired via an `ActiveSubmitContext` (a ref the active step's `StepFooter` registers when enabled) rather than a module-level mutable singleton — keeps the wizard re-mountable and test-isolated.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] App.tsx gate broke the existing `<App />`-rendering test harness**
- **Found during:** Task 2 (caught when running the full UI suite after Task 3)
- **Issue:** Adding the `useSetupState()` gate to `App.tsx` made every `<App />` render depend on a `GET /api/v1/setup/state` response. The shared MSW handlers had no such handler, so the App-shell tests (`src/App.test.tsx`, 4) and the restore integration tests (`tests/integration/restore.test.tsx`, 2) rendered the loading-blank root and their synchronous assertions failed (6 failures).
- **Fix:** Added a default `GET /api/v1/setup/state` handler to `ui/tests/msw/handlers.ts` returning a CONFIGURED Burrow (non-null `setupCompletedAt`) so the normal shell renders by default; updated the four `src/App.test.tsx` cases to `await` the gate resolving to the shell before their synchronous assertions. The 6 failing tests went green; the gate-on cases live in `SetupWizard.test.tsx` (which renders `<SetupWizard />` directly + overrides `/setup/state` per case). This is the source-of-truth fix (real Burrow defaults to configured once set), not a per-test workaround.
- **Files modified:** `ui/tests/msw/handlers.ts`, `ui/src/App.test.tsx`
- **Commit:** `11d9d5c`

## Issues Encountered

None beyond the Rule 1 harness fix above.

## User Setup Required

None - no external service configuration required (CI-provable over the Fake provider; the real first-workspace-on-real-Proxmox walkthrough is the Phase 14 ACC-01 human UAT).

## Verification

- `cd ui && npx tsc --noEmit` — exit 0 (clean).
- `cd ui && npx biome check src/components/SetupWizard.tsx src/App.tsx src/components/SetupWizard.test.tsx tests/msw/handlers.ts src/App.test.tsx` — clean (5 files, no fixes).
- `cd ui && npx vitest run src/components/SetupWizard.test.tsx` — 6/6 passed.
- `cd ui && npm run test` — 125/125 passed (16 files), including the 6 SetupWizard cases and the now-fixed App-shell + restore tests.
- Visual contract: no hex in `SetupWizard.tsx` (`grep` confirms `--gold` appears only in the StepSpinner top-arc + a comment); Escape inert; `aria-live` status region present.

## Threat Surface Scan

No new security-relevant surface beyond the plan's `threat_model`. T-13-07 honored: the Proxmox token lives ONLY in step-1 `useState`, is passed to `useTestConnection.mutate`, and is never written to the query cache / Zustand / localStorage and never logged (the field is `type="password"`). T-13-09 honored: only the FIXED token-free mapped messages + static UI guidance reach the DOM — no token or raw exception text is interpolated. T-13-SC honored: no new npm packages.

## Known Stubs

None - the gate is wired end-to-end against the Phase 12 endpoints + the Phase 13-01 `/setup/complete` setter. The step-4 "Node" field is a free-text input (placeholder "Auto (least-loaded)") rather than the `useNodes` select used in `NewWorkspaceModal`; empty maps to `node: null` (the same Auto sentinel the backend auto-selects), so it is a functional simplification, not a stub.

## Self-Check: PASSED

All created/modified files exist on disk and all three task commits are in the git log (verified below).

---
*Phase: 13-setup-wizard-ui-first-run-gate*
*Completed: 2026-06-26*
