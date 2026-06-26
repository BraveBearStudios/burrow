---
phase: 13-setup-wizard-ui-first-run-gate
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - api/db/provider.py
  - api/db/sqliteProvider.py
  - api/db/postgresProvider.py
  - api/routers/setup.py
  - api/tests/integration/test_setup_api.py
  - ui/src/App.tsx
  - ui/src/App.test.tsx
  - ui/src/components/SetupWizard.tsx
  - ui/src/components/SetupWizard.test.tsx
  - ui/src/components/NewWorkspaceModal.tsx
  - ui/src/components/NewWorkspaceModal.test.tsx
  - ui/src/hooks/useSetup.ts
  - ui/src/types/setup.ts
  - ui/src/types/workspace.ts
  - ui/tests/e2e/setup-wizard.spec.ts
  - ui/tests/msw/handlers.ts
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the Phase 13 first-run gate + setup wizard against the binding `13-UI-SPEC.md`,
the project conventions (`/api/v1` envelope, snake_case→camelCase, SPDX, token-free error
copy), and the six scrutiny axes in the brief.

The core security and correctness claims hold up. The Proxmox token entered in step 1 is
genuinely transient: it lives only in `useState("")`, is passed solely as a TanStack
mutation argument, is never written to localStorage / Zustand / the query cache, never
logged, and never echoed in any error UI (the connection error path runs through
`mapError`, which discards `err.message` and uses fixed copy keyed on `ApiError.code`).
The field is `type="password"`. **No CRITICAL token-handling defect was found.** The gate
render logic in `App.tsx` is correct (themed-blank while loading, ONLY `<SetupWizard/>`
when `setupCompletedAt == null` with the shell omitted, normal shell otherwise; fail-closed
to the gate when the state query errors). The backend `setSetupCompleted` is a plain
idempotent `UPDATE ... WHERE id = 1` writing the same ISO-8601 `strftime` shape the rest of
the codebase uses, reading back through `getSetupState`; the `003` migration always seeds the
`id=1` row first, so the "complete returns null forever" failure cannot occur. Postgres stub
parity is intact (both setup methods raise `NotImplementedError`, keeping the ABC concrete).
Error copy maps exactly to the real backend codes (`setup_unreachable` / `setup_auth_failed`
/ `setup_template_not_found`) plus the missing-privileges success path. Tokens-only styling
holds (only literal is the verbatim `rgba(8,13,8,.55)` scrim copied from `NewWorkspaceModal`),
gold is reserved to the `StepSpinner`, reduced-motion stills the spinner via the global rule.

The defects below are robustness, accessibility, and test-coverage gaps — none block on
security, but WR-01 carries a real duplicate-resource risk and WR-04 leaves the headline
gate-replacement behavior unproven in the vitest tier.

## Warnings

### WR-01: Failed `/setup/complete` strands a created workspace and re-enables a duplicating CTA

**File:** `ui/src/components/SetupWizard.tsx:633-647`
**Issue:** In `StepCreate.submit`, the create mutation's `onSuccess` fires
`completeSetup.mutate()` as fire-and-forget — there is **no `onError` on the complete
mutation**. If `POST /setup/complete` fails (network blip, transient 5xx), the workspace has
already been created but the gate never flips off, and no error is surfaced. Worse, the
button-enable guard is `isLoading = createWorkspace.isPending || completeSetup.isPending`;
once the complete mutation settles into an error state both are `false`, so `canSubmit`
returns `true` again and the now-enabled "Create workspace" button, if clicked, creates a
**second** workspace. This is the failure edge of the otherwise-correct complete-after-create
ordering.
**Fix:** Give the complete mutation an error handler and gate the CTA on success, e.g.:
```tsx
const submit = () => {
  if (!canSubmit) return;
  setError(null);
  createWorkspace.mutate(
    { name, projectRepo, projectBranch: projectBranch.trim() || "main", node: node || null, persistent },
    {
      onSuccess: () =>
        completeSetup.mutate(undefined, {
          // Workspace already exists: surface the failure and DO NOT let the
          // CTA re-create. Retrying setup-complete is idempotent and safe.
          onError: () =>
            setError("Workspace created, but finishing setup failed. Retry."),
        }),
      onError: (err) =>
        setError(err instanceof ApiError ? err.message : GENERIC_ERROR),
    },
  );
};
```
Additionally treat "create already succeeded" as a latch so a second submit retries
*complete* rather than re-POSTing `/workspaces`.

### WR-02: Step status regions are not announced — only the checklist is `aria-live`

**File:** `ui/src/components/SetupWizard.tsx:216-249, 394-435, 564-590` (and `263-264`)
**Issue:** UI-SPEC §"Focus / keyboard / a11y" (line 241) requires *each step's status region*
to be an `aria-live="polite"` `role="status"` block, and the component docstring (lines 18-19)
claims "Each step status is an aria-live='polite' region." In practice the **only** live
region is `Checklist` (lines 263-264), which announces the glyph rows. The actual status
content — the `ErrorStrip` (mapped error message + guidance), the missing-privilege list, and
the `StepHealth` db/compute readout — render in plain `<div>`s with no live-region ancestor.
A screen-reader user gets no announcement when a `setup_auth_failed` strip appears, when the
missing-priv list renders, or when health flips to "unreachable". The status-is-never-color-only
text is present, but it is silent to assistive tech on transition.
**Fix:** Wrap the per-step status output (error strip + missing-priv block + health readout) in
a `role="status" aria-live="polite"` container so transitions are announced. The checklist may
keep its own live region or be downgraded to `aria-hidden` decorative glyphs paired with the
announced status text.

### WR-03: Health step shows red "unreachable" for both rows during the in-flight probe

**File:** `ui/src/components/SetupWizard.tsx:533-577, 592-611`
**Issue:** On mount `result` is `null`, so `HealthRow` computes `ok = result?.db === "ok"` =
`undefined === "ok"` = `false`, rendering a red `--err` dot and the literal text
"unreachable" for both Database and Compute **while the probe is still in flight**. The
UI-SPEC per-step matrix (line 220) prescribes a Loading state (the `StepSpinner`), not a
false-negative "unreachable" readout. On a fast backend this is a brief flash before
auto-advance, but on a slow or degraded control plane it is a misleading state shown to the
operator (it reads as "down" when it is merely "not yet checked").
**Fix:** Distinguish loading from probed. While `isLoading && result === null`, render the
rows in a neutral/checking state (e.g. a muted dot + "checking…" or the `StepSpinner`), and
only paint `--ok`/`--err` once `result !== null`:
```tsx
<HealthRow label="Database" state={result === null ? "checking" : result.db === "ok" ? "ok" : "down"} />
```

### WR-04: No vitest/App-level test proves the gate REPLACES the shell when unconfigured

**File:** `ui/src/App.test.tsx:13` (gap); `ui/tests/e2e/setup-wizard.spec.ts:96-99`
**Issue:** Phase 13's headline criterion is "App renders ONLY `<SetupWizard/>` when
`setupCompletedAt === null`, the normal shell otherwise." `App.test.tsx` never overrides the
default MSW `/setup/state` (which returns a *configured* Burrow) to null, so every App test
exercises only the configured branch. The unconfigured branch (gate replaces Navbar + list +
StatusBar) is asserted **only** in the e2e — and that e2e `test.skip`s its gate-visible
walkthrough whenever the shared DB is already configured (`setup-wizard.spec.ts:96-99`). So in
the entire vitest tier, and in any CI run on a persisted DB, the gate-replaces-shell behavior
is unproven. `SetupWizard.test.tsx` tests the wizard in isolation and never mounts `<App/>`.
**Fix:** Add an App test that mounts `<App/>` with `server.use(http.get("/api/v1/setup/state",
() => HttpResponse.json(envelope({ setupCompletedAt: null }))))` and asserts the `Set up
Burrow` dialog is present AND `queryByRole("main", { name: "Burrow workspace manager" })` is
absent (and the inverse for the configured case).

## Info

### IN-01: Step title font-size deviates from the UI-SPEC (14px vs 16px)

**File:** `ui/src/components/SetupWizard.tsx:725-738`
**Issue:** `StepHeading` renders at `fontSize: "14px"`, but UI-SPEC Typography (line 75) maps
"Display (wizard title / step title)" to **16px**/500, and the function's own JSDoc (line 725)
says "16px display". Only the gate header title (line 819) is 16px; the per-step titles are
14px. Minor visual-contract drift.
**Fix:** Set `fontSize: "16px"` in `StepHeading` to match the spec and the comment, or amend
the spec if 14px is intended for step subheadings.

### IN-02: Template VMID number input accepts non-integers

**File:** `ui/src/components/SetupWizard.tsx:471, 489-496`
**Issue:** The Template VMID field is `type="number"` and submitted as `Number(templateVmid)`.
A browser number input permits `9000.5` or `1e4`, which `Number()` passes through as a float;
the backend `VerifyTemplateBody.template_vmid: int` would 422. `isValid` only checks
non-empty.
**Fix:** Coerce/validate to an integer before submit (e.g. `Number.parseInt(templateVmid, 10)`
plus an `Number.isInteger` guard, or `step="1" min="1"` plus a client check).

### IN-03: No focus trap; relies on App rendering the wizard alone

**File:** `ui/src/components/SetupWizard.tsx:776-792`
**Issue:** The dialog focuses itself on mount and intercepts Escape (no-op) and Enter (submit),
but there is no Tab-wrapping focus trap — the docstring's "focus trapped (the only interactive
surface)" is true only because `App.tsx` renders `<SetupWizard/>` as the sole child (no shell
behind it). The behavior is acceptable as-is, but it is structural, not enforced: any future
change that co-renders content behind the gate would let Tab escape the blocking gate.
**Fix:** Optionally add a real focus trap (wrap Tab/Shift+Tab within the card) so the gate's
blocking guarantee does not depend on the App-level render structure. Low priority.

### IN-04: Re-probe-to-first-failing-step is implemented as always-step-1

**File:** `ui/src/components/SetupWizard.tsx:767-770`
**Issue:** UI-SPEC line 182 describes re-entry as "the re-entry probe lands on the first
failing step," and the review brief expected a "re-probe jump" behavior/test. The
implementation always opens on `useState(1)` (no jump logic), which the spec also explicitly
permits ("an unconfigured Burrow opens directly on step 1"). This is internally consistent —
an unconfigured gate has no prior progress to resume — but the brief's expected re-probe-jump
test does not exist (and correctly is not present in `SetupWizard.test.tsx`). Flagging the
divergence between the brief's expectation and the shipped (simpler) design so it is a
conscious decision, not an omission.
**Fix:** None required if always-step-1 is the accepted design; otherwise implement the
first-failing-step landing and add a covering test. Recommend confirming the design intent.

---

## Structural Findings (fallow)

No structural pre-pass (`<structural_findings>`) was provided with this review.

---

_Reviewed: 2026-06-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
