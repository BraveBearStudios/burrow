<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Milestones

- ✅ **v1.0 MVP** — Phases 0-4 (shipped 2026-06-11)
- 🚧 **v1.1 UI Polish + Stop/Start Controls** — Phases 5-6 (in progress)

Full v1.0 detail is archived at [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md);
requirements at [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md); the
close-out audit at [`milestones/v1.0-MILESTONE-AUDIT.md`](milestones/v1.0-MILESTONE-AUDIT.md).

## Overview (v1.1)

v1.1 is a tight, focused polish milestone that closes the operator-facing tech-debt
carried out of the v1.0 close-out audit. The backend already ships the WS-06 (stop)
and WS-07 (start) endpoints plus their TanStack hooks; v1.1 surfaces them as explicit,
state-machine-gated controls and restores three drawer-polish details the v1.0 UI
review flagged (04-UI-REVIEW 22/24). Two CI/tooling robustness gaps that bite on this
host are also closed. Every v1.1 requirement is dev-box-buildable and CI-provable over
the `FakeComputeProvider` — there is no real-Proxmox path in this milestone. The v1.0
acceptance debt (real-homelab smoke / first CI run / real GHCR release) is deliberately
excluded: it needs real infra off the dev box and stays tracked as v1.0 debt.

## Phases

**Phase Numbering:**

- Integer phases (5, 6): Planned milestone work (v1.1 continues from v1.0's Phase 4)
- Decimal phases (5.1, 5.2): Urgent insertions (marked with INSERTED)

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

### v1.1 UI Polish + Stop/Start Controls (Phases 5-6)

- [ ] **Phase 5: Stop/Start Controls + Drawer Polish** - Surface the backend-ready stop/start lifecycle as explicit, state-machine-gated UI controls and restore the three drawer-polish details (responsive sheet, focus ring, custom scrollbar)
- [ ] **Phase 6: CI / Tooling Robustness** - Pin the `reuse` encoding dependency and reconcile the SPDX-header-before-frontmatter convention with the gsd-sdk `phase-plan-index` parser

## Phase Details

### Phase 5: Stop/Start Controls + Drawer Polish

**Goal**: The operator can stop and start a workspace directly from the UI, with controls gated by the live state machine, and the activity drawer behaves correctly on a phone-width viewport with the design-system focus ring and custom scrollbar restored.
**Depends on**: Phase 4 (the v1.0 control plane + UI — WS-06/WS-07 endpoints, TanStack hooks, the activity drawer, and the four-theme token sheet all ship from v1.0)
**Requirements**: UI-07, UI-08, UI-09, UI-10, UI-11
**Success Criteria** (what must be TRUE):

  1. The operator clicks Stop on a `running` workspace; the control is enabled only in `running`, calls the WS-06 stop path, and on success the status indicator transitions to `stopped` and the workspace's terminal disconnects.
  2. The operator clicks Start on a `stopped` workspace; the control is enabled only in `stopped`, calls the WS-07 start path (which awaits ttyd health), and on success the status transitions to `running` and the terminal re-enables/reconnects.
  3. The Stop/Start controls treat the backend state machine as the authority — an illegal action (Start on `running`, Stop on `stopped`/`creating`) is not offerable from the UI, and a backend rejection surfaces as a readable envelope error rather than a broken state.
  4. On a phone-width viewport (≤375px) the activity drawer renders as a full-width sheet instead of the fixed 360px panel, and reverts to the 360px panel above that breakpoint (V2 responsive-gap finding).
  5. Keyboard-focusing any interactive control shows the `--accent-line` focus ring (V3) and scrollable drawer/terminal-adjacent surfaces use the custom Burrow scrollbar styling instead of the native one (V4) — both honoring `design/Burrow-handoff/` + `docs/design/` tokens across all four themes.

**Plans**: 4 plans (3 waves)
Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Wave 0 test infra: MSW stop/start handlers + failing-first UI-07..UI-11 tests + e2e scaffold

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 05-02-PLAN.md — Stop/Start controls + stopped placeholder + LeafPanel wiring (UI-07, UI-08)
- [ ] 05-03-PLAN.md — Drawer polish CSS: --w-drawer responsive token, :focus-visible ring, custom scrollbar (UI-09, UI-10, UI-11)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 05-04-PLAN.md — Playwright e2e phase gate: stop->start round-trip + 375px drawer + live focus-ring/scrollbar

**UI hint**: yes
**Scope note**: All five criteria are CI-provable over the Fake provider (vitest + Playwright + MSW) — the stop/start saga, status transitions, and terminal disconnect/reconnect all run against `BURROW_COMPUTE=fake` + the protocol-accurate stub ttyd already in the harness. No real Proxmox is touched. Every changed source file carries the SPDX header; tests land with the change.

### Phase 6: CI / Tooling Robustness

**Goal**: `reuse lint` and the gsd-sdk `phase-plan-index` parser both run clean on this Windows host and in CI, so the SPDX/REUSE gate stops failing on an encoding quirk and PLAN `wave`/`depends_on` metadata is actually read instead of silently defaulted.
**Depends on**: Nothing within v1.1 (independent of Phase 5; touches CI workflow + tooling/docs only, not the React app)
**Requirements**: CICD-07, CICD-08
**Success Criteria** (what must be TRUE):

  1. `reuse lint` runs with a pinned encoding dependency (`uvx --with charset-normalizer reuse lint`) in the CI static-gates job and in the documented local command, and no longer fails with `NoEncodingModuleError` on a Windows / CI runner.
  2. The SPDX-header-before-frontmatter ordering is reconciled with the gsd-sdk `phase-plan-index` parser so a PLAN's `wave` and `depends_on` YAML metadata is read from the frontmatter (not silently defaulted to wave 1 / no-deps), demonstrated on at least one multi-wave PLAN.
  3. The chosen SPDX-vs-frontmatter convention is documented (CLAUDE.md or CONTRIBUTING) so every future PLAN follows it and the parser keeps reading the metadata.

**Plans**: TBD
**Scope note**: Fully CI-verifiable and dev-box-buildable — no infra. SPDX headers and tests (or a verifiable parser/lint check) land with the change.

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 (Phase 6 has no dependency on Phase 5 and may be planned/executed in parallel)

| Phase | Milestone | Plans Complete | Status      | Completed  |
|-------|-----------|----------------|-------------|------------|
| 0. Contracts, Seams & Golden Template | v1.0 | 7/7 | Complete | 2026-06-10 |
| 1. Control Plane API | v1.0 | 5/5 | Complete | 2026-06-10 |
| 2. Terminal Proxy + React UI | v1.0 | 6/6 | Complete | 2026-06-10 |
| 3. Reproducible Workers | v1.0 | 3/3 | Complete | 2026-06-11 |
| 4. Hardening & Release | v1.0 | 5/5 | Complete | 2026-06-11 |
| 5. Stop/Start Controls + Drawer Polish | v1.1 | 1/4 | In Progress|  |
| 6. CI / Tooling Robustness | v1.1 | 0/? | Not started | - |
