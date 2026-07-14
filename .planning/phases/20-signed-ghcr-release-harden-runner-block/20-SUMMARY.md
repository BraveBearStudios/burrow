<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 20: Signed GHCR Release & Harden-Runner Block - Summary

**Date:** 2026-07-14
**Requirement:** ACC-06 · **ADR:** ADR-0019

## Pre-release security audit (gate before the cut)

A multi-agent audit (code scanning, Dependabot alerts + config, secret scanning,
supply-chain) returned **go-with-caveats, no blockers**. Remediated before the cut:
- Upgraded base pip `>=26.1.2` in `Dockerfile.api` — cleared the one FIXABLE Trivy
  HIGH (CVE-2026-8643) that `ignore-unfixed` would not skip.
- Dismissed CodeQL #280 (benign ABC `...` note) — SEC-03 first-run baseline recorded.
- Deferred to operator (non-blocking): enable secret scanning + push protection;
  dismiss the 20 unfixable Trivy OS-package CVEs as accepted baseline.

## The release-trigger gap (the real ACC-06 finding)

Merging release PR #1 tagged `v1.4.0`, but `release.yml` **never fired**:
release-please creates the tag with `GITHUB_TOKEN`, and GitHub suppresses workflow
triggers for `GITHUB_TOKEN`-created events. The repo's immutable-releases policy +
a tag creation-restriction then blocked recovery by recreating the release or
re-pushing the tag, so **`v1.4.0` was consumed** with no signed artifacts. (Root
cause + decision: ADR-0019.)

## Recovery + the signed release (ACC-06 core: DONE)

Added a **`workflow_dispatch` escape hatch** to `release.yml` (version + ref
inputs, shared version resolver; PR #10, which also fixed main's reuse-red on the
release-please `CHANGELOG.md` via `REUSE.toml`). Dispatched `version=1.4.1`,
`ref=main` -> run **`29355954285`**, both images GREEN through every step:
build+push by digest, SBOM (SPDX + CycloneDX), **cosign keyless sign**, **SLSA
build-provenance attest**. `ghcr.io/bravebearstudios/burrow-{api,ui}:1.4.1` are
published, signed, and attested. The first green signed release exists.

## Operator-pending (carried into Phase 22 ACC-05)

- **Independent verify** — `cosign verify` + `gh attestation verify` against the
  published digests. Blocked here: the session token lacks `read:packages`, there
  is no local `cosign`, and the GHCR packages default to private. Commands handed
  to the operator; also re-verified live in Phase 22.
- **Harden-runner egress `audit -> block`** — needs run `29355954285`'s
  Step-Security insights (the real allowlist includes base-image pulls + PyPI + npm
  beyond the cosign/OIDC/GHCR set), which are not gh-readable. NOT drafted with a
  guessed allowlist (would break future builds). Operator reads the insights; the
  flip lands as a reviewed PR.

## Artifacts

- ADR-0019 (release publish trigger). `release.yml` workflow_dispatch hatch (PR #10).
- `Dockerfile.api` pip bump; `REUSE.toml` CHANGELOG coverage.
- Release run `29355954285` (v1.4.1, signed + attested, both images).
