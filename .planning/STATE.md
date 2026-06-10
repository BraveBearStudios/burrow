---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 00-06-PLAN.md (Proxmox host-prime kit + PRIMING.md, SETUP-01..05 doc/script half)
last_updated: "2026-06-10T03:02:23.503Z"
last_activity: 2026-06-10
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 7
  completed_plans: 3
  percent: 43
---

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
Plan: 3 of 7 complete in current phase
Status: Executing
Last activity: 2026-06-10 — Plan 00-06 complete: re-runnable Proxmox Day-0 host-prime kit (cc-worker-config/lxc/host-prime/ lib/common.sh + 00/10/20/40 scripts + 30-network-notes.md) + PRIMING.md runbook. BurrowProvisioner 9-priv least-privilege role + privsep token to both principals, full secret hygiene, static-IP-from-VMID note, five-step acceptance gate. SETUP-01..05 doc/script half done; real-Proxmox validation deferred to dev-homelab smoke.

Progress: [████░░░░░░] 43%

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: 18 min
- Total execution time: 0.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 3 | 55 min | 18 min |

**Per-plan:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 0 P06 | 35 min | 4 tasks | 7 files |

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
- [Plan 00-01]: Provider switches bind via `Field(validation_alias="BURROW_COMPUTE"/"BURROW_DB")` — a bare field would bind the lowercase env name, not the BURROW_* name (verified with `BURROW_COMPUTE=proxmox`).
- [Plan 00-01]: Single `CamelModel` base (`alias_generator=to_camel`, `populate_by_name`, `from_attributes`) is the sole snake↔camel mechanism; serialize at the boundary with `model_dump(by_alias=True)`. No per-field hand-mapping.
- [Plan 00-01]: Dev deps use PEP 735 `[dependency-groups]` (portable) over uv-specific `[tool.uv] dev-dependencies`.
- [Plan 00-05]: All eight Phase-0 ADRs authored (`docs/adr/ADR-0001..0008`). ADR-0002 locks **pull-at-boot** (Option C — API-only file injection — is impossible; no Proxmox HTTPS API writes a file into a CT rootfs; Option A SSH+`pct push` reserved as a documented fallback). ADR-0003 locks **tight ACL scoping** (`/pool/burrow-workers`+`/storage`+`/nodes`) with the consequence that the clone path must add each new VMID to the pool. ADR-0008 consolidates the stack bumps and records the `tailwind.config.ts` removal (Tailwind v4 is CSS-first via `@tailwindcss/vite`).
- [Plan 00-05]: ADR-0007 satisfies WORK-04's **documentation half** (ttyd LAN bind, security dimension recorded); the implementation/validation half lands with `burrow-boot.sh` (00-07) + dev-homelab smoke, so WORK-04 stays Pending.
- [Plan 00-06]: Host-prime kit authored (cc-worker-config/lxc/host-prime/ + PRIMING.md). BurrowProvisioner = exactly 9 privs; privsep token granted to BOTH user and token at pool/template/storage/node (effective = user-intersect-token); token captured silently, never echoed/CLI-arged, .env write refused unless git check-ignore passes (0600). SETUP-01..05 doc/script half complete; real-Proxmox acceptance deferred to dev-homelab smoke.
- [Plan 00-06]: shellcheck unavailable on the Windows dev host -> scripts validated with bash -n (all pass); shellcheck static analysis unverified, run in CI/homelab. SPDX verified via uvx --with charset-normalizer reuse lint-file.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- ADRs required before/within their phase: **Phase 0 — RESOLVED (Plan 00-05):** SC-8 (`--once`) → ADR-0006, SC-9 (ttyd binding) → ADR-0007, clone-mode `--full` → ADR-0005, boot-config injection (pull-at-boot) → ADR-0002, Proxmox ACL scoping (`/pool` vs `/vms`) → ADR-0003, static-IP-from-VMID → ADR-0004, sqlite-first → ADR-0001, stack-version bumps (Vite 8, TS 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic 6.2.0, Tailwind v4) → ADR-0008. **Still pending: Phase 3** — B4 plugin cadence (boot-time-latest vs snapshot-at-create).
- Real-infra-only validation: Phase 0 template, Phase 1 real-clone create, Phase 3 worker boot cannot be CI-verified — dev-homelab smoke gate is the acceptance authority (the "Looks Done But Isn't" checklist).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-10T03:01:38.728Z
Stopped at: Completed 00-06-PLAN.md (Proxmox host-prime kit + PRIMING.md, SETUP-01..05 doc/script half)
Resume file: None
Next plan: 00-02 (provider seams: ComputeProvider/DbProvider ABCs + FakeComputeProvider + Sqlite/Postgres + Proxmox skeleton) — wave-1 sibling, no remaining dependency.
