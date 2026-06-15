<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow — CI/CD & Testing Specification
## Working Draft v0.1

**Status:** Spec only — no workflows exist yet. Claude Code implements this when
the project kicks off (see `docs/open-items.md` §5).
**Scope:** How Burrow is tested, built into container images, scanned, signed,
and published to the GitHub Container Registry (GHCR).

This document is the authoritative reference for the items the tech spec and
`CONTRIBUTING.md` refer to as "the CI matrix." It assumes the stack and repo
layout defined in [`tech-spec.md`](tech-spec.md): a FastAPI backend (`api/`,
Python 3.12, uv, ruff, mypy) and a Vite + React + TypeScript frontend (`ui/`,
biome).

---

## 1. Goals & principles

1. **Fail-closed.** Nothing is built or published unless every test and gate
   upstream of it passed. The pipeline is a DAG: gates → tests → build → scan →
   sign → push. A red step blocks everything downstream.
2. **CI proves a clean build and inter-app functionality — not live
   infrastructure.** CI never talks to a real Proxmox node. The Proxmox/compute
   integration is exercised against a fake `ComputeProvider` and a mocked
   Proxmox API. Real-infrastructure validation happens in the dev environment,
   not in CI (see §4.4).
3. **Reproducible images.** Multi-stage builds, base images pinned by digest,
   deterministic dependency installs from committed lockfiles (`uv.lock`, the JS
   lockfile). The same commit always produces the same image contents.
4. **Supply-chain integrity is a first-class gate.** Every published image is
   scanned, accompanied by an SBOM, signed, and carries build provenance. See §5.
5. **Least privilege.** The default `GITHUB_TOKEN` is read-only; each job widens
   only the exact permissions it needs. Third-party actions are pinned to a full
   commit SHA, never a mutable tag.

---

## 2. Container & image strategy

### 2.1 Images

Two images, built and published independently:

| Image | Contents | Base (build → runtime) |
|---|---|---|
| `burrow-api` | FastAPI app + uvicorn | `python:3.12-slim` → `python:3.12-slim` (or distroless) |
| `burrow-ui`  | Vite static build served by nginx | `node:22` (build) → `nginx:1.27-alpine` |

Published as:

```
ghcr.io/<owner>/burrow-api
ghcr.io/<owner>/burrow-ui
```

`<owner>` is the GitHub org/user that owns the repo. The worker LXC image is
**not** a container — it is a Proxmox golden template provisioned out of
`cc-worker-config` (tech-spec §9) and is out of scope for this pipeline.

### 2.2 Dockerfile requirements

Both `Dockerfile.api` and `Dockerfile.ui` (repo root, per tech-spec §4.1) must:

- Use **multi-stage** builds; the final stage carries only runtime artifacts (no
  build toolchain, no dev dependencies).
- Pin base images **by digest** (`FROM python:3.12-slim@sha256:…`), not by tag.
- Install dependencies from the committed lockfile only (`uv sync --frozen` /
  `npm ci`), so builds are deterministic.
- Run as a **non-root** user; set a read-only root filesystem where possible and
  drop all Linux capabilities not required.
- Declare a `HEALTHCHECK` (`api`: `GET /health`; `ui`: nginx status/200 on `/`).
- Carry OCI labels for provenance and AGPL §13 source-availability:
  `org.opencontainers.image.source`, `.revision`, `.created`, `.licenses`,
  `.title`, `.version`.
- Include a `.dockerignore` that excludes `.git`, `.env*`, tests, and local
  state so build context stays minimal and secret-free.

### 2.3 Local development

`docker-compose.dev.yml` (tech-spec §4.1) wires `api` + `ui` with hot reload for
local work. It is a developer convenience and is **not** used by CI to build
release images — CI builds the production Dockerfiles directly with Buildx.

### 2.4 Tagging

| Trigger | Tags applied |
|---|---|
| Push to default branch | `edge`, `sha-<short>` |
| Release tag `vX.Y.Z` | `X.Y.Z`, `X.Y`, `latest`, `sha-<short>` |
| Pull request | **none** — PRs build the image to prove it builds, but never push |

Images are also addressable by immutable digest; deployment configs should pin
the digest, not a floating tag.

---

## 3. Pipeline overview

### 3.1 Workflows

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | PR + push to default branch | Static gates → tests → build (no push on PR) |
| `.github/workflows/release.yml` | Release published / tag `v*` | Build → scan → SBOM → sign → push to GHCR |
| `.github/workflows/codeql.yml` | PR + weekly schedule | SAST for Python and JS/TS |
| `.github/workflows/dependency-review.yml` | PR | Block PRs that introduce vulnerable/incompatible deps |
| `.github/workflows/scorecard.yml` | weekly schedule | OpenSSF Scorecard supply-chain posture report |

### 3.2 Job DAG (ci.yml)

```
                 ┌─────────────┐
                 │ static-gates│  lint · format · type-check · SPDX · commits
                 └──────┬──────┘
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   ┌────────────┐ ┌───────────┐ ┌───────────┐
   │ unit (api) │ │ unit (ui) │ │ secrets   │  gitleaks
   └─────┬──────┘ └─────┬─────┘ └───────────┘
         └──────┬───────┘
                ▼
        ┌───────────────┐
        │  integration   │  api+sqlite+mocked proxmox · ui+MSW
        └──────┬─────────┘
               ▼
        ┌───────────────┐
        │  e2e           │  full stack, FakeComputeProvider, Playwright
        └──────┬─────────┘
               ▼
        ┌───────────────┐
        │ build (matrix) │  burrow-api, burrow-ui — build only, prove it builds
        └──────┬─────────┘
               ▼
        ┌───────────────┐
        │ image-scan     │  Trivy/Grype on the built image (fail on HIGH/CRIT)
        └────────────────┘
```

`release.yml` re-runs build on the tagged commit and continues into SBOM →
sign → attest → push (§5). Publish never happens from `ci.yml`.

### 3.3 Gating & merge policy

- **Branch protection** on the default branch requires: all `ci.yml` jobs green,
  CodeQL green, dependency-review green, ≥1 maintainer review, up-to-date branch.
- PRs are **squash-merged**; the PR title must be a valid Conventional Commit
  (drives versioning — see §6).
- `concurrency` cancels superseded runs per branch/PR to save minutes.
- Caching: uv cache + npm cache keyed on lockfile hashes; Buildx layer cache via
  the GitHub Actions cache backend.

---

## 4. Test tiers

The suite is a pyramid: many fast static/unit checks, fewer integration tests,
a thin e2e layer. Every tier runs in CI on every PR. **Regression tests are not
a separate tier** — every bug fix lands with a test that reproduces it, and those
tests live permanently in the unit/integration suites (§4.6).

### 4.1 Tier 0 — Static gates (`static-gates`)

Fast, no runtime. Fail the build on any violation.

- **Lint:** `ruff check` (api), `biome lint` (ui).
- **Format:** `ruff format --check` (api), `biome format --check` (ui).
- **Type-check:** `mypy` (api, strict), `tsc --noEmit` (ui).
- **SPDX header check:** every source file carries the two-line SPDX header
  (`CONTRIBUTING.md`); a `reuse lint` (or equivalent) job enforces it.
- **Conventional Commits:** PR title + commit messages validated.
- **Lockfile freshness:** `uv lock --check` and `npm ci` confirm lockfiles match
  manifests.

### 4.2 Tier 1 — Unit / regression (`unit-api`, `unit-ui`)

Pure logic, no network, no containers. Fast and high-volume.

- **Backend (`pytest`):** services and helpers with all I/O mocked —
  `WorkspaceService` state-machine transitions, capacity-guard logic, VMID
  allocation, userdata builder, response-envelope shaping, Pydantic models.
  `ProxmoxService` and the DB are replaced with test doubles.
- **Frontend (`vitest` + Testing Library):** Zustand `layoutStore` reducers,
  hooks (`useWorkspaces`, `useTerminal`) with fetch/WebSocket mocked, the typed
  API client, and component rendering/states.
- **Coverage gate:** fail under an agreed line/branch threshold (start at 80%,
  ratchet up). Coverage is reported but the **threshold** is the gate.

### 4.3 Tier 2 — Integration (`integration`)

Real internal wiring; external systems faked. No real Proxmox, no real network
egress.

- **Backend:** run the FastAPI app via `httpx.ASGITransport` against a **real
  SQLite** database (exercises the `DbProvider` + migrations for real) with the
  **Proxmox HTTP API mocked** (`respx`/`responses`). Cover the full
  `/api/v1/workspaces` CRUD, the workspace create saga (reserve VMID → clone →
  boot → health → running) including compensation/cleanup on failure, the state
  machine, and the `/health` endpoint.
- **WebSocket terminal proxy:** stand up a **stub ttyd** (a tiny local WS echo
  server) and assert the proxy bridges binary frames both directions, logs
  connect/disconnect events, and emits the right error frames when the upstream
  is unreachable.
- **Contract:** snapshot the generated OpenAPI schema and assert the standard
  response envelope (`data`/`meta`/`error`) shape; fail on unintended drift.
- **Frontend:** integration render of the app against a **mocked API** (MSW) —
  create-workspace flow, sidebar↔panel active-state sync, reconnect overlay.

### 4.4 Tier 3 — End-to-end (`e2e`)

Proves the apps work **together** as shipped — UI → API → WebSocket → terminal —
with **no real infrastructure**.

- Bring up the full stack (built `ui` served by nginx + `api`) via a CI compose
  file.
- The API runs with a **`FakeComputeProvider`** (in-memory; no Proxmox) and a
  **stub ttyd** so a "workspace" is a local echo terminal. This is the seam that
  lets e2e run hermetically in CI.
- **Playwright** drives a real browser through the primary journeys: create a
  workspace (watch the create-saga checklist advance), see the terminal panel
  connect and echo input, split/drag/resize panels, detach → reconnect, and
  terminate. Assert UI state and the `/api/v1` calls behind each action.
- Artifacts (Playwright trace, video, screenshots) are uploaded on failure.

> **Out of scope for CI, by design.** Real Proxmox clone/start/destroy, real
> cloud-init env injection, real worker boot, and real `cc-worker-config` pulls
> are validated in the **dev environment**, not in CI. CI's contract is "the
> images build cleanly and the apps talk to each other correctly."

### 4.5 Tier 4 — Container smoke (`image-scan` / build job)

After each image builds: start the container and assert it comes up healthy
(`api`: `/health` returns ok; `ui`: serves `index.html` and proxies are wired),
then run the image security scan (§5.2). A container that won't start, or that
fails the vuln gate, fails the build.

### 4.6 Regression & flake policy

- **Every bug fix ships with a failing-first test** added to the appropriate
  tier; it stays forever. This is the regression suite — distributed across
  Tiers 1–3, not a separate job.
- **Zero-tolerance for known flakes** in required jobs: a flaky test is quarantined
  (marked, tracked as an issue) rather than retried blindly, so a green check
  always means something.

---

## 5. Supply-chain hardening (full)

Applied primarily in `release.yml`, with the scanning/SAST/secret gates also on
every PR.

### 5.1 Code & dependency scanning (PR + schedule)

- **SAST:** **CodeQL** for `python` and `javascript-typescript` on PRs and a
  weekly schedule.
- **Dependency review:** `actions/dependency-review-action` blocks PRs that add
  vulnerable or license-incompatible dependencies.
- **Dependency audit:** `pip-audit` / `uv` audit (api) and `npm audit` (ui) as
  required jobs; **Dependabot** for automated dependency + GitHub Actions bumps.
- **Filesystem scan:** **Trivy** (or Grype) scans the source tree for vulnerable
  manifests and misconfigurations.

### 5.2 Image scanning

- **Trivy/Grype** scan each built image; **fail on HIGH and CRITICAL** with no
  available fix-suppression unless explicitly waived in a tracked allowlist with
  an expiry.
- Results uploaded as **SARIF** to GitHub code scanning for a single audit view.

### 5.3 Secret scanning

- **gitleaks** as a required CI job **and** a `pre-commit` hook (open-items §5).
- GitHub **secret scanning + push protection** enabled on the repo.
- Reinforces `SECURITY.md`: no real secrets in code, fixtures, or images;
  `.env` is gitignored, `.env.example` is the only template.

### 5.4 SBOM, signing & provenance (publish path)

For every image published to GHCR:

- **SBOM:** generate with **syft** in SPDX + CycloneDX, attach to the image and
  the GitHub Release.
- **Signing:** **cosign keyless** (Sigstore, GitHub OIDC) signs the image by
  digest — no long-lived keys.
- **Provenance attestation:** emit a **SLSA build-provenance attestation**
  (`actions/attest-build-provenance`) and an SBOM attestation, both bound to the
  image digest, so consumers can verify *what* built the image and *from which
  source*.
- **Verification:** document the `cosign verify` / `gh attestation verify`
  invocation in the release notes / runbook so downstream users (and auditors)
  can check signatures and provenance.

### 5.5 Runner & token hardening

- All third-party actions **pinned to a full commit SHA**.
- Per-job `permissions:` blocks; the workflow default is `contents: read`. The
  publish job adds exactly `packages: write`, `id-token: write` (keyless signing
  + OIDC), and `attestations: write`.
- Publishing is gated to the default branch / release tags and to a protected
  GitHub **Environment** (optional manual approval) — fork PRs can never push or
  read publish credentials.
- `egress-policy: block` via a hardened runner (e.g. step-security/harden-runner)
  with an allowlist, optional but recommended.

---

## 6. Release & versioning

- **Conventional Commits** drive versioning. A release automation tool
  (release-please or semantic-release) opens a release PR; merging it tags
  `vX.Y.Z` and publishes a GitHub Release with generated notes.
- The `v*` tag triggers `release.yml`, which builds, scans, SBOMs, signs,
  attests, and pushes the versioned + `latest` images (§2.4).
- `CHANGELOG.md` is generated from commit history; the release notes link the
  image digests and their SBOM/attestation.
- Pre-1.0, breaking changes bump the minor; this is documented in `CONTRIBUTING.md`.

---

## 7. Compliance mapping (generic)

Burrow is licensed for anyone to self-host; this maps pipeline controls to the
common framework families operators ask about, so a deployer can inherit the
evidence. (Generic guidance, not a certification.)

| Control area | How the pipeline addresses it |
|---|---|
| Change management / approvals | Branch protection, required reviews, required green checks, squash-merge with traceable Conventional Commits |
| Secure SDLC / SAST | CodeQL, lint/type gates, coverage gate |
| Vulnerability management | Dependency review + audit, Trivy/Grype fs + image scans, Dependabot, SARIF in code scanning |
| Secrets management | gitleaks (CI + pre-commit), push protection, `.env` discipline per `SECURITY.md` |
| Supply-chain integrity | SBOM (syft), cosign signatures, SLSA provenance attestation, SHA-pinned actions, least-privilege tokens |
| Auditability / traceability | Immutable image digests, signed provenance linking image → commit → workflow run, generated changelog |
| Availability of source (AGPL §13) | OCI `image.source`/`.revision` labels point to the exact published commit |

This stays vendor-neutral; deployers map it to their own SOC 2 / ISO 27001 /
PCI DSS control set.

---

## 8. Repo additions (files Claude Code creates)

```
.github/
├── workflows/
│   ├── ci.yml
│   ├── release.yml
│   ├── codeql.yml
│   ├── dependency-review.yml
│   └── scorecard.yml
├── dependabot.yml
└── CODEOWNERS

Dockerfile.api                 # multi-stage FastAPI image
Dockerfile.ui                  # multi-stage Vite build → nginx
.dockerignore
docker-compose.dev.yml         # local dev (already in tech-spec §4.1)
docker-compose.e2e.yml         # CI full-stack: api(FakeComputeProvider)+ui+stub ttyd

.pre-commit-config.yaml        # ruff, biome, gitleaks, conventional-commit, SPDX (open-items §5)

api/
└── tests/
    ├── unit/                  # Tier 1
    └── integration/          # Tier 2 (real SQLite, mocked Proxmox, stub ttyd)

ui/
├── src/**/*.test.tsx          # Tier 1 (vitest)
└── tests/
    ├── integration/          # Tier 2 (MSW)
    └── e2e/                   # Tier 3 (Playwright specs)
playwright.config.ts
```

Test config lives with each app: `pytest`/coverage settings in
`api/pyproject.toml`; `vitest` config in `ui/`. Every file added carries the
SPDX header.

---

## 9. Open questions (resolve at kickoff)

1. **Runtime base for `burrow-api`:** `python:3.12-slim` (simplest) vs distroless
   (smaller attack surface, harder to debug). Recommendation: start slim, move to
   distroless once the runtime deps are stable.
2. **Release automation tool:** release-please vs semantic-release. Either works;
   pick one and wire it once CI exists.
3. **Coverage thresholds:** confirm the starting line/branch percentages and the
   ratchet policy per app.
4. **Vuln waiver policy:** define the allowlist format + required expiry/owner for
   any HIGH/CRITICAL finding that can't be fixed immediately.
5. **Hardened-runner egress allowlist:** decide whether to adopt
   harden-runner now and seed its allowlist, or defer to post-MVP.

> Per project convention (`open-items.md`), don't silently implement around these
> — surface and decide first.
