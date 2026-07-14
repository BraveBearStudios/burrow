<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: human_needed
phase: 20
verified: 2026-07-14
---

# Phase 20: Signed GHCR Release & Harden-Runner Block - Verification

**Goal:** First GREEN signed + attested `release.yml` run to GHCR, `cosign verify` +
`gh attestation verify` against the published digest (ACC-03), and harden-runner
egress `audit -> block` (ACC-02 item 14). ACC-06.

## Must-Haves

1. **First GREEN signed + attested release to GHCR** - PASSED. Run `29355954285`
   (dispatched `v1.4.1`, `ref=main`) succeeded for BOTH images with every step green:
   build+push by digest, SBOM (SPDX + CycloneDX), cosign keyless sign, SLSA
   build-provenance attest. `ghcr.io/bravebearstudios/burrow-{api,ui}:1.4.1` are
   published, signed, and attested. Delivered via the ADR-0019 workflow_dispatch
   escape hatch after the `GITHUB_TOKEN` tag-trigger gap consumed `v1.4.0`.

2. **Independent verify (cosign + gh attestation) against the digest (ACC-03)** -
   HUMAN_NEEDED. Blocked in-session: the token lacks `read:packages`, no local
   `cosign`, and the GHCR packages default to private. The sign + attest STEPS ran
   green (keyless signing cannot succeed without actually signing), so the artifacts
   are signed; the independent third-party re-verify is operator-run and is also
   exercised live in Phase 22 (ACC-05). Commands provided.

3. **Harden-runner egress audit -> block (ACC-02 item 14)** - HUMAN_NEEDED. Requires
   run `29355954285`'s Step-Security egress insights to compose the real allowlist
   (base-image pulls + PyPI + npm beyond the cosign/OIDC/GHCR set). Not gh-readable
   in-session; deliberately NOT flipped with a guessed allowlist (would break future
   builds). Operator reads the insights; the flip lands as a reviewed PR.

## Evidence

- Pre-release security audit: go-with-caveats, no blockers; pip HIGH patched; CodeQL
  baseline dismissed.
- Release run `29355954285`: both `Publish + sign burrow-{api,ui}` jobs success; the
  `Sign image (cosign keyless)` + `Attest build provenance (SLSA)` steps success.
- ADR-0019 records the trigger-gap root cause + the workflow_dispatch decision.

## Verdict

**Signed release DELIVERED (must-have 1 PASSED)** — the milestone's ACC-06 core
(a real, green, signed + attested release exists) is achieved. Must-haves 2-3 are
operator/infra follow-ups (independent verify + egress block-flip) that overlap
Phase 22 ACC-05; status is `human_needed` until the operator completes them.
