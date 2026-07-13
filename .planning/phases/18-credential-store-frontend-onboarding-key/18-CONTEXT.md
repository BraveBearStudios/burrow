<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 18: Credential Store Frontend & Onboarding Key - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto (autonomous run). Frontend phase — the UI design contract is baked
in here (extends the existing SetupWizard + four-theme token system; no greenfield
design), so the standalone UI-SPEC step is folded into these decisions.

<domain>
## Phase Boundary

Turn the curl-only ADR-0015 credential backend into a novice-usable GUI: an
admin-secret + credentials step in the setup wizard, an admin-gated post-setup
Credentials/Settings screen (status + rotation), a read-only audit view, the
`X-Burrow-Admin` client header, `BURROW_SECRET_KEY` auto-generation in onboarding,
and an extended sentinel leak test. Ships the milestone's ship blocker (CRED-02..07).
</domain>

<decisions>
## Implementation Decisions

### Admin gate + header (CRED-02)
- The admin secret is held in a small in-memory Zustand store
  (`useAdminStore`) for the session only — NEVER localStorage/sessionStorage,
  never the query cache. Reload re-prompts. The `api()` client gains no global
  coupling; admin-gated hooks pass `{ headers: { "X-Burrow-Admin": secret } }`
  explicitly via the existing `RequestInit` passthrough.
- A 401 `admin_auth` from any admin-gated call clears the store and surfaces a
  re-enter prompt (no oracle on which of missing/wrong).

### Credentials in the wizard (CRED-03)
- The wizard gains two steps after template/health: (a) set admin secret
  (`POST /setup/admin-secret`, first-run unauthenticated), (b) enter Proxmox token
  + optional GitHub PAT (`POST /setup/credentials`, admin-gated). This REPLACES the
  v1.3 "validate in memory only, never store" test-connection-only flow — the token
  is now validated-then-stored (the backend validates before persist + applies
  without restart). Both inputs are password fields; values are transient React
  state, never cached/logged.

### Settings/Credentials screen + rotation (CRED-04)
- A new admin-gated post-setup screen (route/panel reachable from the Navbar)
  shows credential status: which credentials are set, their last4, and
  `credentialsUpdatedAt`. Rotation = re-submitting `POST /setup/credentials` with a
  new value. It NEVER shows a secret value (the backend never returns one).
- Admin-gate UX: if the admin secret is not in the store, the screen prompts for
  it before any status/audit fetch.

### Audit view (CRED-05)
- New backend read endpoint `GET /setup/audit` (admin-gated, `Depends(require_admin)`)
  returns recent `audit_log` rows (id, action, target, outcome, sourceIp, detail,
  createdAt) newest-first, bounded (default 100). New `DbProvider.listAudit(limit)`
  ABC method + SQLite impl (SELECT ... ORDER BY createdAt DESC, rowid DESC LIMIT ?)
  + Postgres `NotImplementedError` stub for ABC parity. A read-only GUI panel on the
  Credentials screen renders the trail (action / target / outcome / when / source).

### Onboarding key (CRED-06)
- `40-control-plane.sh` .env assembly: after copying `.env.example` → `.env`, if the
  `BURROW_SECRET_KEY=` line is empty, generate a Fernet key
  (`python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
  and write it in (umask 077, gitignore-guarded like the existing secret handling).
  Add a documented key-loss recovery note (losing the key = stored ciphertext is
  unrecoverable; re-enter credentials via the GUI — the resolver already falls back
  to `.env`, so a lost/rotated key never crashes the control plane or worker boot).
- Verify the existing startup + `CredentialResolver` fallback already means a
  missing/undecryptable key never crashes boot; add a regression test if a gap.

### Sentinel leak test (CRED-07)
- Extend the setup-token leak test through `POST /setup/credentials`: a sentinel
  credential must appear in NO DB cell (assert over every `settings`/`audit_log`
  cell), NO API envelope (save + status + audit responses), and NO log line — only
  the Fernet ciphertext (a BLOB, not the plaintext) + the 4-char last4 persist.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/routers/setup.py` — `require_admin`, `_audit`, `_secret_box`, the credentials
  save/status endpoints; `GET /setup/audit` slots in beside `GET /setup/credentials`.
- `api/db/provider.py` — `writeAudit`, `getCredentialStatus`, `getAdminSecretHash`,
  etc.; `listAudit` is the one missing read method.
- `api/db/migrations/004_credentials_and_audit.sql` — `audit_log` columns already
  defined; no new migration needed for the read.
- `ui/src/api/client.ts` — `api<T>(path, init)` merges `init.headers`; header
  injection needs no client change.
- `ui/src/hooks/useSetup.ts`, `ui/src/types/setup.ts`, `SetupWizard.tsx` — the
  wizard/hook pattern to extend; `NewWorkspaceModal.tsx` accent-color input style.
- The app already uses Zustand (workspace store) + TanStack Query + the four-theme
  token sheet (`--accent`, mono for secrets) — reuse verbatim.

### Established Patterns
- CamelModel snake↔camel at the boundary; envelope `respond(...)`.
- SecretStr request bodies + leak-free 422 handler; audit is best-effort.
- vitest + MSW for hooks/components; Playwright for gate e2e.

### Integration Points
- Backend: `GET /setup/audit` (setup.py), `DbProvider.listAudit` (provider.py +
  sqliteProvider.py + postgresProvider.py stub).
- Frontend: `useAdminStore` (new Zustand), `useSetup.ts` (+ hooks), `types/setup.ts`
  (+ types), `SetupWizard.tsx` (+2 steps), new `CredentialsScreen.tsx` + `AuditPanel`,
  `Navbar.tsx` (entry point).
- Onboarding: `cc-worker-config/lxc/host-prime/40-control-plane.sh`, `.env.example`.
</code_context>

<specifics>
## Specific Ideas

Admin secret in memory only (Zustand, no persistence). Token inputs are password
fields with the green `--accent`, not browser-blue. Audit panel is read-only, mono,
newest-first. Match the SetupWizard a11y (role=dialog, focus-on-mount) for the new steps.
</specifics>

<deferred>
## Deferred Ideas

Live den01 apply of the GUI credential store (migration 004 applies, a GUI-set token
applies without restart + survives one) is the Phase 22 ACC-05 smoke — not here.
</deferred>
