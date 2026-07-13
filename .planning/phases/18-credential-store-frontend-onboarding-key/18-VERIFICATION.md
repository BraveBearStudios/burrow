<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: passed
phase: 18
verified: 2026-07-13
---

# Phase 18: Credential Store Frontend & Onboarding Key - Verification

## Must-Haves

1. **Admin secret + X-Burrow-Admin gate (CRED-02)** - PASSED. Setup wizard sets a
   local admin secret (`POST /setup/admin-secret`); the credential surface is gated
   by an `X-Burrow-Admin` header sent from an in-memory Zustand store (never
   persisted). A `admin_unauthorized` 401 clears the store and re-prompts.

2. **Encrypted credentials in the wizard (CRED-03)** - PASSED. The wizard credentials
   step submits the Proxmox token + optional GitHub PAT to `POST /setup/credentials`,
   which validates then stores them Fernet-encrypted at rest — replacing the v1.3
   validate-in-memory-only step.

3. **Admin-gated Credentials/Settings screen with rotation (CRED-04)** - PASSED. The
   `CredentialsScreen` (Navbar gear) prompts for the admin secret, shows status
   (set + last4 + updatedAt), supports rotation by re-submit, and never returns or
   renders a secret value.

4. **Audit read endpoint + panel (CRED-05)** - PASSED. `GET /setup/audit`
   (admin-gated, bounded) + `DbProvider.listAudit`; a read-only `AuditPanel` renders
   the append-only trail newest-first.

5. **BURROW_SECRET_KEY onboarding + boot resilience (CRED-06)** - PASSED.
   `40-control-plane.sh` auto-generates the Fernet key into `.env` on first run when
   empty (idempotent, hygienic, provisioning never blocked); key-loss recovery
   documented; a missing/undecryptable key never crashes boot (lifespan +
   CredentialResolver fall back to `.env`, locked by an existing test).

6. **Extended sentinel leak test (CRED-07)** - PASSED. A sentinel POSTed through
   `/setup/credentials` appears in no DB cell, no API envelope (save/status/audit),
   and no log line; only the Fernet ciphertext (decrypts back to the sentinel) + a
   4-char last4 persist.

## Evidence

- Backend: `ruff` + `mypy --strict` clean; `uv run pytest -q` → **299 passed**;
  `reuse lint` → 481/481; `bash -n 40-control-plane.sh` clean.
- Frontend: `tsc --noEmit` clean; `biome ci .` clean (59 files); `vitest run` →
  **17 files / 136 tests passed**; admin-secret in-memory-only asserted in tests.
- Contract alignment: frontend mirrors the real backend `updatedAt` key +
  `admin_unauthorized` code (verified against source, not guessed).
- Commits: 3 backend (`feat(18)`/`test(18)`) + 3 frontend (`feat(18)`).

## Realized-at-downstream (by design, NOT gaps)

- The live den01 smoke — migration `004` applies, a GUI-set token applies without a
  restart + survives one — is the Phase 22 ACC-05 human UAT, not a Phase 18 gate.

**Verdict: PASSED** — all six CRED requirements delivered and verified over the api
(299) + ui (136) suites; the curl-only backend is now a novice-usable GUI.
