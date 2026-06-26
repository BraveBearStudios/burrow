# Phase 13: Setup Wizard UI + First-Run Gate - Research

**Researched:** 2026-06-25
**Confidence:** HIGH — codebase claims verified by scout against live files; the design contract is locked in 13-UI-SPEC.md (6/6 verified).

## What must be true (SETUP-04/05/06 + WSX-02 UI half)

(1) When `setupCompletedAt` is unset, the UI presents `SetupWizard.tsx` as a first-run gate before
the workspace list; once set, the wizard never reappears. (2) The wizard's final step creates the
first workspace then marks setup complete, transitioning to the normal view. (3) Re-opening re-probes
state and lands on the first failing step (idempotent, re-enterable, no persisted checkpoint). (4)
`NewWorkspaceModal` exposes a `persistent` checkbox (default unchecked) submitting the flag. CI via
vitest + Playwright over the Fake; real first-workspace-on-real-Proxmox is the Phase 14 (ACC-01) smoke.

## Backend (the setter deferred from Phase 12)

Phase 12 shipped read-only `getSetupState()` (`api/db/sqliteProvider.py:370-382`) + the `settings`
singleton (migration 003). Phase 13 adds:
- `DbProvider.setSetupCompleted()` (ABC `api/db/provider.py` + sqlite impl): `UPDATE settings SET
  setupCompletedAt = <ISO-8601 now> WHERE id = 1`. Idempotent in effect (re-running just re-stamps;
  the endpoint can no-op if already set, returning the existing value).
- `GET /api/v1/setup/state` (in `api/routers/setup.py`): calls `db.getSetupState()`, returns the
  envelope `{ data: { setupCompletedAt }, ... }` for the gate.
- `POST /api/v1/setup/complete`: calls `db.setSetupCompleted()`, returns the envelope. No token, no
  body needed.
Both use the standard `respond(...)` envelope. No new error codes needed (the setter cannot fail on
a valid singleton). Integration tests over the Fake-backed app: state reads null initially, complete
sets it, state then returns the timestamp, complete is idempotent.

## Frontend (the wizard + gate + checkbox)

### Hooks (alongside `ui/src/hooks/useWorkspaces.ts`, same `useQuery`/`useMutation` + `api()` pattern)
- `useSetupState()`: `useQuery({ queryKey: ["setupState"], queryFn: () => api("/setup/state") })`.
  The App reads this; `setupCompletedAt === null` → render the gate.
- `useTestConnection()` / `useVerifyTemplate()`: `useMutation` → POST `/setup/test-connection` /
  `/setup/verify-template` (Phase 12 endpoints). Return ConnectionResult / TemplateResult.
- `useCompleteSetup()`: `useMutation` → POST `/setup/complete`; `onSuccess` invalidates `["setupState"]`
  so the gate re-renders away.
- The create mutation is the existing `useCreateWorkspace()`.

### Gate (App.tsx ~:42-74)
Read `useSetupState()` at the top of `App`. While loading, show the "Checking setup..." state
(UI-SPEC). If `setupCompletedAt === null`, render ONLY `<SetupWizard />` (full-page modal gate,
Escape disabled, focus-trapped). Otherwise render the existing Navbar + workspace layout. On
`useCompleteSetup` success the query invalidation flips the gate off.

### SetupWizard.tsx (new, flat in components/)
- Internal step state (1..4). On mount/open, re-probe in order and jump to the first failing step
  (criterion 3): run test-connection (if creds available) / read health / etc. The simplest correct
  approach: the wizard derives position from live probe results, not stored progress. Each step
  auto-advances on its success.
- Steps per UI-SPEC: (1) token validation form (host/user/token_name/token_value -> test-connection;
  show success or the `missingPrivileges` list; map `setup_auth_failed`/`setup_unreachable`), (2)
  template verify (template_vmid/node -> verify-template; map `setup_template_not_found`), (3) health
  (GET /api/v1/health; show db+compute ok / degrade), (4) create first workspace (reuse the create
  form fields incl. the new persistent checkbox) -> on success POST /setup/complete.
- Uses existing tokens/idioms (Field, modal container, primary `var(--accent)` CTA, StepSpinner gold).
- a11y: `role="dialog"`, `aria-modal`, focus on mount, focus trap, Enter submits the active step,
  Escape does nothing (hard gate), `aria-live` for step status, `prefers-reduced-motion` honored.

### NewWorkspaceModal persistent checkbox
- `const [persistent, setPersistent] = useState(false)`; native checkbox with
  `accent-color: var(--accent)` after the Node selector; copy "Persistent (keep workspace after
  session ends)"; wire `persistent` into the `createWorkspace.mutateAsync({...})` body (the backend
  `WorkspaceCreate.persistent` already accepts it). Reset to false on modal close.

## Pitfalls

- Do NOT persist the gate state to localStorage/Zustand — server `settings` is the source of truth
  (scout: layoutStore is view-state only). Use the TanStack Query `["setupState"]` cache + invalidate.
- Do NOT build a persisted checkpoint/resume machine (criterion 3 explicitly wants stateless re-probe).
- Mark setup complete ONLY AFTER the first workspace create succeeds (criterion 2 ordering) — call
  `/setup/complete` in the create step's `onSuccess`, not before.
- Escape must NOT close the gate (override the NewWorkspaceModal Esc-closes behavior); the gate is a
  hard block until configured.
- Copy the inherited off-grid micro-gaps (14px field gap, hairline borders) verbatim from
  `NewWorkspaceModal.tsx` for surface parity (UI-checker non-blocking note).
- The token field in the wizard form is sensitive — it is sent to test-connection (Phase 12 redacts
  server-side); do NOT log it client-side or store it; it is transient form state only.

## Validation Architecture

**Framework:** vitest (jsdom + MSW) for components/hooks; Playwright (Fake-backed 3-process
webServer) for e2e; pytest for the two new backend endpoints + the setter.

**Wave 0 / key tests:**
- Backend: `GET /setup/state` returns null then the timestamp after `POST /setup/complete`;
  `setSetupCompleted` idempotent; over the Fake-backed app.
- vitest: `SetupWizard.test.tsx` — gate shows when setupCompletedAt null; step success auto-advances;
  a failing step shows the mapped error + retry; re-probe jumps to first failing step; complete fires
  after create. Mock the hooks/MSW.
- vitest: `NewWorkspaceModal.test.tsx` — checking persistent → request body `persistent: true`;
  default false.
- Playwright e2e `tests/e2e/setup-wizard.spec.ts` — unconfigured app shows the gate, walk the steps
  over the Fake, complete, gate vanishes and the workspace list shows; a configured app skips the gate.

**Manual-only / deferred:** real first-workspace-on-real-Proxmox + real wizard walkthrough → Phase 14
(ACC-01/02).

**Sampling:** `cd ui && npm run test` after each UI change; `cd api && uv run pytest tests/integration -k setup -q`
after backend; `cd ui && npm run test:e2e -- setup-wizard` before verification. biome + tsc clean.

**Security (ASVS L1):** no new secret-at-rest (the token is transient form state sent to the Phase 12
redacted endpoint; never stored/logged client-side). The setter writes only a timestamp. v1 LAN-only
no-auth (the gate is a UX gate, not an authz boundary). No new HIGH threat.

## RESEARCH COMPLETE
