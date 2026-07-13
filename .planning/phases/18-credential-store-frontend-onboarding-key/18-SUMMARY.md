<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 18: Credential Store Frontend & Onboarding Key - Summary

**Completed:** 2026-07-13
**Requirements:** CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CRED-07

The milestone ship blocker: the curl-only ADR-0015 credential backend now has its
full operator-facing GUI + a novice-safe onboarding key.

## Backend (Plan 01)

- **CRED-05** — `GET /api/v1/setup/audit` (admin-gated, `limit` clamped 1..500,
  default 100) returns `{entries: [...]}` newest-first over the append-only
  `audit_log`. New `DbProvider.listAudit(limit)` ABC + SQLite impl (`ORDER BY
  createdAt DESC, rowid DESC`) + Postgres `NotImplementedError` stub for parity.
- **CRED-06** — `40-control-plane.sh` auto-generates a Fernet `BURROW_SECRET_KEY`
  into `.env` on first run when empty (idempotent, umask 077, gitignore-guarded,
  written via a shell builtin so the key is never a process CLI arg or logged;
  tolerant of a missing python3/cryptography — logs a warning and leaves the store
  disabled rather than aborting provisioning). Key-loss recovery documented in the
  script + a new ADR-0015 operational note. Boot resilience was already covered
  (main.py lifespan + CredentialResolver swallow a missing/undecryptable key and
  fall back to `.env`; locked by the existing `test_credential_resolver` test).
- **CRED-07** — extended the credential-leak integration test: a sentinel token
  POSTed to `/setup/credentials` appears in NO `settings`/`audit_log` cell, NO API
  envelope (save / status / audit), and NO log line; the positive contract is
  asserted — the stored ciphertext decrypts back to the sentinel and last4 matches.

## Frontend (Plan 02)

- **CRED-02** — in-memory `useAdminStore` (Zustand, no persist) holds the admin
  secret for the session; admin-gated hooks send it as `X-Burrow-Admin`. A
  `admin_unauthorized` 401 clears the store and re-prompts (no oracle).
- **CRED-03** — the setup wizard gains an admin-secret step (with a confirm field
  to prevent typo lockout) + a credentials step (Proxmox token required, GitHub PAT
  optional) that stores encrypted via `POST /setup/credentials`, replacing the v1.3
  validate-in-memory-only step. Password inputs, green `--accent`, transient state.
- **CRED-04** — a new admin-gated `CredentialsScreen` (opened from a Navbar gear)
  prompts for the admin secret, shows status (set + last4 + `updatedAt`), supports
  rotation (re-submit), and never renders a secret value.
- **CRED-05 UI** — an embedded read-only `AuditPanel` renders the trail newest-first.

## Contract corrections found during build

- `getCredentialStatus` returns `updatedAt` (not the plan's guessed
  `credentialsUpdatedAt`); the frontend mirrors the real key.
- The admin-auth error code is `admin_unauthorized`.

## Verification evidence

- Backend: `ruff` + `mypy --strict` clean; `uv run pytest -q` → **299 passed**
  (incl. the audit endpoint + extended leak test); `reuse lint` 481/481.
- Frontend: `tsc --noEmit` clean; `biome ci .` clean (59 files); `vitest run` →
  **17 files, 136 tests passed** (incl. CredentialsScreen + 2 new wizard tests).
- Admin secret proven in-memory only (localStorage sweep asserted in two tests).
- `bash -n 40-control-plane.sh` clean.

## Commits

`feat(18)` audit endpoint/listAudit · `feat(18)` BURROW_SECRET_KEY onboarding ·
`test(18)` extended leak · `feat(18)` admin store+hooks · `feat(18)` wizard steps ·
`feat(18)` Credentials screen + audit panel.
