<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Requirements: Burrow — Milestone v1.4 "Ship & Harden"

**Defined:** 2026-07-13
**Core Value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.

> v1.4 consolidates and ships everything in flight. Grounded in the 2026-07-13 loose-thread
> recon (`.planning/` session record), which surfaced three live pipeline blockers, a
> backend-complete-but-UI-less credential store, and a half-configured security posture.
> Decisions locked at definition: cut as **v1.4.0** (reconcile release-please forward); the
> **credential store is now secret-at-rest by design** (ADR-0015 supersedes the old
> `.env`-only posture); a **2nd live worker node is available** for the acceptance capstone
> (item 9 in-scope); **multi-agent workers are research-only** this milestone (no build).

## Milestone v1.4 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase (see Traceability).
Pipeline, security-hygiene, credential-frontend, async-create, and backlog items are
CI-provable / repo-config; the ACC items are operator-run human UAT on real hardware.

### Pipeline & Release Infrastructure (RELX)

- [ ] **RELX-03**: release-please can update its release branch (the active `oss` ruleset excludes `refs/heads/release-please--**`, or the GitHub Actions bot is a bypass actor), so the release PR maintains cleanly and merging it produces a `vX.Y.Z` tag.
- [x] **RELX-04**: `release.yml` builds every GHCR reference from a **lowercased** owner and the SBOM (syft) step authenticates to the registry, so SBOM + cosign keyless sign + SLSA attestation all succeed and published images ship **signed and attested** (not the current unsigned partial-publish).
- [ ] **RELX-05**: CI on `main` passes the Trivy HIGH/CRITICAL gate (green `main` / precondition PC1) via patched base-image digests and/or a reviewed ignore policy for unfixable base CVEs.
- [x] **RELX-06**: Release tags follow semver `vX.Y.Z` owned by release-please; hand-pushed milestone tags no longer trigger `release.yml`, and the stale `1.2.0` release PR is reconciled forward to **v1.4.0**.

### Credential Store — ADR-0015 Completion (CRED)

- [ ] **CRED-01**: The ADR-0015 credential-store backend (PR #3) is merged to a green `main`, and the secret-at-rest docs (ROADMAP / STATE / tech-spec) are reconciled to reference ADR-0015 (no longer assert "no secret-at-rest").
- [ ] **CRED-02**: The operator can set a local admin secret in the setup wizard (`POST /setup/admin-secret`); the credential surface is admin-gated via the `X-Burrow-Admin` header.
- [ ] **CRED-03**: The operator can enter the Proxmox token and GitHub PAT in the wizard and have them **stored encrypted at rest** (Fernet), replacing the current "validated in memory only, never stored" step.
- [ ] **CRED-04**: An admin-gated post-setup Credentials/Settings screen shows credential status (set + last4 + updatedAt) and supports rotation, and never returns a secret value.
- [ ] **CRED-05**: An admin-gated read-only audit view (`GET /setup/audit` + a GUI panel) surfaces the append-only credential audit trail (the write path exists; the read path does not).
- [ ] **CRED-06**: `BURROW_SECRET_KEY` is auto-generated into `.env` on first run when empty (novice-safe), with documented key-loss recovery; a missing/undecryptable key never crashes worker boot.
- [ ] **CRED-07**: A sentinel-through-`/setup/credentials` leak test proves credential plaintext appears in no DB cell, API envelope, or log line (only Fernet ciphertext + a 4-char last4 persist).

### Repo Security Hygiene (SEC)

- [ ] **SEC-01**: `.github/dependabot.yml` configures weekly, grouped version-updates for `pip`/`uv` (`api/`), `npm` (`ui/`), and `github-actions` (`.github/workflows/`).
- [ ] **SEC-02**: Dependabot automated-security-fixes are enabled so vulnerable dependencies get auto-remediation PRs.
- [ ] **SEC-03**: CodeQL SAST runs on the default branch for Python + JavaScript/TypeScript (source SAST, not only Trivy image CVEs), and its first-run findings are triaged/baselined.

### Create UX (UX)

- [ ] **UX-01**: Creating a workspace returns immediately (`202` + the `creating` row) with the boot saga running in a tracked background task, so a slow real boot never `504`s; the UI's existing 3s list poll drives `creating`→`running`/`error`, and the setup-wizard create step no longer blocks.

### Backlog & Robustness (ROB)

- [ ] **ROB-01**: The `_is_running_or_locked` bare `"lock"` substring match (WR-04) is removed (keep the precise `"is locked"`), with a regression test; the already-resolved 07r and WR-02 todos are filed/closed.
- [ ] **ROB-02**: The tautological `worker.env` leak assertion in `test_burrow_boot.py` is replaced with an assertion over files the boot script actually writes (or removed, pointing at the stdout/stderr scrub), and em-dashes in worker-template shell comments are swept.

### Multi-Agent Workers Research (AGENT)

- [ ] **AGENT-02**: A research-first ADR / design contract for running Cursor / Copilot CLI / Codex in workers is produced (no build), and the v1.4 credential seam is confirmed **additive** for future per-agent auth.

### Real-Infra Acceptance Capstone (ACC) — operator-run human UAT on real hardware

- [ ] **ACC-04**: On the homelab, the remaining real-infra lifecycle passes (completing carried v1.3 ACC-01 items 6-11): the reaper destroys a real injected orphan LXC + frees its VMID on a non-default node; idle auto-stop fires after the real `idle_window_s` (a brief reconnect does not trip it); capacity holds under real concurrent creates; real least-loaded node selection lands correctly across **≥2 live nodes**; a persistent workspace survives stop→start with disk + scrollback intact; the reaper never destroys a persistent stopped workspace.
- [ ] **ACC-05**: The GUI credential store is verified live on den01 — migration `004` applies on the real SQLite, a GUI-set Proxmox token applies **without a restart** and survives a restart.
- [ ] **ACC-06**: The first real `v1.4.0` GHCR release is verified live — `cosign verify` + `gh attestation verify` pass against the published `@sha256:` digest (completing carried ACC-03), and harden-runner egress is flipped `audit`→`block` from the green run's discovered allowlist (completing carried ACC-02 item 14).

## Future Requirements

Deferred. Tracked, not in this milestone's roadmap.

### Multi-Agent Workers — build (AGENT)

- **AGENT-03+**: Actually boot Cursor / GitHub Copilot CLI / Codex CLI in workers (agent registry + per-agent secrets seam extending the ADR-0015 store + `WorkspaceCreate` DTO + create-modal picker). *A full milestone of its own; v1.4 produces only the research ADR (AGENT-02).*

### Operator Onboarding (HOST)

- **HOST-01**: Replace PRIMING.md's manual clone-on-node with a GitHub-delivered signed-release fetch + `cosign`/`gh attestation` verify flow (download-then-run pinned to a tag, never `curl|bash` for the privileged step). *Self-contained supply-chain/delivery enhancement; its own onboarding milestone.*

### Persistence v2 (WSX)

- **WSX-05 / WSX-06 / WSX-07**: Snapshots/rollback, CRIU suspend/resume, cross-reboot scrollback. *Deferred from v1.3 (storage backend + `VM.Snapshot` priv + CRIU limits).*

### Hosted Path (CRED)

- **CRED-HOSTED**: Implement the credential-store `DbProvider` methods on `postgresProvider.py` (currently `NotImplementedError` stubs) + the `KmsSecretKeyProvider`. *Hosted multi-tenant path only; the v1 self-host store stays SQLite + `EnvSecretKeyProvider`.*

## Out of Scope

Explicitly excluded. Anti-features belong here with reasoning.

| Feature | Reason |
|---------|--------|
| Building multi-agent workers (Cursor / Copilot / Codex boot) | v1.4 is research-only there (AGENT-02); the build is a full milestone of its own (AGENT-03+). |
| Postgres credential-store implementation | Hosted-path scope; `postgresProvider` keeps the `NotImplementedError` stubs (correct for v1 self-host). Not a silent "done." |
| KMS-backed secret key | `EnvSecretKeyProvider` is the v1 self-host mechanism; `KmsSecretKeyProvider` is a reserved hosted-path seam. |
| Per-repo short-lived PAT minting (A3) | The store serves a single global git token this milestone; per-repo issuance is future work. |
| Host-prime signed-release delivery | Deferred to its own onboarding milestone (HOST-01). |
| Real-Proxmox exercise in CI | CI proves contracts over the FakeComputeProvider + mocked proxmoxer; real-infra validation is the ACC human UAT (ci-cd §4.4). |
| Snapshots / CRIU suspend / cross-reboot scrollback | Deferred to WSX-05/06/07 (storage + `VM.Snapshot` + CRIU limits). |

## Traceability

Finalized by the roadmapper against ROADMAP.md Phases 15-22. Each requirement maps to exactly one
phase; no requirement appears in two phases. The finalized mapping matches the definition-time
proposal one-to-one (the operator-approved 8-phase shape required no reassignment):

| Requirement | Phase | Status |
|-------------|-------|--------|
| RELX-03 | Phase 15 | Pending |
| RELX-04 | Phase 15 | Complete |
| RELX-05 | Phase 15 | Pending |
| RELX-06 | Phase 15 | Complete |
| CRED-01 | Phase 16 | Pending |
| SEC-01 | Phase 17 | Pending |
| SEC-02 | Phase 17 | Pending |
| SEC-03 | Phase 17 | Pending |
| ROB-01 | Phase 17 | Pending |
| ROB-02 | Phase 17 | Pending |
| CRED-02 | Phase 18 | Pending |
| CRED-03 | Phase 18 | Pending |
| CRED-04 | Phase 18 | Pending |
| CRED-05 | Phase 18 | Pending |
| CRED-06 | Phase 18 | Pending |
| CRED-07 | Phase 18 | Pending |
| UX-01 | Phase 19 | Pending |
| ACC-06 | Phase 20 | Pending |
| AGENT-02 | Phase 21 | Pending |
| ACC-04 | Phase 22 | Pending |
| ACC-05 | Phase 22 | Pending |

**Coverage:**

- v1.4 requirements: 21 total
- Mapped to phases: 21 (finalized) ✓
- Unmapped: 0 ✓
- Requirements in two phases: 0 ✓

**Dependency ordering** (recorded by the roadmapper): Phase 16 depends on 15; Phase 18 depends on 16;
Phase 20 depends on 15 + 18; Phase 22 depends on 16 + 18 + 20. Phases 17, 19, 21 are parallelizable
off the earlier work. Phases 15-21 are CI-provable (runner + FakeComputeProvider); Phase 22 is
operator-run human UAT on real Proxmox (acceptance, not code — NOT CI-provable).

**ADRs anticipated** (authored within their phase, `docs/adr/`): ADR-0016 CodeQL/Dependabot
security-posture (Phase 17, only if a baseline deviation is recorded) · ADR-0017 async-202 create +
background-task lifecycle (Phase 19) · ADR-0018 multi-agent worker design contract (Phase 21).
*ADR-0015 (credential store) already authored; Phase 16 reconciles the docs to it.*

---
*Requirements defined: 2026-07-13*
*Last updated: 2026-07-13 — traceability finalized by the roadmapper against ROADMAP.md Phases 15-22 (21/21 mapped, 0 unmapped, no requirement in two phases); the finalized mapping matches the definition-time proposal one-to-one.*
