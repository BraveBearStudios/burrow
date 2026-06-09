<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.
**Current focus:** Phase 0 — Contracts, Seams & Golden Template

## Current Position

Phase: 0 of 4 (Contracts, Seams & Golden Template)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-06-09 — Roadmap created (5 phases); Proxmox priming gap closed (added SETUP-01..05, 53/53 mapped)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: - min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Seams-first build — provider ABCs + FakeComputeProvider + envelope land in Phase 0 so ~80% of the backend is CI-green before any real Proxmox call.
- [Roadmap]: Implement the Spec Corrections (SC-1..SC-13), not the spec happy-path — UPID waits, persist-before-clone, race-safe VMID reservation, partial unique index, `tty` subprotocol, persistent ttyd.
- [Phase 0]: Drop ttyd `--once` (SC-8), bind ttyd to the worker LAN interface (SC-9), use `--full` clone — frozen before the template is finalized.
- [Phase 0]: Proxmox priming is a one-time operator kit (`cc-worker-config/lxc/host-prime/` + `PRIMING.md`); least-priv `burrow@pve` role (9 privs) + privsep token scoped to pool/storage/node. See SETUP-01..05 and `research/PROXMOX-PRIMING.md`.
- [Phase 0→1]: Boot config delivered pull-at-boot (recommended) — `pct exec`/`pct push` are not in the HTTPS API; `injectBootConfig` = DB write + worker fetch from an internal endpoint. WORK-03 reframed; mechanism locked by Phase 0 ADR.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- ADRs required before/within their phase: **Phase 0** — SC-8 (`--once`), SC-9 (ttyd binding), clone-mode `--full`, boot-config-injection mechanism (pull-at-boot recommended), Proxmox ACL scoping (`/pool` vs `/vms`), static-IP-from-VMID; **Phase 3** — B4 plugin cadence; plus the stack-version-bump ADRs (Vite 8, TS 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic 6.2.0, Tailwind v4).
- Real-infra-only validation: Phase 0 template, Phase 1 real-clone create, Phase 3 worker boot cannot be CI-verified — dev-homelab smoke gate is the acceptance authority (the "Looks Done But Isn't" checklist).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-09
Stopped at: Roadmap + STATE created; Proxmox priming folded into Phase 0; REQUIREMENTS.md traceability populated (53/53 mapped)
Resume file: None
