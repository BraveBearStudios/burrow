# Phase 13: Setup Wizard UI + First-Run Gate - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

An unconfigured Burrow presents a guided, re-enterable setup wizard as a first-run gate that walks
the operator from token validation through template verification and health to creating their first
workspace; once configured the wizard never reappears, and create gains the opt-in persistent
toggle. Requirements: SETUP-04, SETUP-05, SETUP-06 (plus the UI half of WSX-02). CI-provable via
vitest + Playwright over the Fake provider; the real first-workspace-on-real-Proxmox is the Phase 14
(ACC-01) smoke.

This phase also lands the small backend SETTER deferred from Phase 12: `setSetupCompleted` on the
DbProvider seam + `GET /api/v1/setup/state` (read for the gate) + `POST /api/v1/setup/complete`
(idempotent setter). Out of scope: any new compute capability (Phase 12), the persistence data model
(Phase 10 — `persistent` is already accepted by the create API), real-infra acceptance (Phase 14).
</domain>

<decisions>
## Implementation Decisions

### Wizard structure & UX
- `SetupWizard.tsx` (flat in `ui/src/components/`) is a **full-page modal gate** rendered by
  `App.tsx` (wrapping the Navbar + workspace area) when `setupState.setupCompletedAt === null`. It
  blocks the app until configured; matches the existing `NewWorkspaceModal` modal pattern + the
  token-themed visual language (Tailwind v4 CSS custom properties in `index.css`).
- Four ordered steps that **auto-advance** on success: (1) token validation (POST
  `/setup/test-connection`, host+token form, shows success or the missing-privilege list), (2)
  template verify (POST `/setup/verify-template`, template_vmid+node), (3) health
  (GET `/api/v1/health`, confirm db+compute ok / degrade-not-500), (4) create first workspace
  (reuse the create flow / `NewWorkspaceModal` fields).
- Re-entry is idempotent with NO persisted checkpoint machine: on open, the wizard re-probes state
  in order and **jumps to the first failing step** (skips passing steps); when all pass it closes.
  Criterion 3.
- Error display: on a failing step show the specific error (missing-priv list, `setup_template_not_found`,
  `setup_unreachable`, `setup_auth_failed`) and let the operator re-enter config and **retry inline**
  (no persisted state — the operator re-enters on the UI).

### Integration & backend setter
- New backend: `DbProvider.setSetupCompleted()` (ABC + sqlite impl — `UPDATE settings SET
  setupCompletedAt = <ISO now> WHERE id = 1`); `GET /api/v1/setup/state` (calls `getSetupState`,
  envelope); `POST /api/v1/setup/complete` (calls `setSetupCompleted`, idempotent — a no-op /
  same-result if already set), in the existing `api/routers/setup.py`. Both endpoints use the
  standard data/meta/error envelope.
- setup is marked complete **AFTER the first-workspace create succeeds** (the wizard's final step),
  i.e. create workspace → on success `POST /setup/complete` → the gate re-renders away to the
  workspace list. Criterion 2 ordering.
- The gate's state lives in TanStack Query (`useSetupState`, queryKey `["setupState"]`, refetch on
  App mount), NOT Zustand or localStorage — the server `settings` row is the source of truth.
- New query/mutation hooks alongside `useWorkspaces.ts`: `useSetupState` (query), `useTestConnection`
  / `useVerifyTemplate` / `useCompleteSetup` (mutations), all through the `api()` client
  (envelope-unwrapping at `ui/src/api/client.ts`).

### Persistent checkbox (WSX-02 UI half)
- `NewWorkspaceModal` gains a `persistent` checkbox, default UNCHECKED (= ephemeral), placed after
  the Node selector. Copy: "Persistent (keep workspace after session ends)". A
  `const [persistent, setPersistent] = useState(false)` wires `persistent` into the
  `createWorkspace.mutateAsync(...)` body. The backend already accepts `persistent` (Phase 10) — no
  backend change for the checkbox.

### Claude's Discretion
- Exact step component decomposition (one SetupWizard with internal step state vs sub-components),
  the precise re-probe sequencing implementation, and the visual micro-layout — at the implementer's
  discretion within the UI-SPEC produced next.
- Whether the wizard's step-4 reuses `NewWorkspaceModal` directly or a shared create-form extract.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui/src/App.tsx:42-74` — root shell (theme, isModalOpen, layout); the first-run gate wraps the
  Navbar + middle row here, conditioned on `useSetupState()`.
- `ui/src/components/NewWorkspaceModal.tsx:175-590` — modal pattern, `<Field>` (137-173), submit
  `runSaga()` (229-269) calling `createWorkspace.mutateAsync` (238-245); add the persistent checkbox
  after the Node selector (412-433) and wire into the body.
- `ui/src/api/client.ts:26-36` — `api<T>(path, init)` envelope unwrap + `ApiError`.
- `ui/src/hooks/useWorkspaces.ts:22-51` — `useQuery`/`useMutation` patterns + `invalidateQueries`;
  model the new setup hooks on these.
- `ui/src/main.tsx:4-23` — QueryClient + provider root.
- `ui/src/store/layoutStore.ts:108-169` — Zustand view-state ONLY (never status/setup).
- `ui/src/index.css:32-89` — design tokens (`--color-*`, `--font-*`, `--radius-*`) + 4 themes
  (`[data-theme=dark|light|warm|ocean]`); inline SVG icons (PLAT-05 no icon fonts).
- `ui/vitest.config.ts:9-25` — jsdom + MSW; `ui/src/components/NewWorkspaceModal.test.tsx:28-60` —
  QueryClientProvider + MSW render pattern.
- `ui/playwright.config.ts:72-86` — 3-process webServer (stub ttyd + FastAPI/Fake + vite preview);
  `ui/tests/e2e/stop-start.spec.ts:30-60` — serial mode + per-test cleanup pattern.
- `api/db/provider.py:101-109` — `getSetupState` ABC (setter deferred); `api/db/sqliteProvider.py:370-382`
  getSetupState impl; `api/routers/setup.py:65-91` — test-connection/verify-template (state endpoints to add).
- `api/models/workspace.py:35-48` — `WorkspaceCreate.persistent: bool = False` already accepted.

### Established Patterns
- `/api/v1` + envelope; TanStack Query for server state; Zustand for view-state only; Tailwind v4
  CSS-first tokens; biome (tabs, double quotes, organize imports); SPDX two-line TS header; camelCase
  vars / PascalCase components; inline SVG icons.
- vitest (jsdom + MSW) for components; Playwright (Fake-backed 3-process harness) for e2e.

### Integration Points
- `api/db/provider.py` + `sqliteProvider.py` — add `setSetupCompleted()`.
- `api/routers/setup.py` — add `GET /setup/state` + `POST /setup/complete`.
- `ui/src/components/SetupWizard.tsx` (NEW) + `App.tsx` (gate).
- `ui/src/hooks/` — `useSetupState` + `useCompleteSetup` (+ reuse test-connection/verify-template mutations).
- `ui/src/components/NewWorkspaceModal.tsx` — persistent checkbox.
- Tests: `SetupWizard.test.tsx`, a `NewWorkspaceModal.test.tsx` persistent case, `tests/e2e/setup-wizard.spec.ts`,
  and api integration for the two new endpoints + the setter.
</code_context>

<specifics>
## Specific Ideas

- The gate is a hard first-run block: an unconfigured Burrow shows ONLY the wizard; a configured one
  never shows it again (the `setupCompletedAt` row flips the gate).
- Re-enterable + idempotent + no-persisted-checkpoint is the explicit design (criterion 3): the
  wizard derives its position by re-probing live state, not by storing progress.
- The persistent checkbox completes WSX-02 end-to-end (Phase 10 backend + this UI).
</specifics>

<deferred>
## Deferred Ideas

- Real first-workspace-on-real-Proxmox + real wizard walkthrough — Phase 14 (ACC-01/02).
- Any setup-config persistence beyond the operator-managed `.env` (token never stored — Phase 12 gate).
- Multi-step persisted checkpoint / resume machine — explicitly rejected (criterion 3 wants stateless re-probe).
</deferred>
