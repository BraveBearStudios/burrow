---
phase: 13-setup-wizard-ui-first-run-gate
plan: 02
subsystem: ui
tags: [react, tanstack-query, vitest, msw, setup-wizard, persistent]

# Dependency graph
requires:
  - phase: 12-setup-wizard-backend
    provides: "GET/POST /api/v1/setup/* (state, complete, test-connection, verify-template) typed contract"
  - phase: 10-persistence-data-model
    provides: "backend WorkspaceCreate.persistent (bool=False) accepted by POST /api/v1/workspaces"
  - phase: 13-setup-wizard-ui-first-run-gate
    provides: "13-01 backend setup-state writer (POST /setup/complete) the useCompleteSetup hook targets"
provides:
  - "useSetupState query hook (queryKey [\"setupState\"]) the first-run gate reads"
  - "useTestConnection / useVerifyTemplate / useCompleteSetup mutation hooks for the wizard steps"
  - "useCompleteSetup invalidates [\"setupState\"] onSuccess so the gate flips off after create"
  - "setup.ts types (SetupState, ConnectionResult, TemplateResult, TestConnectionBody, VerifyTemplateBody)"
  - "WorkspaceCreate.persistent? optional flag"
  - "NewWorkspaceModal persistent checkbox (default unchecked) wired into the create body (WSX-02 UI half)"
affects: [13-03-app-gate, 13-04-setup-wizard, setup-wizard, persistent]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Setup hooks modelled verbatim on useWorkspaces.ts (useQuery/useMutation + api() envelope unwrap)"
    - "Transient-secret discipline: the Proxmox token is a mutation argument only, never stored/logged client-side"
    - "Native checkbox themed via inline accentColor: var(--accent) (no new palette, no custom control)"

key-files:
  created:
    - ui/src/types/setup.ts
    - ui/src/hooks/useSetup.ts
  modified:
    - ui/src/types/workspace.ts
    - ui/src/components/NewWorkspaceModal.tsx
    - ui/src/components/NewWorkspaceModal.test.tsx

key-decisions:
  - "useSetupState has NO refetchInterval — it is read on mount + invalidated by useCompleteSetup, not polled"
  - "The Proxmox token (TestConnectionBody.tokenValue) is never written to query cache / Zustand / localStorage (T-13-04)"
  - "persistent checkbox resets to false on close via the parent unmounting the modal (fresh useState on remount) — no explicit reset effect needed"

patterns-established:
  - "Setup hooks: copy the useWorkspaces useQuery/useMutation + api() idiom; invalidate the shared key onSuccess"
  - "Token-as-transient-arg: setup mutations take the secret as a body field only, with no client-side persistence/log"

requirements-completed: [SETUP-04, SETUP-05, WSX-02]

# Metrics
duration: 7min
completed: 2026-06-26
---

# Phase 13 Plan 02: Setup Hooks + Persistent Checkbox Summary

**TanStack Query setup hooks (useSetupState/useTestConnection/useVerifyTemplate/useCompleteSetup) typed to the Phase 12 contract, plus the WSX-02 persistent checkbox on NewWorkspaceModal wired into the create body and proven by vitest.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-26T02:42:52Z
- **Completed:** 2026-06-26T02:49:55Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `useSetup.ts`: the four setup hooks — `useSetupState` (query `["setupState"]`, no poll), `useTestConnection` / `useVerifyTemplate` (mutations), `useCompleteSetup` (mutation that invalidates `["setupState"]` onSuccess so the gate flips off), all modelled on `useWorkspaces.ts`.
- `setup.ts`: the five wizard contract types (`SetupState`, `ConnectionResult`, `TemplateResult`, `TestConnectionBody`, `VerifyTemplateBody`) typed to the camelCase Phase 12 backend.
- `WorkspaceCreate.persistent?: boolean` added (mirrors the Phase 10 backend `persistent: bool = False`).
- `NewWorkspaceModal`: a native persistent checkbox (default UNCHECKED = ephemeral) after the Node selector, styled with `accentColor: var(--accent)` and the verbatim copy, wired into `createWorkspace.mutateAsync({ …, persistent })`.
- vitest proves checked → request body `persistent: true`, default → not `true` (MSW request capture).

## Task Commits

Each task was committed atomically:

1. **Task 1: Setup types + the four setup hooks** - `65ae6e0` (feat)
2. **Task 2: Persistent checkbox in NewWorkspaceModal** - `efec223` (feat)
3. **Task 3: vitest — persistent checkbox submits the flag** - `1379f75` (test)

_Task 3 is the TDD verification half; the implementation it proves landed in Task 2 (the persistent checkbox is intentionally built before its regression test in this UI plan)._

## Files Created/Modified
- `ui/src/types/setup.ts` - Wizard contract types (SetupState, ConnectionResult, TemplateResult, TestConnectionBody, VerifyTemplateBody).
- `ui/src/hooks/useSetup.ts` - The four setup hooks + `SETUP_STATE_KEY`; token is a transient mutation arg only.
- `ui/src/types/workspace.ts` - Added optional `persistent?: boolean` to `WorkspaceCreate`.
- `ui/src/components/NewWorkspaceModal.tsx` - `persistent` useState + accent-themed checkbox after Node + wired into the create body.
- `ui/src/components/NewWorkspaceModal.test.tsx` - Two new WSX-02 cases (checked → persistent:true; default → not true).

## Decisions Made
- `useSetupState` deliberately has no `refetchInterval` — it is read on mount and invalidated by `useCompleteSetup`, not polled (the gate state is a one-time timestamp, not a live resource).
- The Proxmox token stays a transient argument to `useTestConnection().mutate(body)`; `useSetup.ts` never writes it to the query cache, Zustand, or localStorage, and never logs it (T-13-04 / T-13-05 mitigations honored).
- The persistent checkbox resets to false on close by relying on the parent unmounting the modal (a fresh `useState(false)` on remount) rather than adding a reset effect — matches how the rest of the modal's form state already behaves.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (App.tsx first-run gate) can now call `useSetupState()` to decide whether to render the wizard and rely on `useCompleteSetup` to invalidate `["setupState"]`.
- Plan 04 (SetupWizard) can wire its three step mutations and reuse the create form (including the new persistent checkbox) for step 4.
- WSX-02 UI half is complete end-to-end against the Phase 10 backend (which already accepts `persistent`); no backend change needed.

## Threat Surface Scan
No new security-relevant surface introduced beyond the plan's threat_model. The token-handling mitigations (T-13-04 transient-only, T-13-05 no client log) are honored in `useSetup.ts`. No new npm packages added (T-13-SC).

## Self-Check: PASSED

All created/modified files exist on disk and all three task commits are in the git log:
- Files: `ui/src/types/setup.ts`, `ui/src/hooks/useSetup.ts`, `ui/src/types/workspace.ts`, `ui/src/components/NewWorkspaceModal.tsx`, `ui/src/components/NewWorkspaceModal.test.tsx`, `13-02-SUMMARY.md` — all FOUND.
- Commits: `65ae6e0`, `efec223`, `1379f75` — all FOUND.
- Verification: `tsc --noEmit` 0, `biome check` clean on all 5 files, `npm run test` 119/119 passed.

---
*Phase: 13-setup-wizard-ui-first-run-gate*
*Completed: 2026-06-26*
