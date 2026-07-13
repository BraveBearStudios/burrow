<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 16: Land Credential Backend & Reconcile Release Train - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto-generated (ops/release phase — the substantive work landed out-of-band; discuss skipped)

<domain>
## Phase Boundary

The ADR-0015 credential-store backend (PR #3, migration `004`) lands on a green
`main`, release-please is reconciled forward from the stale 1.2.0 to target
v1.4.0, the secret-at-rest docs are reconciled to reference ADR-0015 (no longer
asserting "no secret-at-rest"), and the merged local branch is pruned. Pure
release/ops + docs — no application code originates in this phase.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — this is a release/ops
phase, not a feature phase. The merge, release-please reconciliation, and green
main run all happened out-of-band on 2026-07-13 (squash-merge `f9b1868`); this
phase records that completion with evidence and closes the residual docs +
branch-prune items.

</decisions>

<code_context>
## Existing Code Insights

The credential backend (ADR-0015) is fully present on `main` as of `f9b1868`:
migration `004`, the Fernet `SecretBox` + `BURROW_SECRET_KEY`, the
`CredentialResolver` (DB-first git credential resolution), the local admin gate,
apply-token-without-restart, and the `/setup` credential endpoints. Phase 18
binds the frontend to that surface.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — the merge/reconcile were performed via GitHub before
this session. Docs reconciliation (CRED-01) covers ROADMAP/STATE/tech-spec plus
forward "Superseded-by ADR-0015" pointers on the historical ADR-0011/ADR-0012
secret-at-rest assertions.

</specifics>

<deferred>
## Deferred Ideas

None — the remote `feat/gui-managed-secrets` branch prune is a residual cleanup
item, not a deferred idea (see VERIFICATION criterion 4).

</deferred>
