<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- ✅ **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (shipped 2026-06-15)
- ✅ **v1.2 Backlog Fixes + Release Automation** — Phases 7-9 (shipped 2026-06-16)

Full milestone detail is archived per version in `milestones/`:
[`v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md),
[`v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md),
[`v1.2-ROADMAP.md`](milestones/v1.2-ROADMAP.md). Requirements + close-out audits live
alongside each. Start the next milestone with `/gsd:new-milestone`.

## Phases

**Phase Numbering:**

- Integer phases (7, 8, 9): planned milestone work (each milestone continues the numbering)
- Decimal phases (7.1, 7.2): urgent insertions (marked with INSERTED)

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

<details>
<summary>✅ v1.2 Backlog Fixes + Release Automation (Phases 7-9) — SHIPPED 2026-06-16</summary>

- [x] Phase 7: Backlog Fixes (Fast-Reconcile + E2E Hardening) (1/1 plan) — completed 2026-06-15
- [x] Phase 8: Release Hardening (release-please + harden-runner) (2/2 plans) — completed 2026-06-15
- [x] Phase 9: Auto Node Selection (3/3 plans) — completed 2026-06-16

**Delivered:** the two deferred v1.1 code-review findings closed (UI-12 `LeafPanel
onTerminalEvent` fast-reconcile + CICD-09 panel-scoped stop/start e2e hardening); a release-please
manifest-mode surface (config + manifest seeded 1.1.0 so the first PR proposes v1.2.0, push:main →
release PR → `v*` tag → existing publish) with `step-security/harden-runner` audit step 0 on all 5
CI/release jobs and every `uses:` SHA-pinned to a live-verified upstream commit (RELX-01/RELX-02);
and capacity-aware auto node selection (WSX-01) — `createWorkspace` auto-picks the least-loaded
fitting node via `selectNode` inside `_create_lock` over a `worker_nodes` Settings list and the
shared `_fits` comparator, manual pick unchanged, no-fit refuses with `capacity_exceeded`, modal
defaults to "Auto (least-loaded)". 6 plans; api 202 + ui 117 green, seam-leakage green, every v1.2
requirement CI-provable over the FakeComputeProvider.

**Deferred (real-infra / backlog, tracked):** ACC-01 (dev-homelab smoke incl. real multi-node
auto-select), ACC-02 (first live release-please PR + egress block-flip + full actionlint), ACC-03
(real GHCR publish + cosign/attestation verify), WSX-02/WSX-03 (persistent workspaces + scrollback
restore, real-boot v2), and the 07r e2e-cleanup-robustness nit. See
`milestones/v1.2-MILESTONE-AUDIT.md`.

</details>

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 0. Contracts, Seams & Golden Template | v1.0 | 7/7 | Complete | 2026-06-10 |
| 1. Control Plane API | v1.0 | 5/5 | Complete | 2026-06-10 |
| 2. Terminal Proxy + React UI | v1.0 | 6/6 | Complete | 2026-06-10 |
| 3. Reproducible Workers | v1.0 | 3/3 | Complete | 2026-06-11 |
| 4. Hardening & Release | v1.0 | 5/5 | Complete | 2026-06-11 |
| 5. Stop/Start Controls + Drawer Polish | v1.1 | 4/4 | Complete | 2026-06-14 |
| 6. CI / Tooling Robustness | v1.1 | 1/1 | Complete | 2026-06-15 |
| 7. Backlog Fixes (Fast-Reconcile + E2E Hardening) | v1.2 | 1/1 | Complete | 2026-06-15 |
| 8. Release Hardening (release-please + harden-runner) | v1.2 | 2/2 | Complete | 2026-06-15 |
| 9. Auto Node Selection | v1.2 | 3/3 | Complete | 2026-06-16 |
