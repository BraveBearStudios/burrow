<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 16: Land Credential Backend & Reconcile Release Train - Summary

**Completed:** 2026-07-13
**Requirement:** CRED-01

## What happened

The substantive work landed out-of-band on 2026-07-13 (before this autonomous
session), and this phase records it with evidence + closes the residual docs and
branch-prune items.

1. **PR #3 merged onto green main.** The ADR-0015 credential-store backend branch
   `feat/gui-managed-secrets` (migration `004` + Fernet SecretBox + admin gate +
   CredentialResolver + `/setup` credential endpoints) was squash-merged to `main`
   as commit `f9b1868`. The post-merge `main` push ran CI green: run
   `29281423984` (`ci`) SUCCESS, run `29281423865` (`release-please`) SUCCESS.

2. **release-please reconciled forward to v1.4.0.** With the Phase 15 RELX-03
   `oss`-ruleset exclusion applied, release-please maintains its branch cleanly;
   the open release PR **#1** is titled `chore(main): release 1.4.0` (the
   credential `feat` drove the minor bump off the stale 1.2.0). The Phase 15
   semver tag ownership (`v[0-9]+.[0-9]+.[0-9]+` publish trigger) holds through
   the merge — hand-pushed milestone tags stay inert.

3. **Secret-at-rest docs reconciled to ADR-0015 (CRED-01).** The
   ROADMAP/STATE/tech-spec "validate-in-memory, `.env`-only, no secret-at-rest"
   assertions were corrected to the Fernet-encrypted-at-rest posture (commit
   `3e36a00`, in the squash). This session added forward **"Superseded (v1.4,
   ADR-0015)"** pointers to the two historical ADRs that still recorded the old
   posture — ADR-0011 (setup-state store) and ADR-0012 (compute-provider setup
   caps) — leaving their original decisions intact per ADR immutability.

4. **Merged local branch pruned.** `feat/gui-managed-secrets` deleted locally
   (squash-merged, tree-identical to `main`). Work continues on a fresh
   `feat/v1.4-harden` branch off green `main`. The **remote** branch prune is a
   residual cleanup item (see VERIFICATION criterion 4).

## Evidence

- `origin/main` HEAD `f9b1868` — "feat: GUI credential store + real-infra deploy +
  v1.4 pipeline unblock (ADR-0015)" (2026-07-13 16:11).
- `git diff origin/main <branch-HEAD>` empty → branch fully merged, zero residual.
- Green main CI: `ci` run `29281423984` SUCCESS, `release-please` run
  `29281423865` SUCCESS.
- Release PR #1 `chore(main): release 1.4.0` OPEN.
- Docs: `docs(16)` commit `3e36a00` + this session's ADR-0011/0012 superseded notes.
