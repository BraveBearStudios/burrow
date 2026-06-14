<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Requirements: Burrow — v1.1

**Defined:** 2026-06-13
**Milestone:** v1.1 UI Polish + Stop/Start Controls
**Core Value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.

> v1.1 closes the operator-facing tech-debt carried out of the v1.0 close-out audit:
> the backend-ready stop/start lifecycle has no UI surface, the activity drawer lost
> three polish details (04-UI-REVIEW 22/24), and two CI/tooling robustness gaps bite
> on this host. All v1.1 scope is dev-box-buildable and CI-provable over the Fake
> provider — no real-Proxmox path. v1.0 requirements + their archive live in
> `milestones/v1.0-REQUIREMENTS.md`.

## User Stories

- As an operator, I click Stop on a running workspace to free its hardware without destroying it, then Start it later to pick up where the disk left off — instead of waiting for the idle reaper or using the API directly.
- As an operator on my phone, I open the activity drawer and it fills the screen as a readable sheet instead of a cramped fixed-width panel hanging off the edge.
- As an operator navigating by keyboard, I can see which control is focused (accent focus ring) and scroll long surfaces with the styled Burrow scrollbar.
- As a maintainer, `reuse lint` and the GSD phase-plan parser both run clean on this Windows host so CI and planning tooling stop tripping over encoding + SPDX-ordering quirks.

## v1.1 Requirements

Requirements for this milestone. Each maps to a roadmap phase (Traceability below).

### Workspace Lifecycle UI (UI)

The WS-06 (stop) and WS-07 (start) API endpoints + TanStack hooks shipped in v1.0; v1.1 surfaces them as explicit, state-machine-gated controls. The activity-drawer items restore polish dropped in the v1.0 UI review.

- [x] **UI-07**: Operator can stop a running workspace from the UI — a Stop control, enabled only when status is `running`, that calls the WS-06 stop path and reflects the resulting `stopped` state (terminal disconnects, status indicator updates)
- [x] **UI-08**: Operator can start a stopped workspace from the UI — a Start control, enabled only when status is `stopped`, that calls the WS-07 start path (awaits ttyd health) and reflects the resulting `running` state, re-enabling the terminal
- [ ] **UI-09**: The activity drawer renders as a full-width sheet on phone-width viewports (≤375px) instead of the fixed 360px panel, per the V2 responsive-gap finding
- [ ] **UI-10**: Focusable interactive controls show the `--accent-line` focus ring on keyboard focus (V3), restoring the design-system focus affordance
- [ ] **UI-11**: Scrollable drawer (and terminal-adjacent) surfaces use the custom Burrow scrollbar styling (V4) rather than the native scrollbar

### CI / Tooling Robustness (CICD)

- [ ] **CICD-07**: `reuse lint` runs with a pinned encoding dependency (`uvx --with charset-normalizer reuse lint`) in CI and in the documented local command, so it never fails with `NoEncodingModuleError` on Windows / CI runners
- [ ] **CICD-08**: The SPDX-header-before-frontmatter convention is reconciled with the gsd-sdk `phase-plan-index` parser so PLAN `wave` / `depends_on` metadata is read from the YAML (not silently defaulted to wave 1 / no-deps); the chosen convention is documented for future plans

## Future Requirements

Tracked, not in the v1.1 roadmap.

### v1.0 Acceptance Debt (off the dev box — real infra required)

- **ACC-01**: Dev-homelab smoke against real Proxmox — Lane D (H1-H19, headline H9 five-step create→terminal→stop→start→destroy gate; reaper-off-node / idle-auto-stop / capacity halves; Phase-3 boot/credential/plugin confirmations)
- **ACC-02**: First CI run — Lane B (C1 images+Trivy+SARIF, C2 e2e-in-CI, C3 shellcheck + boot/manifest pytest tiers, C4 reuse encoding dep [overlaps CICD-07], C5 SPDX-vs-parser reconcile [overlaps CICD-08])
- **ACC-03**: Real release / CD — Lane C (D1 GHCR publish + `cosign verify` + `gh attestation verify`)

### v2 Candidates (from v1.0 archive)

- **WSX-01**: Auto node selection (capacity-aware / round-robin) instead of manual pick
- **WSX-02**: Persistent / snapshotted workspaces that survive destroy
- **WSX-03**: Full terminal scrollback restore after refresh (requires tmux/zellij in the worker template)
- **RELX-01**: Release automation (release-please or semantic-release)
- **RELX-02**: Hardened-runner egress allowlist (`step-security/harden-runner`)

## Out of Scope

Carried forward from v1.0 — explicit boundaries to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Authentication / login / multi-tenancy / RLS | v1 is LAN-only single-user by design; auth is hosted-path scope (tech-spec §13) |
| Postgres as primary DB | SQLite is the v1 store (ADR-0001); Postgres impl is a stub behind `DbProvider` |
| Cloud / container compute backend | v1 targets Proxmox LXC only; `ComputeProvider` seam exists but no other impl |
| Real Proxmox exercised in CI | CI is hermetic (FakeComputeProvider + mocks); real infra validated in the dev homelab |
| Native mobile app | Browser-first, responsive web only (UI-09 is responsive web, not native) |
| Secrets manager | v1 uses a gitignored `.env`; secrets manager is hosted-path scope |
| Terminal scrollback restore | v2 (WSX-03) — needs a multiplexer in the worker template |

## Definition of Done

v1.1 is releasable when:

- All v1.1 requirements above are implemented and mapped to a completed phase.
- CI is green: static gates (now including the pinned `reuse` encoding dep), unit, integration, e2e (FakeComputeProvider + Playwright), with new/updated tests for the stop/start controls and the drawer-responsive behavior.
- Every new/changed source file carries the SPDX header; any baseline-architecture deviation is recorded as an ADR in `docs/adr/`.
- Affected docs (UI-SPEC / design notes, CLAUDE.md or CONTRIBUTING for the SPDX-vs-parser convention, README if behavior changes) are updated to match shipped reality.

## Traceability

Which phases cover which requirements. **Populated during roadmap creation.**

| Requirement | Phase | Status |
|-------------|-------|--------|
| UI-07 | Phase 5 | Complete |
| UI-08 | Phase 5 | Complete |
| UI-09 | Phase 5 | Pending |
| UI-10 | Phase 5 | Pending |
| UI-11 | Phase 5 | Pending |
| CICD-07 | Phase 6 | Pending |
| CICD-08 | Phase 6 | Pending |

**Coverage:**

- v1.1 requirements: 7 total
- Mapped to phases: 7 (Phase 5: UI-07..UI-11; Phase 6: CICD-07, CICD-08)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-13 for milestone v1.1; mapped to phases 2026-06-13.*
