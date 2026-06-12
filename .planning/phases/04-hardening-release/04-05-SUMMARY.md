<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
plan: 05
subsystem: infra
tags: [github-actions, supply-chain, sbom, syft, cosign, sigstore, slsa, provenance, ghcr, release, ci]

# Dependency graph
requires:
  - phase: 04-hardening-release
    plan: 04
    provides: "Dockerfile.api + Dockerfile.ui (the images this release path builds/publishes) + the ci.yml SHA-pin + per-job-permission convention"
  - phase: 00-foundations
    provides: ".github/workflows/ci.yml — SHA-pinned actions (checkout/setup-buildx/build-push) reused here + the contents:read default"
provides:
  - ".github/workflows/release.yml — release supply-chain: build+push GHCR by digest -> syft SBOM (SPDX+CycloneDX) -> cosign keyless -> SLSA build-provenance, all by digest"
affects: [deployment, ghcr-publish, release-runbook]

# Tech tracking
tech-stack:
  added:
    - "docker/login-action@5e57cd1 (v3.6.0) — GHCR auth via GITHUB_TOKEN"
    - "docker/metadata-action@318604b (v5.9.0) — §2.4 tags + OCI labels"
    - "anchore/sbom-action@d8a2c01 (v0.20.7) — syft SBOM, run twice (SPDX + CycloneDX)"
    - "sigstore/cosign-installer@d7543c9 (v3.10.0) — cosign for keyless signing"
    - "actions/attest-build-provenance@977bb37 (v3.0.0) — SLSA build-provenance attestation"
  reused-from-ci:
    - "actions/checkout@34e1148 (v4.3.1)"
    - "docker/setup-buildx-action@d7f5e7f (v4.1.0)"
    - "docker/build-push-action@f9f3042 (v7.2.0)"
  patterns:
    - "Sign + attest BY DIGEST (steps.build.outputs.digest), never a floating tag (tamper-resistant binding)"
    - "Dual-format SBOM = two anchore/sbom-action runs (one invocation emits one format)"
    - "cosign keyless: no --key, ephemeral OIDC identity (Fulcio cert in Rekor) — no long-lived key"
    - "Least-privilege per-job permissions: EXACTLY the 4 scopes keyless+provenance+GHCR-push need"

key-files:
  created:
    - ".github/workflows/release.yml"
  modified: []

key-decisions:
  - "Resolved REAL commit SHAs for all five new actions via the GitHub git/refs API (same certifi-CA approach 04-04 used) — every action SHA-pinned, NO PIN_AT_WRITE placeholders remain"
  - "GHCR target is ghcr.io/${{ github.repository_owner }}/<image> — no hardcoded org, no PAT; auth is the run's built-in GITHUB_TOKEN scoped by packages:write"
  - "publish-job permissions are EXACTLY contents:read + packages:write + id-token:write + attestations:write; workflow default stays contents:read (Pitfall 7)"
  - "SBOM/cosign/attest all target the pushed image @${{ steps.build.outputs.digest }}, never a tag (T-04-05C)"
  - "metadata-action emits the §2.4 release tags (X.Y.Z, X.Y, latest-on-tag, sha-<short>); latest is gated to refs/tags/v*"
  - "harden-runner intentionally NOT added (deferred per CONTEXT — release-polish, out of scope)"

patterns-established:
  - "Release supply-chain workflow split from ci.yml: ci builds+scans on PR without pushing; release.yml owns SBOM/sign/provenance/GHCR-publish on v* tags only (fork PRs never see publish creds)"
  - "Self-contained verification runbook in the workflow trailer (cosign verify + gh attestation verify against the published digest)"

requirements-completed: [CICD-05]

# Metrics
duration: 18min
completed: 2026-06-11
---

# Phase 4 Plan 05: Release supply-chain (SBOM + cosign keyless + SLSA provenance → GHCR) Summary

A `v*` tag (or published GitHub Release) now drives a single `release.yml` `publish` job that builds **both** production images, pushes them to GHCR **by immutable digest**, and — for each image — emits a syft SBOM in **both SPDX and CycloneDX**, signs it **keyless with cosign** (Sigstore + GitHub OIDC, no long-lived key), and attaches a **SLSA build-provenance attestation** bound to the digest, under **exactly** the four least-privilege token scopes with every third-party action SHA-pinned to a real resolved commit. CICD-05 is satisfied.

## What was built

`.github/workflows/release.yml` (new, 159 lines, SPDX `#` header):

- **Trigger:** `on: { push: { tags: ['v*'] }, release: { types: [published] } }`; workflow default `permissions: contents: read`.
- **`publish` job** with EXACTLY `contents: read`, `packages: write`, `id-token: write`, `attestations: write` — a two-image matrix (`burrow-api`/`Dockerfile.api`, `burrow-ui`/`Dockerfile.ui`).
- **Steps (in order):** checkout → setup-buildx → GHCR login (`GITHUB_TOKEN`) → metadata (§2.4 tags + OCI labels) → `id: build` build-push `push: true` (exposes `steps.build.outputs.digest`) → cosign-installer → SBOM SPDX → SBOM CycloneDX → `cosign sign --yes …@<digest>` (keyless) → `attest-build-provenance` (`subject-digest: <digest>`, `push-to-registry: true`).
- **Verification runbook** documented in the workflow trailer: `cosign verify` (certificate-identity-regexp + OIDC issuer) and `gh attestation verify` against the published digest, so the release runbook is self-contained (ci-cd §5.4).

## Verification performed (CI-assertable gates, all green)

| Gate | Result |
|------|--------|
| `python -c "import yaml; yaml.safe_load(...)"` | YAML parses; top keys name/on/permissions/jobs |
| publish-job permissions == {contents:read, packages:write, id-token:write, attestations:write} | PASS (exactly 4) |
| workflow default permissions == contents:read | PASS |
| trigger == push.tags ['v*'] + release.published | PASS |
| every `uses:` SHA-pinned (40-hex) + `# vX.Y.Z` comment | PASS (9 step uses) |
| SBOM in BOTH spdx-json and cyclonedx-json | PASS |
| cosign sign keyless (no `--key`) against `@<digest>` | PASS |
| build-push `push: true`, `id: build` → outputs.digest | PASS |
| attest-build-provenance `subject-digest: <digest>` + `push-to-registry: true` | PASS |
| GHCR target via `github.repository_owner` (no hardcoded org/secret) | PASS |
| `uvx --with charset-normalizer reuse lint` | 272/272 compliant (incl. release.yml) |
| ci.yml untouched (`git diff --stat`) | empty — unchanged |
| `cd api && uv run pytest -q` (non-regression) | 166 passed |
| `cd api && uv run ruff format --check .` (task verify) | 64 files already formatted |

## SHA resolution (no placeholders)

All five new actions were pinned to real commit SHAs resolved via the GitHub `git/refs/tags` API on this host (the same certifi-CA path 04-04 used to resolve image digests); each resolved ref pointed directly to a commit and was confirmed reachable:

| Action | Version | Commit SHA |
|--------|---------|-----------|
| docker/login-action | v3.6.0 | `5e57cd118135c172c3672efd75eb46360885c0ef` |
| docker/metadata-action | v5.9.0 | `318604b99e75e41977312d83839a89be02ca4893` |
| anchore/sbom-action | v0.20.7 | `d8a2c0130026bf585de5c176ab8f7ce62d75bf04` |
| sigstore/cosign-installer | v3.10.0 | `d7543c93d881b35a8faa02e8e3605f69b7a1ce62` |
| actions/attest-build-provenance | v3.0.0 | `977bb373ede98d70efdf65b84cb5f73e068dcc2a` |

checkout / setup-buildx / build-push reuse the exact SHAs already pinned in `ci.yml`. **No `PIN_AT_WRITE` / TODO placeholders remain.**

## CD / human acceptance (the authority beyond CI YAML-lint)

The CI-assertable proof here is **structural**: YAML/actionlint validity + the permission-scope + SHA-pin + by-digest assertions above. The **authoritative** acceptance is a CD/human step (Manual-Only in 04-VALIDATION) and is **NOT a PR-CI command**, because it needs a real `v*` tag, the live GHCR registry, and an OIDC-issued identity:

1. Tag `v*` / publish a Release → confirm both images land in GHCR by digest.
2. `cosign verify --certificate-identity-regexp 'https://github.com/BraveBearStudios/burrow/.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com ghcr.io/BraveBearStudios/burrow-api@sha256:<digest>` succeeds.
3. `gh attestation verify oci://ghcr.io/BraveBearStudios/burrow-api@sha256:<digest> --owner BraveBearStudios` confirms the SLSA provenance.
4. Confirm the SPDX + CycloneDX SBOMs are attached. (Repeat for `burrow-ui`.)

These invocations are documented verbatim in the `release.yml` trailer so the runbook is self-contained.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes and no Rule 4 architectural questions were needed. No authentication gates occurred.

## Threat-model coverage (04-05 STRIDE register)

| Threat ID | Mitigation as shipped |
|-----------|----------------------|
| T-04-05A (long-lived signing key) | cosign **keyless** — no `--key`, ephemeral OIDC identity; nothing stored to leak/rotate |
| T-04-05B (token over-scope) | publish job EXACTLY 4 scopes; workflow default `contents: read` |
| T-04-05C (signing a floating tag) | sign + attest the immutable `steps.build.outputs.digest` |
| T-04-05D (compromised action) | all 8 distinct actions SHA-pinned to resolved commits + version comment |
| T-04-05E (unsigned/unattested image) | every published image signed + dual-format SBOM'd + provenance-attested; verify runbook documented |
| T-04-05F (fork PR reads publish creds) | publish gated to `v*` tags / published releases — not PRs |
| T-04-SC (supply-chain installs) | accept — zero new runtime registry packages; CI tooling is SHA-pinned GitHub Actions |

## Known Stubs

None. (`harden-runner` is an intentional, CONTEXT-deferred non-stub — release-polish, explicitly out of scope, not required for CICD-05.)

## Open / carried items (CI-only / CD-human, NOT a PR-CI blocker)

- `actionlint` is unavailable on this Windows dev host → the workflow was validated via `python yaml.safe_load` + the targeted structural assertions above; the **first CI run** (and any actionlint in CI) is the structural authority.
- The actual GHCR push + `cosign verify` + `gh attestation verify` against a published digest is the **CD/human** acceptance (needs a real tag + registry + OIDC), documented in the runbook — not run in PR CI.

## Self-Check: PASSED

- `.github/workflows/release.yml` — FOUND
- commit `fd58d5e` (feat 04-05 release.yml) — FOUND
