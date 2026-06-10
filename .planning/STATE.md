---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 00-04-PLAN.md (static CI gates CICD-01 + REUSE/SPDX CICD-06 + minimal ui/ scaffold)
last_updated: "2026-06-10T05:43:19.852Z"
last_activity: 2026-06-10
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 7
  completed_plans: 6
  percent: 86
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
Plan: 6 of 7 complete in current phase
Status: Executing
Last activity: 2026-06-10 — Plan 00-04 complete: Tier-0 static CI gates (CICD-01) + repo-wide REUSE/SPDX compliance (CICD-06) + minimal ui/ scaffold. `.github/workflows/ci.yml` static-gates job runs every gate (ruff lint+format, mypy --strict, uv lock --check, tsc --noEmit, biome ci, reuse lint) with SHA-pinned actions + least-privilege permissions, plus a Conventional-Commit PR-title gate. `LICENSES/AGPL-3.0-or-later.txt` + a precisely-scoped `REUSE.toml` (non-headerable files only) make `uvx reuse lint` green at 100/100. ui/ scaffold pins typescript@6.0.3 + @biomejs/biome@2.4.16 (fresh Biome 2 config); npm ci + tsc + biome all green. CICD-01/CICD-06 complete.

Progress: [█████████░] 86%

## Performance Metrics

**Velocity:**

- Total plans completed: 5
- Average duration: 17 min
- Total execution time: 1.43 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 5 | 86 min | 17 min |

**Per-plan:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 0 P06 | 35 min | 4 tasks | 7 files |
| Phase 0 P07 | 20 min | 3 tasks | 4 files |
| Phase 0 P02 | 11 min | 3 tasks | 10 files |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 0 P04 | 20 min | 3 tasks | 22 files |

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
- [Plan 00-07]: Golden-template shell artifacts authored from the SC-corrected RESEARCH skeletons, NOT the tech-spec §9.3 snippet (its --once and --interface lo are both SC-reversed). burrow-boot.sh ttyd is FROZEN: --port 7681 --writable --interface 0.0.0.0, NO --once (SC-8 persistent) + LAN bind (SC-9 / WORK-04). Pull-at-boot is a documented TODO(Phase 3) stub; no secret is written to /etc/burrow/worker.env (SC-4). WORK-01/WORK-04 script half done; real-template build/boot is the dev-homelab gate.
- [Plan 00-07]: Unit-location conflict resolved — burrow-worker.service canonicalized under cc-worker-config/systemd/ (Plan 00-07, most-recent-doc-wins) rather than worker-template/ where 00-06's 20-create-template.sh expected it; 20-create-template.sh's WORKER_UNIT repointed at the systemd/ path.
- [Plan 00-02]: ComputeProvider ABC exposes the COMPLETE Phase-1 saga method set + typed ComputeError hierarchy; the surface is frozen before the saga is written (PLAT-07, SC-13).
- [Plan 00-02]: FakeComputeProvider is in-memory + deterministic (IP=10.99.0.<vmid%256>, no random/sleep), lifecycle-accurate, with an injectable FakeFailures(raise_on_nth_call) hook shaped for Phase-1 compensation tests (PLAT-08).
- [Plan 00-02]: Scoped mypy override module='proxmoxer.*' ignore_missing_imports (no py.typed) keeps --strict on all first-party code; proxmoxer stays confined to proxmoxProvider.py.
- [Plan 00-02]: SQLite columns are camelCase (tech-spec §7.1 verbatim); snake<->camel bridge lives ONLY in sqliteProvider.py. 001_init.sql omits the UNIQUE(vmid) partial index (Phase-1 002_* migration, SC-4).
- [Phase ?]: [Plan 00-04]: Tier-0 static-gates CI job (CICD-01) runs ruff lint+format, mypy --strict, uv lock --check (api/), tsc --noEmit + biome ci (ui/), uvx reuse lint (repo); third-party actions SHA-pinned (checkout v4.3.1, setup-uv v6.8.0, setup-node v4.4.0), contents:read. PR-title gate via amannn/action-semantic-pull-request with placeholder SHA + '# TODO pin exact SHA' (exact pin deferred).
- [Phase ?]: [Plan 00-04]: REUSE/SPDX green repo-wide (CICD-06, 100/100) via LICENSES/AGPL-3.0-or-later.txt + REUSE.toml scoped to non-headerable files ONLY (uv.lock, package-lock.json, comment-less JSON, design/Burrow-handoff bundle) -- never blanket-globs source extensions so a missing inline header still fails. Headerable sources got inline headers; in-body example SPDX strings wrapped in REUSE-IgnoreStart/End.
- [Phase ?]: [Plan 00-04]: ui/ scaffold minimal-by-design (typescript@6.0.3 + @biomejs/biome@2.4.16 only); full UI tree is Phase 2. biome.json written fresh from biome init (2.4.16 schema); vcs.useIgnoreFile=false, includes scoped to src/**.

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

Last session: 2026-06-10T05:41:26.949Z
Stopped at: Completed 00-04-PLAN.md (static CI gates CICD-01 + REUSE/SPDX CICD-06 + minimal ui/ scaffold)
Resume file: None
Next plan: 00-02 (provider seams: ComputeProvider/DbProvider ABCs + FakeComputeProvider + Sqlite/Postgres + Proxmox skeleton) — wave-1 sibling, no remaining dependency.
