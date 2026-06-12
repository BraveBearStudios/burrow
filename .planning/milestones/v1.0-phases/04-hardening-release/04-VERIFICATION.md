<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
verified: 2026-06-11T21:15:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Real-Proxmox orphan reap (CR-01 node-correctness on live hardware)"
    expected: "An LXC injected into the worker pool on a NON-default node (no owning DB row) is destroyed on its actual node by one reconcile pass; its VMID is freed and reusable; reaper.destroyed logs only on a real destroy."
    why_human: "The Fake models node-scoped DELETE, but only a live Proxmox cluster (cluster/resources cluster-wide scan + nodes(node).lxc.delete) proves the orphan on a non-default node is actually removed, not 404-swallowed. Requires real Proxmox + injected orphan."
  - test: "Real idle auto-stop after the configured window"
    expected: "A running workspace whose last terminal event is a disconnect older than idle_window_s is STOPPED (not destroyed) with workspace.stopped reason=idle; a disconnect/reconnect inside the window does NOT trip it."
    why_human: "Requires a real terminal WebSocket lifecycle + wall-clock window elapse against a live worker; the hermetic test uses an injected clock."
  - test: "Capacity holds under real concurrent creates"
    expected: "Multiple concurrent create requests against a node near its memory threshold cannot both pass the capacity gate and overcommit the node; exactly the safe number succeed."
    why_human: "The asyncio.Lock + deterministic race test prove the in-process serialization, but only real concurrent HTTP creates against real node-RAM readings confirm no overcommit on the homelab."
  - test: "Actual GHCR publish + signature/provenance verify on a real v* tag"
    expected: "After a v* tag, both images push to GHCR by digest; `cosign verify --certificate-identity-regexp ... --certificate-oidc-issuer https://token.actions.githubusercontent.com <digest>` succeeds and `gh attestation verify oci://...@<digest> --owner BraveBearStudios` succeeds."
    why_human: "Needs the live registry + GitHub OIDC + a real tag push; the workflow is structurally correct but the publish + Sigstore/Rekor verification is the CD/first-run authority, not a PR-CI command."
  - test: "Docker image build + Trivy execution in CI"
    expected: "Both Dockerfiles build on the CI runner (Buildx) and Trivy fails the build on HIGH/CRITICAL while uploading a full SARIF to code scanning."
    why_human: "No Buildx/Docker on the Windows dev host; the Dockerfiles + ci.yml are structurally verified (digest pins, non-root, HEALTHCHECK path, push:false, two-run gate), but the actual build+scan is the first-CI-run authority."
---

# Phase 4: Hardening & Release Verification Report

**Phase Goal:** The fleet stays healthy unattended — orphans are reaped, idle workspaces auto-stop, capacity holds under concurrency — and the release path produces signed, attested, scanned images in GHCR.
**Verified:** 2026-06-11T21:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

This phase is `mode: mvp` in ROADMAP.md, but the goal is an outcome statement, not a strict `As a..., I want to..., so that...` User Story. Verification therefore applied the standard goal-backward methodology against the 5 ROADMAP success criteria (the roadmap contract) merged with the 5 PLAN-frontmatter must_have sets. Every CI-provable truth was confirmed in the actual code and by running the real test suites; the only outstanding items are real-infrastructure/CD acceptances that by ROADMAP design are the dev-homelab smoke / first-CI-run authority.

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | A reaper reconciles desired vs actual — destroys pool LXCs with no owning row, frees leaked VMIDs, marks timed-out `creating` rows `error` (destroying their CTs) — verified against an injected orphan | ✓ VERIFIED | `reconciler.py:75-127` `_reap` (pool-range bound `if vmid in pool` at :108; node-correct destroy via `listManagedCts()` at :107-110; timed-out sweep :116-127). Tests `test_reconciler.py` (orphan, off-default-node CR-01, out-of-pool spared, timed-out→error, fresh-spared, no-secret) — 15/15 hermetic tier green. |
| 2 | Idle workspaces auto-stopped as a deliberate lifecycle end, consistent with detach-not-terminate | ✓ VERIFIED | `reconciler.py:130-159` `_auto_stop` keys on last terminal event = `terminal.disconnected` beyond `idle_window_s`, calls guarded `stopWorkspace(reason="idle")`; reconnect re-arms. `stopWorkspace` threads `reason` into `workspace.stopped` data (`workspaceService.py:271-272`). |
| 3 | Per-workspace activity drawer surfaces the full event log; capacity guard tuned so concurrent creates cannot both pass + overcommit | ✓ VERIFIED | Drawer: `ActivityDrawer.tsx` (role=dialog, Esc, focus return, boot.error emphasis), `useWorkspaceEvents.ts` (enabled-gated poll, error backoff), `events.ts` EVENT_BADGE + reaper.* + unknown fallback. Capacity: `workspaceService.py:126,143-148` `_create_lock` spans check+reserve only, released before clone; `test_capacity_race.py` proves exactly one of two concurrent creates passes. UI suite 96/96 green. |
| 4 | CI builds both images multi-stage, digest-pinned, non-root, HEALTHCHECK; scan fails on HIGH/CRITICAL | ✓ VERIFIED (CI-first-run authority for build/scan exec) | `Dockerfile.api` (digest-pinned :14,:39; non-root UID 10001 :56-70; HEALTHCHECK `/api/v1/health` :77-78), `Dockerfile.ui` (digest-pinned, non-root nginx :8080, HEALTHCHECK). `.dockerignore` excludes `.git`/`.env*`/`*.pem`/`*.key`/tests. `ci.yml` build-scan: `push: false` (:153), Trivy gate exit-code 1 on HIGH/CRITICAL (:158-165) + `if: always()` SARIF run + upload (:168-181). |
| 5 | Release path emits SBOM (syft), cosign keyless signature, SLSA provenance, publishes to GHCR with least-priv per-job perms + SHA-pinned actions | ✓ VERIFIED (CD authority for publish/verify) | `release.yml` exactly 4 perms (contents:read, packages:write, id-token:write, attestations:write :44-48); build+push by digest (:90-99); dual SBOM SPDX+CycloneDX (:102-116); cosign keyless by digest (:124-129); SLSA `attest-build-provenance` bound to digest (:134-139); every `uses:` SHA-pinned. |

**Score:** 5/5 truths verified (CI-provable evidence). Real-infra/CD acceptances routed to human verification.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/services/reconciler.py` | reaper + idle auto-stop, injectable now | ✓ VERIFIED | `reconcile_once` → `_reap` then `_auto_stop`; seam-clean (no aiosqlite/proxmoxer); CR-01 + WR-02 fixes present |
| `api/services/workspaceService.py` | `_create_lock` + `stopWorkspace(reason=)` + `_redact_repo` | ✓ VERIFIED | lock :126/:143-148; reason threading :271-272; WR-01 redaction :81-96,:433-435 |
| `api/compute/provider.py` + impls | `listManagedCts()` seam (CR-01) | ✓ VERIFIED | ABC abstract :89; `fakeProvider.py:109-114` (node-honest); `proxmoxProvider.py:149-162` (cluster-wide, real node) |
| `api/main.py` | FastAPI lifespan owns the reconciler | ✓ VERIFIED | `build_reconciler()` from singletons :138-150; `_reconcile_loop` broad-except survives :153-169; clean cancel+suppress :182-188; `lifespan=lifespan` :229 |
| `ui/...ActivityDrawer/useWorkspaceEvents/events` (UI-06) | drawer + gated poll + badge map | ✓ VERIFIED | WR-03 scrim `tabIndex=-1`+`aria-hidden`; WR-04 error backoff; `WorkspaceEvent` camelCase type |
| `Dockerfile.api` / `Dockerfile.ui` / `.dockerignore` | hardened images, secret-free context | ✓ VERIFIED | see SC-4 evidence above |
| `.github/workflows/ci.yml` + `release.yml` | Trivy two-run gate + supply-chain | ✓ VERIFIED | see SC-4/SC-5 evidence above |
| `docs/adr/ADR-0010-...md` | Nygard ADR | ✓ VERIFIED | Status/Context/Decision/Consequences/Revisit; both decisions recorded |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `reconciler._reap` | `compute.destroyCt` | `listManagedCts()` (node,vmid) under pool bound | ✓ WIRED | :107-110 destroys on real node; safety bound :108 |
| `reconciler._auto_stop` | `WorkspaceService.stopWorkspace` | guarded transition reason=idle | ✓ WIRED | :157 |
| `main.lifespan` | `Reconciler` | `asyncio.create_task` on request-path singletons | ✓ WIRED | :181-188 |
| `createWorkspace` | `self._create_lock` | `async with` around capacity guard + reserve | ✓ WIRED | :143-148 |
| `ActivityDrawer` | `/api/v1/workspaces/{id}/events` | `useWorkspaceEvents` enabled-gated poll | ✓ WIRED | hook :26-39 + client reverse |
| `release.yml publish` | GHCR images | `build-push push:true` → digest → sign/attest | ✓ WIRED | :90-139 |
| `release.yml permissions` | cosign + provenance | id-token:write + packages:write + attestations:write | ✓ WIRED | :44-48 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full API suite (reconciler/capacity/lifespan/CR-01 over Fake) | `cd api && uv run pytest -q` | 173 passed in 146s | ✓ PASS |
| Phase-4 hermetic tiers | `cd api && uv run pytest tests/unit/test_reconciler.py tests/integration/test_capacity_race.py tests/integration/test_lifespan.py -q` | 15 passed | ✓ PASS |
| Full UI suite (drawer + a11y + poll-stop) | `cd ui && npm run test -- --run` | 96 passed (14 files) | ✓ PASS |
| Repo-wide SPDX gate | `uvx --with charset-normalizer reuse lint` | 275/275 compliant, REUSE 3.3 | ✓ PASS |
| Docker build + Trivy exec | (Buildx absent on Windows host) | n/a | ? SKIP → human |
| GHCR publish + cosign/attestation verify | (live registry/OIDC) | n/a | ? SKIP → human |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CAP-02 | 04-01, 04-02 | Idle workspaces auto-stopped beyond a window | ✓ SATISFIED | `_auto_stop` + `_create_lock` + reason=idle; reconciler/capacity tests green |
| CAP-03 | 04-01 | Reaper destroys orphaned LXCs + frees leaked VMIDs (SC-9) | ✓ SATISFIED | `_reap` orphan+leaked-vmid+timed-out, pool-bounded, node-correct (CR-01) |
| UI-06 | 04-03 | Per-workspace activity drawer surfaces the event log | ✓ SATISFIED | ActivityDrawer + useWorkspaceEvents + events.ts; 96 UI tests + e2e journey |
| CICD-04 | 04-04 | Multi-stage, digest-pinned, non-root, HEALTHCHECK images; scan fails on HIGH/CRITICAL | ✓ SATISFIED (CI-first-run for exec) | Dockerfiles + .dockerignore + ci.yml build-scan two-run Trivy gate |
| CICD-05 | 04-05 | SBOM + cosign keyless + SLSA provenance → GHCR | ✓ SATISFIED (CD for publish/verify) | release.yml 4-perm, SHA-pinned, dual SBOM, keyless sign, provenance by digest |

No orphaned requirements: REQUIREMENTS.md maps exactly CAP-02, CAP-03, UI-06, CICD-04, CICD-05 to Phase 4, and all five are claimed by a plan's `requirements` field.

### Review-Finding Closure (04-REVIEW.md: 1 blocker + 4 warnings)

| Finding | Severity | Status | Evidence in code |
|---------|----------|--------|------------------|
| CR-01: orphan reaper destroyed against wrong node, logging false success | BLOCKER | ✓ FIXED | `listManagedCts()` seam in ABC + both impls returns `(node, vmid)`; `_reap` destroys on real node (`reconciler.py:107-110`); Fake `destroyCt` models node-scoped 404 (`fakeProvider.py:153-169`); regression `test_reap_destroys_off_default_node_orphan_on_its_actual_node` is a true (non-tautological) test |
| WR-01: `bootconfig.persisted` leaked repo URLs un-redacted to UI | WARNING | ✓ FIXED | `_redact_repo` (`workspaceService.py:81-96`) applied at log site (:433-435); regression `test_bootconfig_persisted_event_redacts_repo_credentials` |
| WR-02: one raising idle-stop aborts the rest of the pass | WARNING | ✓ FIXED | per-stop `try/except IllegalTransitionError: continue` (`reconciler.py:156-159`) |
| WR-03: focus trap escapable via scrim button | WARNING | ✓ FIXED | scrim `tabIndex={-1}` + `aria-hidden="true"` (`ActivityDrawer.tsx:311-312`) |
| WR-04: keeps polling a 404'd/deleted workspace | WARNING | ✓ FIXED | function-form `refetchInterval` backs off on error (`useWorkspaceEvents.ts:35-36`) |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX/placeholder/not-implemented in any phase-modified file | ℹ️ Info | Clean; completion is auditable |

### Human Verification Required

See frontmatter `human_verification`. Five items, all real-infrastructure or first-CI-run authority by ROADMAP design (Infra note: "their true acceptance is the dev-homelab smoke gate, not CI"):

1. **Real-Proxmox orphan reap (CR-01 node-correctness)** — inject an orphan LXC on a non-default node; confirm one reconcile pass destroys it on its real node and frees the VMID.
2. **Real idle auto-stop** — let a real worker's terminal disconnect exceed `idle_window_s`; confirm STOP (not destroy) with `reason=idle`; confirm a reconnect inside the window does not trip it.
3. **Capacity under real concurrent creates** — fire concurrent creates near a node's memory threshold; confirm no overcommit.
4. **GHCR publish + verify** — push a real `v*` tag; run `cosign verify` and `gh attestation verify` against the published digest for both images.
5. **Docker build + Trivy exec in CI** — confirm both images build on the CI Buildx runner and the Trivy gate fails on HIGH/CRITICAL with a SARIF upload.

### Gaps Summary

No gaps. Every CI-provable must-have is verified in the actual code and by running the real suites: 173 API tests pass (incl. the 6 reconciler decisions, the capacity-race, the lifespan start/cancel, and the CR-01 multi-node reap), 96 UI tests pass (incl. drawer a11y + poll-stop), and REUSE lint is 100%. The one review BLOCKER (CR-01) and all four WARNINGs are confirmed fixed in code with backing regressions. The Dockerfiles and both workflows are structurally correct (digest pins, non-root, HEALTHCHECK `/api/v1/health`, `push:false` on PR, exactly four release permissions, SHA-pinned actions, dual SBOM, keyless cosign, SLSA provenance bound to the digest).

Status is `human_needed` (not `passed`) solely because the authoritative acceptance for the runtime-fleet behaviors (real Proxmox reaper/auto-stop/capacity) and the supply-chain publish (real GHCR push + cosign/attestation verify) requires live infrastructure that cannot run in this hermetic/Windows environment — exactly the dev-homelab smoke + first-CI-run authority the ROADMAP designates. No code changes are outstanding.

---

_Verified: 2026-06-11T21:15:00Z_
_Verifier: Claude (gsd-verifier)_
