<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 15: Pipeline Unblock & Green Main - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the three live CI/release pipeline blockers so the release pipeline is functional and `main` is green (precondition PC1), and reconcile the release-tag scheme. In scope: the `oss` repo ruleset exclusion for the release-please branch (RELX-03, operator/admin-run), lowercasing the GHCR owner + giving the SBOM step registry auth in `release.yml` so images ship signed + attested (RELX-04), greening the Trivy HIGH/CRITICAL gate on `main` (RELX-05), and narrowing the `release.yml` tag glob to semver + retiring hand-pushed milestone tags (RELX-06). Out of scope: merging PR #3 (Phase 16), the actual first signed release run (Phase 20), and any credential/feature code.

</domain>

<decisions>
## Implementation Decisions

### Pipeline fixes

- **`oss` ruleset (RELX-03):** exclude `refs/heads/release-please--**` from the active `oss` ruleset (surgical; leaves branch protection intact elsewhere), rather than adding `github-actions[bot]` to bypass_actors. This is a GitHub repo-admin change, NOT a repo file — the operator runs it (the available `gh` token lacks `admin:org`/repo-admin). Claude documents the exact `gh api` / repo-settings steps.
- **Trivy unfixable-base-CVE policy (RELX-05):** set `ignore-unfixed: true` on the HIGH/CRITICAL gate, bump base images to patched digests where one exists, and add a reviewed `.trivyignore` (owner + reason + link per entry) for any residual unfixable CVE. Keeps the gate meaningful for fixable findings.
- **"Green main" sequencing (RELX-05):** the pipeline fixes are authored on `feat/gui-managed-secrets` (part of PR #3). "Green main" is realized when PR #3's CI is green and it merges in Phase 16 — not via a separate pipeline-only PR to main.
- **Tag scheme (RELX-06):** narrow `release.yml`'s tag trigger glob to semver `v[0-9]+.[0-9]+.[0-9]+` so hand-pushed two-component `v1.x` milestone tags no longer fire it; also stop hand-pushing milestone tags (release-please owns release tags).

### Claude's Discretion

- Exact `.trivyignore` entries + which base digests to bump (driven by the actual live Trivy findings on the runner).
- Whether the GHCR-owner lowercase is done via a `${VAR,,}` / `tr` step feeding a step output vs reusing `docker/metadata-action` outputs / the pushed digest — pick the cleanest that fixes syft + cosign sign + SLSA attest uniformly.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `.github/workflows/release.yml` — the supply-chain publish path (SBOM/syft -> cosign keyless sign -> SLSA attest). The mixed-case `${{ github.repository_owner }}` = `BraveBearStudios` in the SBOM/sign/attest steps is the bug (`docker/metadata-action` already lowercases the pushed tag).
- `.github/workflows/ci.yml` — the `build-scan` job runs Trivy twice (gate `exit-code:1` HIGH/CRITICAL `ignore-unfixed:false` + SARIF upload via `github/codeql-action/upload-sarif`). The gate is what reds main.
- `.github/workflows/release-please.yml` + `release-please-config.json` (release-type simple, include-v-in-tag) + `.release-please-manifest.json` (`.`: `1.1.0`).

### Established Patterns

- Every `uses:` is SHA-pinned; harden-runner egress `audit` is step 0 on all jobs (the audit->block flip is Phase 20, NOT here — do not touch it).
- `docker/metadata-action` already emits lowercased image refs for the push; the fix is to reuse that lowercasing for the SBOM/sign/attest refs too.

### Integration Points

- The `oss` ruleset (id 18189353) is GitHub repo config, not a repo file — RELX-03 is executed via `gh api` / repo settings, not a commit.
- Verifying "green main" + a green signed release requires CI runs on GitHub (post-merge / on a tag) — not fully provable from the dev box; the branch/PR CI is the in-session proof.

</code_context>

<specifics>
## Specific Ideas

- Recon evidence to act on: release run `27664127224` (syft FAIL, image pushed unsigned `burrow-ui@sha256:e49cf96c...`); the release-please run failing at "Error updating ref heads/release-please--branches--main"; CI `build-scan` FAIL x2 at the Trivy gate. The mixed-case owner bug also appears in the release.yml verify-runbook comment + `14-ACCEPTANCE.md` Steps E/F — fix those in the same pass.
- `actionlint` (carried ACC-02 item 13) already passes on the live runner (run `29221779815`) — do not touch that gate.

</specifics>

<deferred>
## Deferred Ideas

- Harden-runner egress `audit`->`block` flip (needs a green audit-mode release run's telemetry) -> Phase 20.
- Merging PR #3 + the actual `v1.4.0` release-please forward-reconcile -> Phase 16.
- Cutting + verifying the first signed release -> Phase 20.

</deferred>
