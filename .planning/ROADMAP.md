<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- ✅ **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (shipped 2026-06-15)
- 🚧 **v1.2 Backlog Fixes + Release Automation** — Phases 7-9 (in progress)

Full v1.0 detail is archived at [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md);
v1.1 at [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md). Requirements + close-out
audits live alongside each in `milestones/`.

## Overview (v1.2)

v1.2 clears the two deferred v1.1 code-review findings (WR-01 the `LeafPanel`
fast-reconcile, WR-02 the brittle stop/start e2e), hardens the release/CI surface
(release-please automation + a `step-security/harden-runner` egress-locked runner with
SHA-pinned actions), and adds capacity-aware auto node selection at create time. Every
v1.2 requirement is dev-box-buildable and CI-provable over the `FakeComputeProvider` —
there is no real-Proxmox path in this milestone. The carried real-infra acceptance debt
(ACC-01/02/03 — the dev-homelab smoke, the first live CI run, a real GHCR release) and the
real-boot v2 candidates (WSX-02 persistent workspaces, WSX-03 scrollback restore) stay
tracked and deferred: they need real Proxmox / a live runner off the dev box.

## Phases

**Phase Numbering:**

- Integer phases (7, 8, 9): Planned milestone work (v1.2 continues from v1.1's Phase 6)
- Decimal phases (7.1, 7.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 MVP (Phases 0-4) — SHIPPED 2026-06-11</summary>

- [x] Phase 0: Contracts, Seams & Golden Template (7/7 plans) — completed 2026-06-10
- [x] Phase 1: Control Plane API (5/5 plans) — completed 2026-06-10
- [x] Phase 2: Terminal Proxy + React UI (6/6 plans) — completed 2026-06-10
- [x] Phase 3: Reproducible Workers (3/3 plans) — completed 2026-06-11
- [x] Phase 4: Hardening & Release (5/5 plans) — completed 2026-06-11

**Delivered:** a browser-accessible manager for many concurrent Claude Code sessions —
create→boot→live-terminal over both providers (Fake for CI, Proxmox for the homelab), a tiling
xterm/react-mosaic UI with reconnect + restore, reproducible manifest-driven workers with
credential hygiene, an in-process reaper + idle auto-stop + atomic capacity guard, a per-workspace
activity drawer, and a signed/attested/scanned container release path to GHCR. 26 plans; all
CI-provable contracts green over the Fake provider.

**Deferred to the dev-homelab smoke / first CI run / a real GHCR release** (CI never touches real
Proxmox by design — every phase closed `human_needed`): golden-template + real worker boot, real
reaper/auto-stop/capacity acceptance, image build+Trivy on the runner, and a real GHCR publish +
cosign/attestation verify. Tracked per-phase in `*-HUMAN-UAT.md` and in the close-out audit's
`tech_debt`.

</details>

<details>
<summary>✅ v1.1 UI Polish + Stop/Start Controls (Phases 5-6) — SHIPPED 2026-06-15</summary>

- [x] Phase 5: Stop/Start Controls + Drawer Polish (4/4 plans) — completed 2026-06-14
- [x] Phase 6: CI / Tooling Robustness (1/1 plan) — completed 2026-06-15

**Delivered:** explicit, state-machine-gated Stop/Start controls in the workspace UI
(UI-07/UI-08) with a calm `Workspace stopped` placeholder + Start CTA and no optimistic flip
(server-truth poll); the three 04-UI-REVIEW drawer-polish details restored as global CSS
(UI-09 phone full-width sheet via a `--w-drawer` token, UI-10 global `--accent-line`
`:focus-visible` ring, UI-11 custom Burrow scrollbar) across all four themes; and the CI/tooling
robustness fixes (CICD-07 `reuse` pinned to `--with charset-normalizer`; CICD-08 planning
artifacts licensed via REUSE.toml so PLAN frontmatter stays line-1 for the gsd-sdk parser).
5 plans; vitest 113/113 + Playwright e2e 7/7 green over the Fake provider; UI audit 23/24;
`reuse lint` compliant 309/309.

**Deferred (tech_debt, tracked):** WR-01 (LeafPanel fast-reconcile wiring) + WR-02 (e2e
hardening) as backlog todos; first real CI run on a live runner (ACC-02); the carried-forward
v1.0 real-infra acceptance (ACC-01/02/03). See `milestones/v1.1-MILESTONE-AUDIT.md`.

</details>

### v1.2 Backlog Fixes + Release Automation (Phases 7-9)

- [x] **Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening)** - Wire the `LeafPanel onTerminalEvent` fast-reconcile so the workspace list refreshes on a terminal error/close (UI-12), and harden the stop/start Playwright e2e with panel-scoped locators + per-test backend isolation (CICD-09) (completed 2026-06-15)
- [ ] **Phase 8: Release Hardening (release-please + harden-runner)** - Add release-please Conventional-Commit-driven release PRs (RELX-01) and a `step-security/harden-runner` egress allowlist with all third-party actions SHA-pinned (RELX-02)
- [ ] **Phase 9: Auto Node Selection** - Capacity-aware auto node selection at create time — least-loaded node that passes the RAM threshold, proven over the FakeComputeProvider's multi-node capacity, with manual pick retained (WSX-01)

## Phase Details

### Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening)

**Goal**: The operator's workspace list reflects a terminal error/close immediately instead of waiting for the ~3s poll, and the stop/start Playwright e2e is robust to parallelization and multi-panel state so it stops being a flaky gate.
**Depends on**: Phase 6 (builds on the shipped v1.1 surface — the `LeafPanel`/`onTerminalEvent` callback, `useInvalidateWorkspaces`, and the `stop-start.spec.ts` Playwright gate all ship from v1.1; also independent of Phases 8 and 9)
**Requirements**: UI-12, CICD-09
**Success Criteria** (what must be TRUE):

  1. When a workspace's terminal emits an error or close event, the sidebar/status reconciles immediately (`LeafPanel` wires `onTerminalEvent` → `useInvalidateWorkspaces`, the documented Pitfall-4 fast-reconcile) — the operator does not wait for the next ~3s poll tick to see the new status.
  2. A vitest test proves the fast-reconcile path: a simulated terminal error/close event triggers a workspace-list invalidation (not a status mirror), and absent an event the list still falls back to the existing poll.
  3. The stop/start Playwright e2e uses panel-scoped locators only — no unscoped `.first()` and no global count assertions — so it asserts the correct panel's state under a multi-panel layout.
  4. The stop/start e2e has per-test backend isolation (cleanup or DB reset between tests) so the suite is order-independent and survives parallelization without cross-test state bleed.
  5. The full vitest + Playwright suite runs green over the Fake provider + stub ttyd, with the hardened stop/start spec passing repeatably.

**Plans**: TBD
**UI hint**: yes
**Scope note**: Fully CI-provable over the Fake provider (vitest + Playwright + the stub ttyd already in the harness) — no real Proxmox. UI-12 is a frontend wiring + unit-test change; CICD-09 is a test-robustness change to `stop-start.spec.ts` and its harness. Every changed source file carries the SPDX header; the UI-12 regression test lands with the change.

### Phase 8: Release Hardening (release-please + harden-runner)

**Goal**: A merge to main maintains an automated release PR (semantic version bump + generated changelog) that tags `v*` on merge, and the CI workflows run under a locked-down, egress-restricted runner with every third-party action pinned to a commit SHA — so cutting a release is one click and the runner surface is hardened.
**Depends on**: Nothing within v1.2 (independent of Phases 7 and 9; touches `.github/workflows/` + `docs/` only, not the React app or the API). Builds on the existing `ci.yml` / `release.yml` supply-chain surface from v1.0 Phase 4.
**Requirements**: RELX-01, RELX-02
**Success Criteria** (what must be TRUE):

  1. A release-please workflow exists that, from Conventional Commits on main, maintains a release PR with a semantic version bump and a generated changelog, and tags `v*` on merge of that PR (release-please is the chosen tool — not semantic-release).
  2. The release-please config (manifest + config file + workflow) is buildable and lint-clean locally / in the static-gates job — its YAML/JSON validates and `reuse lint` stays green; the first real release PR is the deferred on-runner acceptance.
  3. The CI workflows run under `step-security/harden-runner` with an egress allowlist using an audit-then-block policy, applied to the relevant jobs.
  4. Every third-party action across the touched workflows is pinned to a full commit SHA (including `harden-runner` and the release-please action), with the SHA-pin convention preserved repo-wide.
  5. The harden-runner egress-allowlist policy and the release process are documented (CONTRIBUTING release section and/or a workflow comment) so the maintainer and future contributors can follow them; the first real enforcement is the deferred on-runner run.

**Plans**: TBD
**Scope note**: CI-config + docs only, dev-box-buildable and statically validatable (YAML/JSON parse + `reuse lint`); the live release-please PR and live harden-runner enforcement are the deferred ACC-02 on-runner acceptance, not a PR-CI command. RELX-01 = release-please (locked, do not propose semantic-release). All actions SHA-pinned; SPDX headers on every new/changed file (planning artifacts via REUSE.toml per CICD-08). Any baseline-architecture deviation lands an ADR.

### Phase 9: Auto Node Selection

**Goal**: When the operator creates a workspace without picking a node, the control plane chooses the least-loaded node that still passes the node-RAM capacity threshold — proven over the FakeComputeProvider's multi-node capacity — while manual node pick remains available and the `ComputeProvider` seam stays free of Proxmox specifics.
**Depends on**: Phase 1 (the v1.0 create saga + capacity guard) and Phase 2 (the create modal + `GET /api/v1/nodes` capacity surface). Independent of Phases 7 and 8 within v1.2.
**Requirements**: WSX-01
**Success Criteria** (what must be TRUE):

  1. When the operator creates a workspace and supplies no node, the control plane auto-selects one: it picks a capacity-fitting node (one that passes the node-RAM threshold) and prefers the least-loaded among the fitting nodes.
  2. When no node passes the capacity threshold, auto-select refuses creation with the existing capacity envelope error (no overcommit) rather than forcing a workspace onto an over-threshold node.
  3. Manual node selection still works end-to-end — an operator who picks a node in the create modal gets that node, and the manual path is unchanged.
  4. The selection logic depends only on the `ComputeProvider` capacity surface (node memory fraction / threshold) — no Proxmox-specific type or detail leaks past the seam, and the seam-leakage guard stays green.
  5. Auto-select is proven over the FakeComputeProvider's multi-node capacity with unit/integration tests (least-loaded-fitting node chosen, over-threshold node skipped, no-fit refuses); real multi-node validation is the deferred dev-homelab smoke (ACC-01).

**Plans**: TBD
**UI hint**: yes
**Scope note**: Primarily a backend phase — the create-saga node-selection logic over the two provider ABCs — with one small create-modal UI touch (an "auto / no node" option so the operator can decline a manual pick). CI-provable over the Fake provider's multi-node `getNodeMemory`; no real Proxmox. snake_case DB → camelCase JSON preserved; the `ComputeProvider`/`DbProvider` seams stay abstract. Tests land with the change; SPDX headers on every changed file. A baseline-architecture deviation (if any) lands an ADR.

## Progress

**Execution Order:**
Phases execute in numeric order: 7 → 8 → 9. The dependency edges between them are empty — Phase 7 (frontend/test), Phase 8 (CI config/docs), and Phase 9 (backend + small UI) touch disjoint surfaces and may be planned/executed in parallel.

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 0. Contracts, Seams & Golden Template | v1.0 | 7/7 | Complete | 2026-06-10 |
| 1. Control Plane API | v1.0 | 5/5 | Complete | 2026-06-10 |
| 2. Terminal Proxy + React UI | v1.0 | 6/6 | Complete | 2026-06-10 |
| 3. Reproducible Workers | v1.0 | 3/3 | Complete | 2026-06-11 |
| 4. Hardening & Release | v1.0 | 5/5 | Complete | 2026-06-11 |
| 5. Stop/Start Controls + Drawer Polish | v1.1 | 4/4 | Complete | 2026-06-14 |
| 6. CI / Tooling Robustness | v1.1 | 1/1 | Complete | 2026-06-15 |
| 7. Backlog Fixes (Fast-Reconcile + E2E Hardening) | v1.2 | 1/1 | Complete    | 2026-06-15 |
| 8. Release Hardening (release-please + harden-runner) | v1.2 | 0/? | Not started | - |
| 9. Auto Node Selection | v1.2 | 0/? | Not started | - |
