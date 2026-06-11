<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 4
slug: hardening-release
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (`api/`) + vitest (`ui/`) + Playwright (`ui/` e2e over Fake) |
| **Config file** | `api/pyproject.toml`, `ui/vitest.config.ts`, `ui/playwright.config.ts` |
| **Quick run command** | `cd api && uv run pytest tests/unit -q` · `cd ui && npm run test -- --run` |
| **Full suite command** | `cd api && uv run pytest -q` · `cd ui && npm run test -- --run && npm run test:e2e` |
| **Estimated runtime** | api ~30s; ui unit ~10s; e2e ~1-2 min |

Reconciler/auto-stop/capacity tests run hermetically over the Fake provider with an
injected `now` and a single `reconcile_once()` pass (no real clock, no Proxmox). The
capacity race is asserted deterministically via `asyncio.gather` of two concurrent
creates against a Fake whose `getNodeMemory` flips above threshold after the first.
Supply-chain gates split into CI-asserted (Dockerfile build, non-root/HEALTHCHECK
assertions, Trivy fail-on-HIGH/CRITICAL, workflow YAML lint) vs registry/homelab-only
(actual GHCR push, cosign verify against a published digest) — the latter are human/CD.

---

## Sampling Rate

- **After every task commit:** `cd api && uv run pytest tests/unit -q` (or `cd ui && npm run test -- --run` for UI tasks)
- **After every plan wave:** full api suite + ui unit + e2e
- **Before `/gsd:verify-work`:** full suites green
- **Max feedback latency:** ~30s (api), ~10s (ui unit)

---

## Per-Task Verification Map

> Populated/confirmed by the planner; each task maps to an automated command or a Wave-0
> stub. Real-Proxmox reaper/auto-stop/capacity acceptance + real-GHCR publish are manual
> (dev-homelab / CD), see Manual-Only.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD reconciler | — | — | CAP-02, CAP-03 | T-04-* | reaper only touches pool VMIDs w/ no live owner; redacted reaper.* events | unit | `cd api && uv run pytest tests/unit -q` | ❌ W0 | ⬜ pending |
| TBD capacity race | — | — | CAP-02 | T-04-* | two concurrent creates cannot both pass the node check | unit | `cd api && uv run pytest tests/unit -k capacity -q` | ❌ W0 | ⬜ pending |
| TBD event drawer | — | — | UI-06 | — | redacted data rendered as-is; boot.error emphasized | unit+e2e | `cd ui && npm run test -- --run && npm run test:e2e` | ❌ W0 | ⬜ pending |
| TBD images/scan | — | — | CICD-04 | T-04-* | non-root + HEALTHCHECK + digest-pinned; Trivy fails HIGH/CRITICAL | ci/static | `docker build` + `trivy image` (CI) | ✅ | ⬜ pending |
| TBD release supply-chain | — | — | CICD-05 | T-04-* | SBOM + cosign keyless + SLSA provenance; least-priv perms; SHA-pinned actions | ci/static | YAML lint + actionlint (CI) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Reconciler test scaffold: Fake-provider fixtures for an injected orphan CT, a timed-out `creating` row, and an idle workspace; injectable `now`
- [ ] Capacity-race test harness (`asyncio.gather` two concurrent creates; Fake `getNodeMemory` flips after first)
- [ ] UI drawer test scaffold (vitest component + a Playwright e2e opening the drawer over the Fake/stub)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reaper destroys a real injected orphan LXC + frees its VMID on the homelab | CAP-03 | Requires real Proxmox; CI is hermetic over Fake | Inject an orphan CT in the pool, run a reconcile pass, confirm it is destroyed and the VMID freed; out-of-pool CTs untouched |
| Idle workspace auto-stops on the homelab after the real window | CAP-02 | Real worker + real terminal lifecycle | Boot a workspace, disconnect the terminal, wait the window, confirm auto-stop with `reason: idle` |
| Capacity holds under real concurrent creates on a real node | CAP-02 | Real node memory | Fire concurrent creates near the threshold; confirm no overcommit |
| Image actually publishes to GHCR; cosign verify against the published digest | CICD-05 | Requires GHCR push + Sigstore/OIDC in CD | Tag `v*`/publish release; confirm GHCR image, `cosign verify`, SBOM + provenance attached |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (api)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-11
