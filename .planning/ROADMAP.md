<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)

Full v1.0 detail is archived at [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md);
requirements at [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md); the
close-out audit at [`milestones/v1.0-MILESTONE-AUDIT.md`](milestones/v1.0-MILESTONE-AUDIT.md).

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

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 0. Contracts, Seams & Golden Template | v1.0 | 7/7 | Complete | 2026-06-10 |
| 1. Control Plane API | v1.0 | 5/5 | Complete | 2026-06-10 |
| 2. Terminal Proxy + React UI | v1.0 | 6/6 | Complete | 2026-06-10 |
| 3. Reproducible Workers | v1.0 | 3/3 | Complete | 2026-06-11 |
| 4. Hardening & Release | v1.0 | 5/5 | Complete | 2026-06-11 |
