<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 13-setup-wizard-ui-first-run-gate
verified: 2026-06-26T04:25:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
requirements_verified: [SETUP-04, SETUP-05, SETUP-06]
re_verification: false
---

# Phase 13: Setup Wizard UI + First-Run Gate Verification Report

**Phase Goal:** An unconfigured Burrow presents a guided, re-enterable setup wizard as a first-run gate that walks the operator from token validation through template verification and health to creating their first workspace; once configured the wizard never reappears, and create gains the opt-in persistent toggle.
**Verified:** 2026-06-26T04:25:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                                      | Status     | Evidence                                                                                                                                                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | When `setupCompletedAt` is unset, App renders ONLY SetupWizard (workspace shell absent); once set the wizard never reappears and the operator lands on the workspace list (WR-04 fix test) | ✓ VERIFIED | `App.tsx:55-96` — loading→blank, `setupCompletedAt == null`→ONLY `<SetupWizard/>`, set→`<main aria-label="Burrow workspace manager">` shell. `App.test.tsx:120-155` mounts `<App/>`, overrides `/setup/state` to null, asserts dialog present AND `main`/`project-eta`/New-workspace ABSENT; inverse for configured. e2e confirms live (1 passed). |
| 2   | The wizard's final step creates the first workspace and THEN marks setup complete (POST /setup/complete in create onSuccess); complete-step guards against duplicate workspace if /setup/complete fails (WR-01 fix)         | ✓ VERIFIED | `SetupWizard.tsx:663-799` — `StepCreate` calls `completeSetup` inside `createWorkspace` onSuccess; `workspaceCreated` latch + CTA→"Complete setup" + `finishSetup` onError. `SetupWizard.test.tsx:188-253` asserts `callOrder === ["workspaces","complete"]`; lines 256-333 prove failed complete retries complete-only with `workspaceCalls === ["workspaces"]` (exactly one create).         |
| 3   | Re-opening re-probes current state and lands on the first failing step (idempotent, re-enterable, NO persisted checkpoint)                                                                | ✓ VERIFIED | `SetupWizard.tsx:846` `useState(1)`; grep confirms NO localStorage/sessionStorage/Zustand/persist/checkpoint machine (only doc comments). Step 3 health auto-probes on mount (`:586-588`); steps 1-2 re-validate live. Backend setter idempotent (proven). Token-not-stored (SETUP-07) makes step-1 auto-advance impossible by design — defensible interpretation per UI-SPEC §182 + REVIEW IN-04. |
| 4   | NewWorkspaceModal exposes a persistent checkbox (default unchecked) that submits the persistent flag (criterion 4 / WSX-02 UI half)                                                       | ✓ VERIFIED | `NewWorkspaceModal.tsx:189` `useState(false)`, `:444-459` native checkbox w/ `accentColor: var(--accent)` + exact copy, `:249` wired into `mutateAsync` body. `NewWorkspaceModal.test.tsx:329-368` proves checked→`body.persistent === true`, default→not true.                                  |
| 5   | Backend: setSetupCompleted (idempotent) + GET /setup/state + POST /setup/complete via the envelope; Postgres stub parity                                                                  | ✓ VERIFIED | `provider.py:111-121` abstractmethod; `sqliteProvider.py:384-400` `UPDATE settings SET setupCompletedAt = strftime(...) WHERE id=1` + commit + read-back; `postgresProvider.py:57-61` both stub overrides (NotImplementedError); `setup.py:101-115` both routes `Depends(get_db)` + `respond(...)`. Integration tests `test_setup_api.py:212-271` (null→complete→state→idempotent→routes-registered). |
| 6   | a11y of the hard gate: role=dialog/aria-modal, focus trap, Escape inert, aria-live on error strips + missing-priv list + health readout (WR-02); health checking state during in-flight probe (WR-03); UI-SPEC tokens-only, gold reserved to spinner | ✓ VERIFIED | `SetupWizard.tsx:875-877` role=dialog/aria-modal/aria-label; `:852-854` focus on mount; `:858-863` Escape preventDefault no-op; `StatusRegion` (`:257-269`) wraps error strips/missing-priv/health (WR-02). `healthRowState`/`HEALTH_ROW_STYLE` (`:625-641`) "checking…" muted, never red (WR-03). No hex except documented `rgba(8,13,8,.55)` scrim; `var(--gold)` appears exactly once (StepSpinner `:171`). `SetupWizard.test.tsx:336-346` Escape inert. |

**Score:** 6/6 truths verified

### ROADMAP Success Criteria (the binding contract)

| # | Success Criterion (ROADMAP.md:205-208) | Maps to Truth | Status |
|---|----------------------------------------|---------------|--------|
| 1 | `setupCompletedAt` unset → SetupWizard gate before list; set → no reappear, lands on list | Truth 1 | ✓ VERIFIED |
| 2 | Final step creates first workspace then marks complete, transitions to normal view | Truth 2 | ✓ VERIFIED |
| 3 | Re-opening re-probes, lands on first failing step (idempotent, re-enterable, no persisted checkpoint) | Truth 3 | ✓ VERIFIED |
| 4 | NewWorkspaceModal persistent checkbox (default unchecked) submits the flag (WSX-02 UI half) | Truth 4 | ✓ VERIFIED |

### Required Artifacts

| Artifact                                       | Expected                                          | Status     | Details                                                              |
| ---------------------------------------------- | ------------------------------------------------- | ---------- | ------------------------------------------------------------------- |
| `ui/src/components/SetupWizard.tsx`            | 4-step gate, role=dialog, ≥200 lines              | ✓ VERIFIED | 923 lines; role=dialog; imported+used in App.tsx; tokens-only       |
| `ui/src/App.tsx`                               | gate conditioned on useSetupState                 | ✓ VERIFIED | `useSetupState()` + `setupCompletedAt == null` branch               |
| `ui/src/hooks/useSetup.ts`                     | 4 setup hooks; useCompleteSetup invalidates key   | ✓ VERIFIED | All 4 hooks; `onSuccess` invalidates `["setupState"]`               |
| `ui/src/types/setup.ts`                        | SetupState + contract types                       | ✓ VERIFIED | Wired (imported by useSetup.ts)                                     |
| `ui/src/components/NewWorkspaceModal.tsx`      | persistent checkbox → create body                 | ✓ VERIFIED | Checkbox + `persistent` in mutateAsync body                        |
| `api/db/provider.py`                           | setSetupCompleted abstractmethod                  | ✓ VERIFIED | `@abstractmethod async def setSetupCompleted`                      |
| `api/db/sqliteProvider.py`                     | UPDATE settings SET setupCompletedAt + commit     | ✓ VERIFIED | Real UPDATE WHERE id=1 + commit + read-back                       |
| `api/db/postgresProvider.py`                   | hosted-path stub parity                           | ✓ VERIFIED | getSetupState + setSetupCompleted NotImplementedError overrides    |
| `api/routers/setup.py`                         | GET /setup/state + POST /setup/complete           | ✓ VERIFIED | Both routes, get_db + respond() envelope                          |
| `ui/tests/e2e/setup-wizard.spec.ts`            | Playwright gate journey                            | ✓ VERIFIED | 206 lines; full walkthrough + configured-skip; passes both DB states |

### Key Link Verification

| From                 | To                                  | Via                                     | Status  | Details                                                       |
| -------------------- | ----------------------------------- | --------------------------------------- | ------- | ------------------------------------------------------------ |
| App.tsx              | SetupWizard                         | `setupCompletedAt == null` conditional  | ✓ WIRED | App.tsx:60 renders `<SetupWizard/>` when null                |
| SetupWizard.tsx      | useTestConnection/useVerifyTemplate/useCreateWorkspace/useCompleteSetup | step mutations | ✓ WIRED | Each step wires its hook; complete-after-create in StepCreate |
| useSetup.ts          | /setup/state, /setup/complete, /setup/test-connection, /setup/verify-template | api() client | ✓ WIRED | All four endpoints called via `api<T>(...)`                 |
| useCompleteSetup     | gate flip-off                       | invalidateQueries(["setupState"])       | ✓ WIRED | useSetup.ts:58-59 onSuccess invalidation                     |
| setup.py routers     | db.getSetupState / db.setSetupCompleted | Depends(get_db)                     | ✓ WIRED | Both handlers `Depends(get_db)` + `respond(await db.…())`    |
| sqliteProvider       | settings table (id=1)               | UPDATE statement                        | ✓ WIRED | `UPDATE settings SET setupCompletedAt … WHERE id=1` + commit |
| NewWorkspaceModal    | createWorkspace.mutateAsync body    | persistent state                        | ✓ WIRED | NewWorkspaceModal.tsx:249 `persistent` in body              |

### Data-Flow Trace (Level 4)

| Artifact          | Data Variable        | Source                              | Produces Real Data | Status     |
| ----------------- | -------------------- | ----------------------------------- | ------------------ | ---------- |
| App.tsx gate      | `setupState.setupCompletedAt` | `GET /setup/state` → SQLite settings.id=1 (real SELECT) | Yes — real DB read | ✓ FLOWING |
| SetupWizard step3 | `result` (health)    | `GET /api/v1/health` (live probe on mount) | Yes — real fetch   | ✓ FLOWING |
| SetupWizard step4 | create → complete    | `POST /workspaces` then `POST /setup/complete` (real UPDATE) | Yes — real write   | ✓ FLOWING |
| gate flip-off     | invalidated `["setupState"]` | refetch returns non-null timestamp (real read-back) | Yes                | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior                                   | Command                                            | Result                       | Status  |
| ------------------------------------------ | -------------------------------------------------- | ---------------------------- | ------- |
| UI vitest full suite (incl. 4 review-fix tests) | `cd ui && npx vitest run`                          | 16 files, **128 passed**     | ✓ PASS  |
| API full suite                             | `cd api && uv run pytest -q`                        | **250 passed**, 11 pre-existing warns | ✓ PASS  |
| No debt markers in phase files             | grep TODO/FIXME/XXX/HACK/TBD/PLACEHOLDER           | none found                   | ✓ PASS  |
| Tokens-only (no rogue hex)                 | grep hex in SetupWizard.tsx                         | only documented scrim rgba   | ✓ PASS  |
| Gold reserved to spinner                   | grep `var(--gold)` in SetupWizard.tsx              | 1 occurrence (StepSpinner)   | ✓ PASS  |

### Probe Execution (Playwright e2e)

| Probe                                | Command                                                     | Result                                          | Status |
| ------------------------------------ | ---------------------------------------------------------- | ----------------------------------------------- | ------ |
| setup-wizard e2e (persisted DB)      | `npx playwright test setup-wizard`                         | 1 passed, 1 skipped (gate-walk guarded off on configured DB — by design) | PASS   |
| setup-wizard e2e (fresh DB, reset)   | reset `api/burrow-e2e.db` → `npx playwright test setup-wizard` | **2 passed** (full unconfigured→walk→complete→vanish + configured-skip) | PASS   |

Both DB starting states confirmed green by the verifier in its own process (not trusting SUMMARY PASS claims). The fresh-DB run exercised the headline gate walkthrough end-to-end: `POST /setup/test-connection` → `verify-template` → `GET /health` → `POST /workspaces` → `POST /setup/complete` → gate vanishes to the workspace-manager landmark.

### Requirements Coverage

| Requirement | Source Plan        | Description                                                                                  | Status      | Evidence                                                            |
| ----------- | ------------------ | ------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------ |
| SETUP-04    | 13-01/02/03        | Wizard's final step creates the operator's first workspace                                   | ✓ SATISFIED | StepCreate → useCreateWorkspace → complete-after-create (truth 2)   |
| SETUP-05    | 13-01/02           | Unconfigured → wizard as first-run gate; once configured does not reappear                   | ✓ SATISFIED | App gate + setSetupCompleted + invalidation (truths 1, 5)          |
| SETUP-06    | 13-03/04           | Steps idempotent + re-enterable; re-probe lands on first failing step (no persisted checkpoint) | ✓ SATISFIED | useState(1) re-probe, no checkpoint machine, idempotent setter (truth 3) |
| WSX-02 (UI half) | 13-02         | Persistent checkbox (default unchecked) submits the flag — UI half of Phase-10 WSX-02        | ✓ SATISFIED | NewWorkspaceModal checkbox + test (truth 4). Note: WSX-02 traces to Phase 10 in REQUIREMENTS.md; this is the additive UI completion, not a Phase-13-owned requirement. |

No orphaned requirements: REQUIREMENTS.md maps exactly SETUP-04/05/06 to Phase 13 — all three verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| —    | —    | none    | —        | No debt markers, no stubs, no hardcoded-empty render data, no orphaned artifacts in any phase-modified file. |

The four REVIEW.md warnings (WR-01..WR-04) were the only outstanding robustness/a11y/coverage gaps; all four are fixed in commit `0f58eee` and verified above (truths 1, 2, 6). The four IN-* info items remain as conscious design notes (IN-01 14px step title is a minor visual-contract drift acknowledged in code comment; IN-04 always-step-1 is the documented, security-mandated design). None block the goal.

### Human Verification Required

None for this phase. All four ROADMAP success criteria are CI-provable over the Fake provider and were verified by automated suites + live e2e runs in the verifier's own process. The real first-workspace-on-real-Proxmox walkthrough is the by-design **Phase 14 ACC-01** human UAT, explicitly out of scope here (and CI never touches real Proxmox by design).

### Gaps Summary

No gaps. All 6 phase truths and all 4 ROADMAP success criteria are verified against the actual codebase, not SUMMARY claims:

- The first-run gate replaces the shell when unconfigured and never reappears once set, proven by an App-level vitest (the WR-04 fix that was the REVIEW's headline coverage gap) and confirmed live in Playwright.
- Complete-after-create ordering plus the WR-01 duplicate-workspace guard (latch + complete-only retry) are both locked by vitest with explicit call-order/call-count assertions.
- The wizard carries no persisted checkpoint machine (verified by absence); step-1 token re-entry is a defensible, security-mandated interpretation of "re-enterable" under the SETUP-07 token-not-stored constraint.
- Backend setter is a real idempotent SQLite UPDATE with Postgres-stub ABC parity, integration-tested.
- a11y hard-gate (role=dialog/aria-modal/focus/Escape-inert/aria-live on all status regions/health-checking state) and tokens-only/gold-to-spinner discipline all hold.
- Test counts independently reproduced: UI vitest 128 passed, API 250 passed, e2e green on both fresh and configured DB states.

---

_Verified: 2026-06-26T04:25:00Z_
_Verifier: Claude (gsd-verifier)_
