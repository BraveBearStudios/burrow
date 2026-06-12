<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
plan: 04
subsystem: infra
tags: [docker, dockerfile, trivy, sarif, github-actions, supply-chain, nginx, uv, ci]

# Dependency graph
requires:
  - phase: 02-terminal-mvp
    provides: "ui/dist Vite build + ui/nginx.e2e.conf SPA-serve pattern + /api/v1/health route"
  - phase: 00-foundations
    provides: ".github/workflows/ci.yml static-gates job + SHA-pin convention + REUSE.toml"
provides:
  - "Dockerfile.api — multi-stage, digest-pinned, non-root, HEALTHCHECK on /api/v1/health, OCI labels"
  - "Dockerfile.ui — node:22 build -> nginx:1.27-alpine runtime, unprivileged nginx :8080, OCI labels"
  - ".dockerignore — secret-free minimal build context (excludes .git, .env*, tests, local state)"
  - "ci.yml build-scan job — build both images (no push) + Trivy two-run gate (fail HIGH/CRITICAL) + SARIF upload"
affects: [04-hardening-release-05-release-yml, deployment, ghcr-publish]

# Tech tracking
tech-stack:
  added:
    - "docker/setup-buildx-action@d7f5e7f (v4.1.0)"
    - "docker/build-push-action@f9f3042 (v7.2.0)"
    - "aquasecurity/trivy-action@ed142fd (v0.36.0)"
    - "github/codeql-action/upload-sarif@c35d1b1 (codeql-bundle-v2.25.6)"
    - "ghcr.io/astral-sh/uv@sha256:f6e3549 (0.9.9) — build-stage lockfile installer"
  patterns:
    - "Base images pinned by live multi-arch index digest, not a floating tag"
    - "Trivy two-run pattern: gate run (exit-code 1) + if:always() SARIF run (one run can't do both)"
    - "Non-root nginx on :8080 with pid/temp under /tmp (a non-root process can't bind :80)"
    - "Python urllib HEALTHCHECK (no curl assumption in slim images)"

key-files:
  created:
    - "Dockerfile.api"
    - "Dockerfile.ui"
    - ".dockerignore"
  modified:
    - ".github/workflows/ci.yml"

key-decisions:
  - "Resolved REAL live base-image digests (python:3.12-slim, node:22, nginx:1.27-alpine) and the uv build-image + all four actions to commit SHAs — NO PIN_AT_* placeholders remain"
  - "api HEALTHCHECK probes /api/v1/health (verified mounted path), NOT the /health the §2.2 snippet shows"
  - "ui runs unprivileged nginx on :8080 (non-root cannot bind :80); all writable paths relocated to /tmp"
  - "uv binary copied from its own digest-pinned GHCR image rather than a curl|sh install"

patterns-established:
  - "Multi-arch index digest pinning for all FROM/COPY --from base images"
  - "Trivy two-run gate + SARIF upload as the PR-time fail-closed vuln gate (no push on PR)"

requirements-completed: [CICD-04]

# Metrics
duration: 41min
completed: 2026-06-11
---

# Phase 4 Plan 04: Dockerfiles + CI build-scan gate Summary

**Two hardened multi-stage Dockerfiles (live-digest-pinned bases, non-root users, HEALTHCHECK on the verified /api/v1/health, six OCI labels) plus a secret-free .dockerignore and a ci.yml build-scan job that builds both images without pushing and runs the Trivy two-run gate (fail on HIGH/CRITICAL) with full SARIF upload to code scanning.**

## Performance

- **Duration:** ~41 min
- **Started:** 2026-06-11T23:04:00Z (approx)
- **Completed:** 2026-06-11T23:46:00Z
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- `Dockerfile.api`: python:3.12-slim build→runtime (both pinned by live multi-arch index digest); `uv sync --frozen` from the committed lockfile in the build stage; runtime carries only the resolved `.venv` + app source `COPY --chown`'d to a non-root UID 10001; HEALTHCHECK via in-image Python `urllib` against the **verified** `/api/v1/health` path; six OCI provenance/AGPL-§13 labels (dynamic revision/created/version are ARG-backed for the CI metadata action).
- `Dockerfile.ui`: node:22 build stage (`npm ci` + `vite build` → `dist/`) → nginx:1.27-alpine runtime; unprivileged nginx bound to `:8080` with pid + all temp paths under `/tmp` and the SPA root `chown`'d to `nginx`; SPA history fallback; wget HEALTHCHECK on `/`; the same six OCI labels.
- `.dockerignore`: excludes `.git`, every `.env*` variant, `**/tests`, and local Python/Node/DB state so no secret enters a layer (T-04-04A mitigation).
- `ci.yml` `build-scan` job: `needs: [static-gates]`, least-priv `contents: read` + `security-events: write`, a two-image matrix building with `push: false` + `load: true`, then the Trivy two-run pattern (gate: table + `severity HIGH,CRITICAL` + `exit-code 1`; report: `if: always()` SARIF) and an `if: always()` `upload-sarif`. All new actions SHA-pinned with trailing version comments; existing jobs and default permissions untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Dockerfiles + .dockerignore** — `1bcd3bd` (feat)
2. **Task 1 follow-up: OCI source label correction** — `3f1aa7c` (fix, Rule 1)
3. **Task 2: ci.yml build-scan job** — `4a0f617` (feat)

**Plan metadata:** committed separately with this SUMMARY + STATE + ROADMAP.

## Files Created/Modified

- `Dockerfile.api` — hardened multi-stage api image; HEALTHCHECK `/api/v1/health`.
- `Dockerfile.ui` — hardened multi-stage ui image; unprivileged nginx :8080.
- `.dockerignore` — secret-free minimal build context.
- `.github/workflows/ci.yml` — added the `build-scan` job (Trivy two-run gate + SARIF).

## Decisions Made

- **Live digests, no placeholders.** Although Docker/crane/skopeo are unavailable on this Windows host and a first digest-resolution attempt hit `CERTIFICATE_VERIFY_FAILED` (expired cert in the default store), resolving via the `certifi` CA bundle against the Docker registry + GHCR HTTP API succeeded. All three base images, the uv build image, and all four GitHub Actions are pinned to **real** digests/SHAs. The optional `PIN_AT_*` placeholder fallback was therefore **not** used.
- **Verified health path.** The api HEALTHCHECK targets `/api/v1/health` (router prefix `/api/v1` + route `/health`, confirmed in `api/routers/health.py`), not the `/health` the §2.2 spec snippet shows. Matches the existing `docker-compose.e2e.yml` urllib probe.
- **Unprivileged nginx.** A non-root process cannot bind `:80`, so the ui image serves on `:8080` and relocates pid/client/proxy/fastcgi/uwsgi/scgi temp paths under `/tmp`.
- **uv via digest-pinned image.** The build stage copies the uv binary from `ghcr.io/astral-sh/uv@sha256:f6e3549…` rather than a `curl | sh` install, preserving the no-floating-tag discipline end to end.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the OCI `image.source` label to the real repo slug**
- **Found during:** SUMMARY prep (verifying the GitHub owner via `gh api`)
- **Issue:** Both Dockerfiles initially labeled `org.opencontainers.image.source=github.com/brave-bear-studios/burrow`, but the actual repo is `github.com/BraveBearStudios/burrow`. A wrong source label breaks the AGPL §13 source-availability link that the label exists to satisfy.
- **Fix:** Updated the slug to `BraveBearStudios/burrow` in both `Dockerfile.api` and `Dockerfile.ui`.
- **Files modified:** `Dockerfile.api`, `Dockerfile.ui`
- **Verification:** Grep confirms the corrected URL; REUSE lint stays 100%.
- **Committed in:** `3f1aa7c` (standalone fix commit)

---

**Total deviations:** 1 auto-fixed (1 bug, Rule 1)
**Impact on plan:** The fix is required for the OCI label to be correct/useful. No scope creep — the rest of the plan executed as written.

## Issues Encountered

- **Base-image digest resolution on the dev host.** Docker, crane, and skopeo are absent, and the first registry HTTP attempt failed with `CERTIFICATE_VERIFY_FAILED` (an expired CA in the default trust store). Resolved by using the `certifi` CA bundle for the TLS context — yielding real multi-arch index digests for all bases. No `verify_ssl=False`-style verification bypass was used (that would have produced an untrusted digest).
- **Pre-existing test warnings.** The api suite emits `websockets.legacy` `DeprecationWarning`s unrelated to this plan — left untouched (out of scope).

## Validation Performed

- `cd api && uv lock --check` → green (Resolved 57 packages).
- `uvx --with charset-normalizer reuse lint` → 100% compliant (266/266 files).
- api HEALTHCHECK grep → confirms `/api/v1/health`, zero bare `localhost:8000/health` matches.
- `python -c "import yaml; yaml.safe_load(...)"` → ci.yml parses; build-scan job has `needs:[static-gates]`, `contents:read`+`security-events:write`, two-image matrix, all six steps.
- `cd ui && npx tsc --noEmit` → exit 0 (no errors).
- `cd api && uv run pytest -q` → **155 passed** (non-regression).
- `actionlint` was unavailable on this host (not installed); the YAML structural validation above stands in. The `build-scan` job's true acceptance is the first CI run (Docker is CI-only per the repo pattern).

## Pre-merge Actions

- **None blocking.** All base-image digests and action SHAs are real and resolved — there are **no** `PIN_AT_*` placeholders to resolve before merge. (Operators may optionally re-pin to a newer base digest at release time, but the committed pins build as-is.)

## Next Phase Readiness

- Plan 04-05 (`release.yml`: SBOM → cosign → SLSA provenance → GHCR publish) can build directly on these two Dockerfiles and the established SHA-pin + per-job-permission convention.
- The build-scan job is the fail-closed vuln gate that must pass before any publish; release.yml adds `push: true` by digest only after this gate is green.

## Self-Check: PASSED

- Files: `Dockerfile.api`, `Dockerfile.ui`, `.dockerignore`, `.github/workflows/ci.yml`, `04-04-SUMMARY.md` — all present.
- Commits: `1bcd3bd`, `3f1aa7c`, `4a0f617` — all in the git log.

---
*Phase: 04-hardening-release*
*Completed: 2026-06-11*
