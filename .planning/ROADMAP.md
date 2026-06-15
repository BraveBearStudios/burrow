<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- ✅ **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (shipped 2026-06-15)

Full v1.0 detail is archived at [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md);
v1.1 at [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md). Requirements + close-out
audits live alongside each in `milestones/`.

## Phases

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
