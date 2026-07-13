---
phase: 15-pipeline-unblock-green-main
plan: 02
subsystem: infra
tags: [trivy, ci, docker, digest-pinning, reuse, supply-chain, relx-05]

# Dependency graph
requires:
  - phase: 14-first-real-infra-acceptance
    provides: "ci.yml build-scan job with the two-run Trivy pattern (gate + if:always SARIF)"
provides:
  - "RELX-05 policy: the build-scan Trivy HIGH/CRITICAL gate runs with ignore-unfixed: true and reads a reviewed .trivyignore, so unfixable base CVEs stop failing the gate while fixable HIGH/CRITICAL still do"
  - "A reviewed repo-root .trivyignore (SPDX header + owner|reason|link|reviewed per-entry format, unfixable-only / never-allowlist-a-fixable rule, zero CVE entries at seed) that passes reuse lint via its inline # header"
  - "Repinned base image digests to the current multi-arch index (python:3.12-slim + node:22 changed; nginx:1.27-alpine + uv:0.9.9 re-resolved, already current) so fixable base CVEs are cleared by rebase"
affects: [phase-16-land-credential-backend-reconcile-release-train, phase-20-signed-ghcr-release, green-main, trivy, reuse-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reviewed CVE-allowlist policy file (.trivyignore) with a documented per-entry owner|reason|link|reviewed acceptance format and an unfixable-only rule"
    - "Base-image digest resolution via the anonymous Docker Registry v2 HTTP API (index media type) when docker/crane/skopeo are unavailable on the dev box"

key-files:
  created:
    - .trivyignore
    - .planning/phases/15-pipeline-unblock-green-main/deferred-items.md
  modified:
    - .github/workflows/ci.yml
    - Dockerfile.api
    - Dockerfile.ui

key-decisions:
  - "ignore-unfixed: true drops only base CVEs with no upstream fix; fixable HIGH/CRITICAL still fail the gate and are cleared by a base repin, never allowlisted (CONTEXT RELX-05 line 24)"
  - ".trivyignore seeded with ZERO CVE entries: the live HIGH/CRITICAL findings are visible only on the Linux CI runner, not the Windows dev box, so residual-unfixable entries are added later from the runner"
  - "Digests resolved via the Docker Registry v2 HTTP API index digest (docker/crane/skopeo absent); the resolved-date comment advanced to 2026-07-13 only because a real repin landed (python + node changed)"
  - "The 15-02-PLAN.md reuse invalid-expression finding is out of RELX-05 scope (CICD-06); logged to deferred-items.md, not fixed, per the scope boundary"

patterns-established:
  - "Pattern 1: a security gate suppression file is a reviewed, attributable policy artifact (owner + reason + advisory link + reviewed date per entry), never a blanket mute"
  - "Pattern 2: prove a CI-runner-only gate structurally on the dev box (policy + pins), and carry the actual green-gate observation as CI-gated"

requirements-completed: [RELX-05]

# Metrics
duration: 24min
completed: 2026-07-13
---

# Phase 15 Plan 02: Green Trivy HIGH/CRITICAL Gate (RELX-05) Summary

**RELX-05 policy landed: the build-scan Trivy gate now runs ignore-unfixed with a reviewed zero-seed .trivyignore, and the runtime/build base images are repinned to their current patched multi-arch index digests, so unfixable base CVEs stop failing while fixable ones are cleared by rebase (green-gate proof is CI-gated).**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-07-13T18:04:00Z (approx)
- **Completed:** 2026-07-13T18:28:00Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified) + 1 meta (deferred-items.md)

## Accomplishments

- Flipped the ci.yml build-scan HIGH/CRITICAL gate to `ignore-unfixed: "true"` and wired `trivyignores: .trivyignore`, leaving the `if: always()` SARIF report run and the trivy-action SHA pin byte-unchanged (all findings still reach code scanning).
- Authored a reviewed repo-root `.trivyignore`: two-line `#` SPDX header, a documented `owner | reason | link | reviewed` per-entry acceptance format, the explicit unfixable-only / never-allowlist-a-fixable-CVE rule, and ZERO CVE entries at seed. `reuse lint` recognizes it via the inline `#` header (copyright + license both detected), so no `.trivyignore.license` sidecar was needed.
- Repinned every base image to the current multi-arch index digest, resolved via the anonymous Docker Registry v2 HTTP API (docker/crane/skopeo are absent on this box): a real repin landed for `python:3.12-slim` (both build + runtime stages, identical digest) and `node:22`; `nginx:1.27-alpine` and `ghcr.io/astral-sh/uv:0.9.9` were re-resolved on 2026-07-13 and confirmed already at the current index digest.

## Task Commits

Each task was committed atomically:

1. **Task 1: ignore-unfixed on the gate + create the reviewed .trivyignore** - `7975f65` (fix)
2. **Task 2: repin the base image digests to current patched** - `ea0c0c5` (fix)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP/REQUIREMENTS) - final docs commit below.

## Files Created/Modified

- `.github/workflows/ci.yml` - build-scan Trivy gate step: `ignore-unfixed "false" -> "true"` + `trivyignores: .trivyignore`; SARIF run and SHA pin untouched.
- `.trivyignore` - reviewed residual-unfixable-CVE allowlist policy (SPDX header, per-entry format, unfixable-only rule, zero entries).
- `Dockerfile.api` - `python:3.12-slim` repinned `a39549e2 -> 423ed6ab` across build + runtime stages; python + uv resolved-date comments advanced to 2026-07-13.
- `Dockerfile.ui` - `node:22` repinned `2d178f27 -> a25c9934`; node + nginx resolved-date comments advanced to 2026-07-13 (nginx digest unchanged).
- `.planning/phases/15-pipeline-unblock-green-main/deferred-items.md` - logs the out-of-scope reuse invalid-expression finding (D-15-02-01).

## Base Digest Repins (old -> new, resolved 2026-07-13)

| Image | Stage | Old digest | New digest | Changed |
|-------|-------|-----------|-----------|---------|
| python:3.12-slim | build + runtime | sha256:a39549e2...9904c94 | sha256:423ed6ab...199fbf | YES (real repin) |
| node:22 | build | sha256:2d178f27...600eb3 | sha256:a25c9934...27c365 | YES (real repin) |
| nginx:1.27-alpine | runtime | sha256:65645c7b...2f2a10 | sha256:65645c7b...2f2a10 | no (already current) |
| ghcr.io/astral-sh/uv:0.9.9 | build | sha256:f6e3549e...da8652 | sha256:f6e3549e...da8652 | no (already current) |

Resolution method: anonymous Docker Registry v2 / GHCR token, `Accept: application/vnd.oci.image.index.v1+json`, read `Docker-Content-Digest`. Verified the python digest is a genuine multi-arch OCI index (16 platform manifests), not a single-arch manifest.

## Structural Verification (dev-box provable)

- ci.yml gate: `ignore-unfixed == true` and `trivyignores == .trivyignore` (parsed from YAML). PASS.
- The `if: always()` SARIF run and the `aquasecurity/trivy-action` 40-hex SHA pin are byte-unchanged. PASS.
- ci.yml parses as YAML. PASS.
- `.trivyignore` has the SPDX header and the `reason:` / `link:` / `reviewed:` per-entry tokens plus the `unfixable` / `never` rule text. PASS.
- `.trivyignore` is reuse-clean and recognized (inline `#` header; 460/460 files carry copyright + license info). PASS. No sidecar needed.
- Both Dockerfiles keep valid `sha256:` + 64-hex pins; api python identical across both stages; `2026-07-13` recorded in both files; the `image.source` label stays canonical-case `https://github.com/BraveBearStudios/burrow`. PASS.

## CI-gated / human_needed

- **The actual Trivy HIGH/CRITICAL gate turning GREEN** is provable only on the Linux CI runner, where the real findings are visible (not on the Windows dev box). This is the RELX-05 green-gate proof and is deferred to the first CI run on the branch / PR #3.
- **Residual unfixable-but-accepted CVE ids** (if `ignore-unfixed: true` plus the digest repins do not fully clear the gate) are added to `.trivyignore` later with a full `owner | reason | link | reviewed` line each, driven by the runner findings. A FIXABLE base HIGH/CRITICAL CVE is never added there; it is cleared by a further base repin/rebuild or escalated.
- **Fixable-base-CVE lever status:** NOT carried as un-repinnable. A real repin landed (python + node) and the other two bases were confirmed already current, all via live registry resolution. Whether the current digests fully clear the fixable base CVEs is the CI-gated Trivy observation above.

## Deviations from Plan

None - plan executed exactly as written. Task 1 and Task 2 landed their acceptance criteria; both automated verify one-liners returned OK. No Rule 1-4 auto-fixes were required inside the plan's scope.

## Issues Encountered

- **Out-of-scope discovery (logged, not fixed):** running the ci.yml reuse hard gate to confirm `.trivyignore` recognition surfaced one repo-wide `reuse lint` failure: an "Invalid SPDX License Expression" in the committed `15-02-PLAN.md` (its action prose quotes an SPDX header tag with trailing text on the same line, which reuse parses as a license expression). It is the phase's own plan artifact, predates execution, and is a CICD-06 concern, not RELX-05. Per the scope boundary it is logged in `deferred-items.md` (D-15-02-01) with the exact tool-sanctioned remedy, not fixed here. `.trivyignore` itself is clean and is the only new file this plan adds to the scan.

## Next Phase Readiness

- RELX-05 policy + base repins are structurally landed; the green-gate proof is a CI run (expected on PR #3 CI). This unblocks the Trivy lever of "green main."
- **Green-main blocker to hand off (not RELX-05):** the reuse hard gate will red on the branch / PR CI until D-15-02-01 (the 15-02-PLAN.md invalid SPDX expression) is fixed. This belongs to the green-main sequencing (Phase 16 merges PR #3 onto green main). Remedy is one line and documented in `deferred-items.md`.
- Phase 15 remaining: plan 15-03 (RELX-03 oss-ruleset exclusion, operator-run) still to execute.

## Self-Check: PASSED

- Created files exist: `.trivyignore`, `deferred-items.md`, `15-02-SUMMARY.md`.
- Task commits exist: `7975f65` (Task 1), `ea0c0c5` (Task 2).
- `.trivyignore` is reuse-clean; the only repo-wide `reuse lint` invalid expression is the pre-existing `15-02-PLAN.md` (logged as D-15-02-01), unchanged by this plan.

---
*Phase: 15-pipeline-unblock-green-main*
*Completed: 2026-07-13*
