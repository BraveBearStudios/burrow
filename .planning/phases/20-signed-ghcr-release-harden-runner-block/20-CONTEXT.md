<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 20: Signed GHCR Release & Harden-Runner Block - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning
**Mode:** Auto (autonomous run). CD / infra phase — partly operator-bound.

<domain>
## Phase Boundary

Drive the first GREEN signed + attested `release.yml` run to GHCR, verify the
published images (`cosign verify` + `gh attestation verify` against the `@sha256`
digest, completing ACC-03), and flip harden-runner egress `audit -> block` from the
green run's discovered allowlist (ACC-02 item 14). ACC-06.
</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
CD/ops phase. The signed-release cut is CI/runner-provable; the independent
verify + the harden-runner block-flip require operator registry auth, `cosign`,
and the run's Step-Security egress insights, so they are operator-bound (they also
ride into Phase 22 ACC-05). Depends on Phase 18 (v1.4 GUI must be in the release)
and Phase 15 (green signed-release path).
</decisions>

<code_context>
## Existing Code Insights
- `release.yml` — the sign/attest/publish supply chain (verified sound by the
  Phase 20 pre-release security audit: 4 perms, keyless cosign by digest, SLSA
  attest, dual SBOM auth, lowercased owner, SHA-pinned).
- `release-please.yml` — creates the tag via `GITHUB_TOKEN` (the trigger-gap root
  cause; see ADR-0019).
</code_context>

<specifics>
## Specific Ideas
First-signed-release traps (carried): verify by digest not tag; exactly 4 publish
perms; `gh attestation verify` can exit-0-on-failure so assert on output; pre-seed
Fulcio/Rekor/TUF in the block allowlist.
</specifics>

<deferred>
## Deferred Ideas
The live homelab re-verify against a homelab-pulled image is Phase 22 ACC-05.
</deferred>
