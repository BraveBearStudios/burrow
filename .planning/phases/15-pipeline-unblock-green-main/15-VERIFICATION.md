<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: passed
phase: 15
verified: 2026-07-13
---

# Phase 15: Pipeline Unblock & Green Main - Verification

**Goal:** Fix the three live CI/release pipeline blockers so the release pipeline is functional and `main` is green (PC1), and reconcile the release-tag scheme.

## Must-Haves

1. **release-please can maintain its release branch (RELX-03)** - PASSED. The operator excluded `refs/heads/release-please--**` from the active `oss` ruleset (id 18189353), verified live (`conditions.ref_name.exclude` contains the glob; enforcement active; all six rules + bypass_actors unchanged). The end-to-end "no Error updating ref" run realizes at the Phase 16 merge (release-please runs on push:main).
2. **Published GHCR images ship signed + attested (RELX-04)** - PASSED (structural). `release.yml` builds every GHCR ref from one lowercased `imgref` base (zero raw `github.repository_owner` refs in the syft/cosign/attest steps), both SBOM steps carry syft registry auth, SHA-pins + the 4-perm publish block intact. The live signed+attested GREEN release realizes at Phase 20 (a real `v1.4.0` tagged run).
3. **Branch CI passes the Trivy HIGH/CRITICAL gate - green main (RELX-05)** - PASSED. Gate set `ignore-unfixed: true` + `trivyignores: .trivyignore` (unfixable-only, reuse-clean); base digests repinned; the FIXABLE HIGH CVEs the gate honestly caught were CLEARED by upgrade (starlette 1.2.1 -> 1.3.1 for CVE-2026-54283, 291 api tests pass; nginx-alpine `apk upgrade` for libxml2/musl/nghttp2-libs/zlib). CI run 29278129663 (headSha bf2570f): all four jobs SUCCESS. Green MAIN realizes fully at the Phase 16 merge.
4. **Release tags follow semver, no manual-tag collision (RELX-06)** - PASSED. `release.yml` `on.push.tags` narrowed to `v[0-9]+.[0-9]+.[0-9]+`; hand-pushed v1.x milestone tags no longer trigger it. The stale 1.2.0 -> v1.4.0 release-please reconcile is scoped to Phase 16 (tied to the merge).

## Evidence

- CI run **29278129663** (`bf2570f`): Conventional-Commit PR title PASS, Tier-0 static gates PASS (reuse + actionlint + ruff + mypy), Build+scan burrow-ui PASS, Build+scan burrow-api PASS.
- Ruleset PUT verified: `exclude: ["refs/heads/release-please--**"]`, enforcement active, rules/bypass unchanged.
- `reuse lint`: compliant 464/464 (D-15-02-01 fixed via the REUSE-Ignore comment pair).

## Realized-at-downstream (by design, NOT gaps)

- The green MAIN (vs branch) proof + release-please-maintains-branch confirmation land at the **Phase 16** PR #3 merge (release-please + the gate run on `main`).
- The signed + attested GHCR release + cosign/attestation verify land at **Phase 20** (a real `v1.4.0` release run).

**Verdict: PASSED** - all four requirements delivered; branch CI green; downstream realizations are the roadmap's dependency chain (Phases 16, 20), not Phase 15 gaps.
