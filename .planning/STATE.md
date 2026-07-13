---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Ship & Harden
status: planning
last_updated: "2026-07-13T15:10:00.000Z"
last_activity: 2026-07-13
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-13)

**Core value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.
**Current focus:** Phase 15 — pipeline-unblock-green-main (v1.4 roadmap complete; ready to plan)

## Current Position

Phase: 15 — Pipeline Unblock & Green Main (roadmap complete, not yet planned)
Plan: —
Status: Roadmap complete — ready to plan Phase 15 with `/gsd:plan-phase 15`
Last activity: 2026-07-13 — v1.4 roadmap created (Phases 15-22, 21/21 requirements mapped, 0 unmapped)

## Performance Metrics

**Velocity:**

- Total plans completed: 45
- Average duration: 16 min
- Total execution time: 3.50 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 7 | 137 min | 20 min |
| 1 | 5 | 75 min | 15 min |
| 5 | 4 | - | - |
| 6 | 1 | - | - |
| 7 | 1 | - | - |
| 8 | 2 | - | - |
| 9 | 3 | - | - |
| 10 | 4 | - | - |
| 11 | 2 | - | - |
| 12 | 2 | - | - |
| 13 | 4 | - | - |

**Per-plan:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 1 P03 | 11 min | 3 tasks | 8 files |
| Phase 1 P01 | 22 min | 4 tasks | 8 files |
| Phase 0 P06 | 35 min | 4 tasks | 7 files |
| Phase 0 P07 | 20 min | 3 tasks | 4 files |
| Phase 0 P02 | 11 min | 3 tasks | 10 files |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 0 P04 | 20 min | 3 tasks | 22 files |
| Phase 0 P03 | 18 min | 3 tasks | 9 files |
| Phase 01 P02 | 21min | 3 tasks | 4 files |
| Phase 1 P04 | 12 | 3 tasks | 14 files |
| Phase 1 P05 | 9 min | 3 tasks | 5 files |
| Phase 2 P01 | 14 min | 3 tasks | 8 files |
| Phase 2 P02 | 24 min | 3 tasks | 22 files |
| Phase 02 P03 | 16min | 3 tasks | 10 files |
| Phase 2 P04 | 23 | 2 tasks | 11 files |
| Phase 2 P05 | 51min | 3 tasks | 12 files |
| Phase 2 P06 | 35min | 2 tasks | 13 files |
| Phase 3 P01 | 22min | 3 tasks | 9 files |
| Phase 03 P02 | 38min | 2 tasks | 9 files |
| Phase 03 P03 | 9min | 2 tasks | 3 files |
| Phase 04 P02 | 38min | 3 tasks | 5 files |
| Phase 04 P03 | 12 | 3 tasks | 8 files |
| Phase 04 P04 | 41min | 2 tasks | 4 files |
| Phase 04 P01 | 12min | 3 tasks | 5 files |
| Phase 04 P05 | 18min | 1 task | 1 file |
| Phase 5 P01 | 16min | 3 tasks | 7 files |
| Phase 5 P02 | 14min | 3 tasks | 4 files |
| Phase 5 P03 | 9 | 2 tasks | 2 files |
| Phase 7 P01 | 10 | 2 tasks | 4 files |
| Phase 8 P08-01 | 12 | 3 tasks | 4 files |
| Phase 8 P08-02 | 5min | 3 tasks | 3 files |
| Phase 9 P09-01 | 18min | 2 tasks | 7 files |
| Phase 9 P09-02 | 20 | 2 tasks | 5 files |
| Phase 9 P09-03 | 7 min | 2 tasks tasks | 4 files files |
| Phase 10 P01 | 8 | 2 tasks | 2 files |
| Phase 10 P02 | 5 | 2 tasks | 1 files |
| Phase 10 P03 | 17 | 3 tasks | 7 files |
| Phase 10 P04 | 12 | 3 tasks | 3 files |
| Phase 11 P01 | 9 | 3 tasks | 3 files |
| Phase 11 P02 | 4 | 2 tasks | 1 files |
| Phase 12 P01 | 22 | 3 tasks | 11 files |
| Phase 12 P02 | 28min | 3 tasks | 6 files |
| Phase 13 P01 | 18 | 3 tasks | 5 files |
| Phase 13 P02 | 7min | 3 tasks | 5 files |
| Phase 13 P03 | 17 | 3 tasks | 5 files |
| Phase 13 P04 | 14 | 1 tasks | 1 files |
| Phase 14 P01 | 18 | 3 tasks | 3 files |
| Phase 14 P02 | 8min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap v1.4]: v1.4 = an 8-phase milestone continuing the numbering from v1.3 (Phases 15-22), honoring the operator-approved shape exactly. Phase 15 pipeline-unblock-green-main (RELX-03/04/05/06 — oss-ruleset exclusion + lowercase GHCR owner/syft auth + green Trivy main + semver tag scheme); Phase 16 land-credential-backend-reconcile-release-train (CRED-01 — merge PR #3 onto green main + reconcile release-please forward to v1.4.0 + reconcile secret-at-rest docs to ADR-0015 + prune branch); Phase 17 repo-security-backlog-hygiene (SEC-01/02/03 + ROB-01/02); Phase 18 credential-store-frontend-onboarding-key (CRED-02..07 — the ship blocker; backend done, frontend + onboarding key remain); Phase 19 create-ux-async-202 (UX-01, ADR-0017); Phase 20 signed-ghcr-release-harden-runner-block (ACC-06); Phase 21 multi-agent-workers-research-spike (AGENT-02, ADR-0018, research-only no build); Phase 22 live-homelab-acceptance-capstone (ACC-04/05, operator human UAT). **21/21 requirements mapped, 0 unmapped, no requirement in two phases.** The finalized traceability matches the definition-time proposal one-to-one (no reassignment forced).
- [Roadmap v1.4]: Build order is a dependency chain gated on a green pipeline — Phase 15 (green main + signed release path) is the true gating work; everything else lands on top. Phase 16 depends on 15 (PR #3 must merge onto a GREEN main); Phase 18 depends on 16 (the credential backend + migration `004` must be merged before the frontend binds to `/setup/*`); Phase 20 depends on 15 + 18 (v1.4.0 must contain the full credential GUI before the tag is cut); Phase 22 depends on 16 + 18 + 20 (live UAT needs the backend live, the GUI, and the signed release to verify). Phases 17, 19, 21 are parallelizable off the earlier work (disjoint surfaces: `.github/` + backlog nits; the create-saga lifecycle; a research ADR).
- [Roadmap v1.4]: **CI-provable vs human-UAT split — Phases 15-21 are CI/config/code** (proven on the GitHub-hosted runner + the FakeComputeProvider; Phase 20 is CD — the tagged release runs on the runner with on-runner cosign/attestation verify + egress block-flip from telemetry; Phase 21 is a research-only ADR, deliverable is the reviewed ADR-0018 not a green run). **Phase 22 is operator-run human UAT on real Proxmox (acceptance, not code — NOT CI-provable) — flagged so downstream planning treats it as runbook, not feature code.** Context anchoring the plan: ACC-01 items 1-5 (H9 core) already PASSED 2026-07-12 on den01; `actionlint` (carried ACC-02 item 13) already passed on the live runner (run 29221779815); PR #3 (credential backend) is mergeable (+18/0 vs main); the credential-store BACKEND is complete + well-tested (only the frontend + onboarding key remain); ACC-06's live cosign/attestation re-verify against a homelab-pulled image rides along in Phase 22.
- [Roadmap v1.4]: Anticipated ADRs (authored within their phase, `docs/adr/`) — ADR-0017 async-202 create + background-task lifecycle (Phase 19); ADR-0018 multi-agent worker design contract (Phase 21); ADR-0016 CodeQL/Dependabot security-posture (Phase 17, only if a baseline deviation is recorded). ADR-0015 (GUI credential store) already authored — Phase 16 reconciles the ROADMAP/STATE/tech-spec secret-at-rest docs to it (the old "validate-in-memory, `.env`-only, no secret-at-rest" posture is superseded by Fernet-encrypted-at-rest).
- [Roadmap v1.3]: v1.3 = a 5-phase milestone continuing the numbering from v1.2 (Phase 10 persistence data model + reaper carve-out — `003` migration + negative-control reaper test + mocked-proxmoxer integration tier; Phase 11 scrollback restore — worker-side tmux in `cc-worker-config`; Phase 12 setup wizard backend — `testConnection`/`verifyTemplate` + `routers/setup.py`; Phase 13 setup wizard UI + first-run gate; Phase 14 first real-infra acceptance — operator human UAT). 15/15 requirements mapped, 0 unmapped, no requirement in two phases. Phases 10/12/13 are CI-provable over the Fake; Phase 11 is worker-side (CI-provable via the boot harness); **Phase 14 is human UAT on real infra (NOT CI-provable) — flagged so downstream planning treats it as acceptance, not code.** Followed the research-proposed breakdown verbatim — no coverage gap forced a deviation.
- [Roadmap v1.3]: Build order is a dependency chain — Phase 10 is the shared foundation (the `settings` singleton + `persistent` column + reaper carve-out + mocked-proxmoxer tier gate everything persistence/setup-touching). Phase 11 (worker-side, separate `cc-worker-config` repo, zero `api/`/`ui/` change) and Phase 12 (wizard backend) parallelize off Phase 10. Phase 13 (wizard UI) consumes Phase 12's endpoints + Phase 10's `persistent` column. Phase 14 (real-infra acceptance) builds LAST, gated on the wizard + persistence being real and CI-green. TEST-02 (07r e2e nit) is bundled into Phase 10 as test-hardening (no better home; it touches the same stop/start e2e suite Phase 10's persistence work exercises).
- [Roadmap v1.3]: Locked-at-definition decisions carried into the phases — persistence is **opt-in per workspace** (default ephemeral; Tier-1 plain `pct stop`/`start`, NO snapshots/CRIU); the reaper gets a **carve-out + negative-control regression test only** (no new auto-reaping code/TTL); the Proxmox token is **validate-in-memory, `.env`-only** (no secret-at-rest, no token-at-rest ADR). The reaper-destroys-a-persistent-workspace hazard (Pitfall #1) is a hard Phase-10 gate; the Fake-vs-real proxmoxer gap (Pitfall #2) is closed by the mocked-proxmoxer tier BEFORE any persistence-compute change. **(SUPERSEDED for v1.4: the token is now secret-at-rest by design — ADR-0015 Fernet-encrypted credential store; Phase 16 reconciles the docs.)**
- [Roadmap v1.3]: Anticipated ADRs (authored within their phase, `docs/adr/`) — ADR-0011 setup-state store (`settings` singleton + `setupCompletedAt`, Phase 10/12); ADR-0012 new `ComputeProvider` capabilities `testConnection`/`verifyTemplate` with Fake parity (Phase 12); ADR-0013 persistence model (Tier-1 `persistent` flag; snapshots/suspend deferred) (Phase 10); ADR-0014 tmux scrollback in the worker template (Phase 11). Token-at-rest ADR avoided by design.
- [Roadmap v1.2]: v1.2 = a 3-phase milestone continuing the numbering from v1.1 (Phase 7 backlog fixes — UI-12 fast-reconcile + CICD-09 e2e hardening, frontend/test; Phase 8 release hardening — RELX-01 release-please + RELX-02 harden-runner, CI config/docs; Phase 9 auto node selection — WSX-01 backend create-saga + a small create-modal UI touch). 5/5 requirements mapped, 0 unmapped. Every criterion is CI-provable over the Fake provider — no real-Proxmox path. ACC-01/02/03 (real-infra acceptance) + WSX-02/03 (real-boot v2) stay deferred Future Requirements, NOT phases.
- [Roadmap v1.2]: The three phases touch disjoint surfaces (Phase 7 the React app + e2e, Phase 8 `.github/workflows/` + docs, Phase 9 the API create-saga + one create-modal touch) so the inter-phase dependency edges are empty — numeric execution order is 7 → 8 → 9 but all three may be planned/executed in parallel. Phase 9 depends on the v1.0 Phase 1 create saga + Phase 2 create modal / `GET /api/v1/nodes`, not on Phase 7 or 8.
- [Roadmap v1.2]: RELX-01 is LOCKED to release-please (the PROJECT.md Open-Q "release-please vs semantic-release" is resolved — do not propose semantic-release in Phase 8). RELX-02 = `step-security/harden-runner` egress allowlist (audit-then-block) + all third-party actions SHA-pinned; resolves the PROJECT.md "harden-runner: adopt now or defer" open item by adopting it this milestone. WSX-01 node selection must read only the `ComputeProvider` capacity surface (node mem fraction / threshold) — no Proxmox specifics leak past the seam (seam-leakage guard stays green).
- [Roadmap v1.1]: v1.1 = a tight 2-phase polish milestone continuing the numbering from v1.0 (Phase 5 frontend stop/start + drawer polish; Phase 6 CI/tooling robustness). 7/7 requirements mapped, 0 unmapped. Every criterion is CI-provable over the Fake provider — no real-Proxmox path; the v1.0 acceptance debt (ACC-01/02/03) is excluded by design (needs real infra off the dev box).
- [Roadmap v1.1]: Phase 6 (CICD-07/08) has NO dependency on Phase 5 — it touches the CI workflow + tooling/docs only, not the React app — so it may be planned/executed in parallel; numeric execution order is 5 → 6 but the dependency edge is empty.
- [Roadmap v1.1]: Phase 5 builds entirely on the v1.0 surface — WS-06/WS-07 endpoints, the TanStack hooks, the activity drawer, and the four-theme token sheet (incl. `--accent-line`, verified present across all four themes in `docs/design/burrow-ui-mockup.html`) already ship. Stop/Start controls treat the backend state machine as the authority (mirrors the v1.0 SC-12 UI posture); detach-vs-destroy semantics are unchanged (close panel = detach, destroy is the only kill path).
- [Plan 01-01]: 002 partial unique index on `workspaces(vmid) WHERE deletedAt IS NULL AND vmid IS NOT NULL` is the cross-process VMID reservation arbiter (SC-3/SC-4); soft-deleted tombstones and NULL vmids stay out of the index so destroy-then-recreate reuses a vmid. A plain UNIQUE would break recycle.
- [Plan 01-01]: `migrate()` is now an ordered, idempotent `schema_migrations`-ledger runner applying every `migrations/*.sql` by stem — replaces the Phase-0 "skip if workspaces table exists" check that wrongly skipped 002 on an existing DB (Pitfall 6).
- [Plan 01-01]: `VmidTakenError` is discriminated on the SQLite `workspaces.vmid` column phrase, NOT the index name — SQLite reports the violated column for a partial-unique failure, and the 002 index is the only uniqueness on that column. Declared on the DbProvider ABC module so the service catches it without an aiosqlite dep.
- [Plan 01-01]: `getEvents` orders by `(createdAt, rowid)` so two same-millisecond events keep insertion order (deterministic WS-11 oldest-first). `getByVmid` returns the active (non-soft-deleted) vmid owner.
- [Plan 01-01]: All Phase-1 `Settings` keys consolidated in one config.py edit (single-owner file → no cross-plan write conflicts) with safe non-secret placeholder defaults; real LAN/secret values live only in the gitignored `.env` (T-01-22 mitigation).
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
- [Plan 00-07]: Golden-template shell artifacts authored from the SC-corrected RESEARCH skeletons, NOT the tech-spec §9.3 snippet (its --once and --interface lo are both SC-reversed). burrow-boot.sh ttyd is FROZEN: --port 7681 --writable --interface 0.0.0.0, NO --once (SC-8 persistent) + LAN bind (SC-9 / WORK-04). Pull-at-boot is a documented TODO(Phase 3) stub; no secret is written to /etc/burrow/worker.env (SC-4). WORK-01/WORK-04 script half done; real-template build/boot is the dev-homelab gate. **(v1.3 Phase 11 WSX-03 inserts `tmux new-session -A -s burrow` into this same FROZEN ttyd exec line — the only change to it since v1.0.)**
- [Plan 00-07]: Unit-location conflict resolved — burrow-worker.service canonicalized under cc-worker-config/systemd/ (Plan 00-07, most-recent-doc-wins) rather than worker-template/ where 00-06's 20-create-template.sh expected it; 20-create-template.sh's WORKER_UNIT repointed at the systemd/ path.
- [Plan 00-02]: ComputeProvider ABC exposes the COMPLETE Phase-1 saga method set + typed ComputeError hierarchy; the surface is frozen before the saga is written (PLAT-07, SC-13). **(v1.3 Phase 12 SETUP adds two NEW capabilities to this ABC — `testConnection`/`verifyTemplate` — with Fake parity, per ADR-0012.)**
- [Plan 00-02]: FakeComputeProvider is in-memory + deterministic (IP=10.99.0.<vmid%256>, no random/sleep), lifecycle-accurate, with an injectable FakeFailures(raise_on_nth_call) hook shaped for Phase-1 compensation tests (PLAT-08). **(v1.2 Phase 9 WSX-01 auto-select is proven over this Fake's multi-node getNodeMemory capacity — least-loaded-fitting chosen, over-threshold skipped, no-fit refuses. v1.3 Phase 10 adds a mocked-proxmoxer integration tier ALONGSIDE the Fake to close the structural error/UPID-path gap the Fake never triggers.)**
- [Plan 00-02]: Scoped mypy override module='proxmoxer.*' ignore_missing_imports (no py.typed) keeps --strict on all first-party code; proxmoxer stays confined to proxmoxProvider.py.
- [Plan 00-02]: SQLite columns are camelCase (tech-spec §7.1 verbatim); snake<->camel bridge lives ONLY in sqliteProvider.py. 001_init.sql omits the UNIQUE(vmid) partial index (Phase-1 002_* migration, SC-4). **(v1.3 Phase 10 adds a `003` migration — a singleton `settings` table + a `persistent` column on workspaces — through the same ordered ledger. v1.4 Phase 16 lands migration `004` — the ADR-0015 credential store — through the same ledger.)**
- [Phase ?]: Plan 01-04: /api/v1 thin routers (workspaces CRUD + stop/start/destroy/events, templates, degrade-not-500 health) wired via get_service DI; ServiceError/.code + ComputeError mapped to envelope statuses (409/404/502). JSON logging (stdlib JsonFormatter, extra-key whitelist, no secrets), SecurityHeadersMiddleware (4 headers, no HSTS), non-* CORS from Settings (outermost). get_compute is a process-wide singleton so the Fake state survives across requests (Rule 1); DbProvider.listTemplates added (Rule 2). Integration tier (ASGITransport + real temp SQLite + Fake + respx stub-ttyd) proves CRUD/health/security. **(v1.3 Phase 12 adds a `/api/v1/setup/*` router via this same get_service DI + envelope mapping; the wizard health step REUSES this degrade-not-500 /api/v1/health. v1.4 Phase 18 extends `/api/v1/setup/*` with admin-secret + credentials + audit endpoints, admin-gated via `X-Burrow-Admin`.)**
- [Plan 01-03]: lib/statemachine.py is the policy authority — a single TRANSITIONS table + assert_transition called BEFORE every stop/start/destroy mutation; creating is internal-only (never an action target) and error exits only via destroy (A4). **(v1.3 Phase 10 WSX-02 reuses the existing `stopped` state + `stopCt`/`startCt` for persistence — NO new state, NO ComputeProvider ABC change for Tier 1; the reconciler/auto-stop must treat a `persistent` stopped workspace as durable. v1.4 Phase 19 UX-01 keeps `creating` as the initial state but moves the boot saga into a tracked background task so `POST /workspaces` returns 202 immediately.)**
- [Phase 04]: [Plan 04-01]: Reconciler (reaper + idle auto-stop, CAP-02/CAP-03) is one pure `reconcile_once()` over the two seams with an INJECTABLE `now`; `_reap` destroys in-pool CTs with no live DB row under the load-bearing `if vmid in pool` bound; timed-out `creating` rows get destroyCt + status=error. **(v1.3 Phase 10 WSX-04 hard gate: VERIFY this `_reap` predicate keys on "no owning DB row," NOT on `stopped` state, and LOCK it with a negative-control regression test proving a persistent stopped workspace is never reaped — Pitfall #1. v1.4 Phase 22 ACC-04 exercises this reaper live against a real injected orphan on a non-default node.)**
- [Phase 04]: [Plan 04-05]: Release supply-chain workflow (CICD-05). `.github/workflows/release.yml` on `v*` tag / release published: one `publish` job with EXACTLY `contents:read + packages:write + id-token:write + attestations:write` over a two-image matrix; cosign keyless + SLSA attestation, every step bound `@<digest>`. **(v1.3 Phase 14 ACC-03 is the FIRST real exercise of this path — real GHCR push + `cosign verify` + `gh attestation verify` against the published `@sha256:` digest; verify by digest not tag, exactly 4 publish perms. v1.4 Phase 15 RELX-04 FIXES this path — lowercase GHCR owner + syft registry auth so images ship SIGNED (the mixed-case `BraveBearStudios` currently breaks syft → unsigned partial-publish); Phase 20 ACC-06 cuts the first GREEN v1.4.0 signed+attested release + flips harden-runner audit→block.)**
- [Phase 8]: [Plan 08-02]: harden-runner (audit) is the literal step 0 of all four CI/release jobs; every `uses:` across all three workflows (25 refs) is a 40-hex commit SHA. **(v1.3 Phase 14 ACC-02 flips harden-runner egress `audit`→`block` with the discovered allowlist + lands the first live release-please PR; pre-seed Fulcio/Rekor/TUF in the allowlist. v1.4 Phase 20 ACC-06 completes this flip from the green v1.4.0 run's telemetry; Phase 15 RELX-03 first unblocks release-please by excluding its branch from the `oss` ruleset.)**
- [Phase 9]: [Plan 09-03]: NewWorkspaceModal defaults to an Auto (least-loaded) <option value=""> and submits node: null; isValid drops the node requirement. **(v1.3 Phase 13 adds a `persistent` checkbox onto this SAME modal — default unchecked = ephemeral — completing the UI half of WSX-02 against the Phase 10 backend.)**
- [Phase ?]: [Plan 10-01]: TEST-01 hard gate GREEN — mocked-proxmoxer integration tier (api/tests/integration/mock_proxmox.py factories + test_mock_proxmox.py self-tests) drives the REAL ProxmoxComputeProvider through running->stopped UPID polling + ResourceException 404/500 inspector branches the Fake never triggers. responses (NOT respx); 9-segment UPID via make_upid; ResourceException raised via responses body=<exc> to hit _is_not_found/_is_running_or_locked exactly. Unblocks persistence-compute Plans 03/04. **(v1.4 Phase 17 ROB-01 removes the bare `"lock"` substring in `_is_running_or_locked` in favor of the precise `"is locked"`, with a failing-first regression test over this same tier.)**
- [Phase ?]: [Plan 10-02]: TEST-02 / 07r e2e hardening landed in ui/tests/e2e/stop-start.spec.ts. W2: the afterEach now captures the cleanup request.delete and asserts expect([200,404]).toContain(res.status()) so a swallowed teardown fails loudly at root cause instead of leaking Fake state as a downstream flaky order-dependent failure (RESEARCH Pitfall 6); cleanup stays id-scoped over createdIds (no broad wipe). W3: the round-trip asserts toHaveCount(2) over the two Start affordances (header button TerminalPanel.tsx:374-383 + placeholder CTA :461-476) and the placeholder CTA visible in the role=status region, BEFORE the unchanged strict-mode placeholder-scoped Start CLICK. W1 id-tracking + unique-per-run names untouched; suite green 5/5. Test-only edit, independent of the Phase-10 api/persistence plans.
- [Phase ?]: [Plan 10-03]: WSX-02 persistence data model landed. 003 migration adds workspaces.persistent (INTEGER NOT NULL DEFAULT 0; the DEFAULT is mandatory for SQLite ADD COLUMN NOT NULL on a non-empty table and is the v1.2 backfill) plus a singleton settings table (id INTEGER PRIMARY KEY CHECK id=1, setupCompletedAt TEXT, seeded id=1/NULL) through the UNCHANGED schema_migrations ledger. persistent bool=False threads through both DTOs, sqliteProvider SELECT+INSERT (data.get default False), and the create-saga reservation base dict; default create stays ephemeral. Create-time-only (updateWorkspace column_map untouched). ADR-0011 (settings singleton setup-state store, shared with Phase 12) + ADR-0013 (Tier-1 persistence = plain pct stop/start same-VMID disk-preserved; snapshots/CRIU deferred v1.4+) authored. test_migrations.py locks DEFAULT-0 backfill, singleton seed+invariant, fresh==migrated convergence. Full api suite 210 passed.
- [Phase ?]: [Plan 10-04]: WSX-04 reaper carve-out locked — comment-only predicate (unchanged, git-diff verified) + 2 RED-if-regressed negative-control tests (persistent-stopped spared, proven RED by injecting a status==stopped reap then restoring; soft-deleted-persistent reclaimed) + 3 WSX-02 round-trip tests (persistent camelCase round-trip, default ephemeral, stop->start same id/vmid). _create override annotation widened str->object. Full api suite 215 passed.
- [Phase ?]: [Plan 11-01]: WSX-03 tmux scrollback reattach landed. burrow-boot.sh inner ttyd shell now execs tmux new-session -A -s burrow ${CLAUDE_CMD} (one fixed burrow session/worker; -A reattaches to the live session + scrollback on ttyd/web-client reconnect, never respawns on attach). ttyd flags frozen, bash -n clean, relay (api/routers/terminal.py) byte-unchanged (criterion 4). Boot harness asserts tmux new-session/-A/-s burrow in normalized recorded argv (criterion 1) + new test_two_boots_stable_tmux_session proves -A idempotency across two boots (criterion 3); tests/boot green 22 passed. ADR-0014 (ADR-0013 format, no em dashes) records the HONEST contract: reattach-on-reconnect now; cross-reboot scrollback (pipe-pane/CRIU) deferred to v1.4 (WSX-06). tmux binary + /etc/tmux.conf baked by Plan 11-02.
- [Phase ?]: [Plan 11-02]: WSX-03 criterion 2 (worker tmux baseline) landed. provision-template.sh now bakes tmux (unpinned in the apt-install line alongside ttyd/jq; tmux 3.4 / Ubuntu 24.04 recorded in the top-of-file pin comment per the pin-by-comment convention, NOT an apt =version lock) plus a minimal /etc/tmux.conf written via a single-quoted heredoc before the apt-cache clean, containing EXACTLY set -g history-limit 50000 (bounded per-pane scrollback, T-11-03 DoS mitigation) and set -g window-size latest (the single-reconnecting-web-client resize fix) - no mouse/status/theme (YAGNI). SPDX header + set -euo pipefail intact, bash -n clean. Only provision-template.sh touched; relay byte-unchanged (criterion 4). Closes Phase 11 (11-01 wired the tmux new-session -A reattach in burrow-boot.sh; 11-02 bakes the binary + config it execs against). **(v1.4 Phase 17 ROB-02 sweeps em-dashes in these worker-template shell comments + fixes the tautological worker.env leak assertion in test_burrow_boot.py.)**
- [Phase 12]: [Plan 12-01]: Setup caps landed. testConnection validates an operator-typed PVE token via an EPHEMERAL throwaway proxmoxer client over a single read-only GET /access/permissions (never self._api), asserts the host-prime 9-priv BurrowProvisioner set (REQUIRED_PRIVS frozenset), returns ConnectionResult(success, missingPrivileges=sorted(missing)), creates ZERO resources; verifyTemplate is GET-only. proxmox_token_value -> SecretStr (read only via get_secret_value at the proxmoxer boundary; git_credential_token untouched); setup_logging pins proxmoxer/urllib3/requests to WARNING; SetupAuth/SetupUnreachable carry FIXED token-free messages. Fake parity via FakeFailures setup toggles. DbProvider.getSetupState() read-only (setter deferred Phase 13, ADR-0011). Full api suite 228 passed; seam-leakage green. **(v1.4 Phase 18 CRED-03 supersedes the validate-in-memory-only posture — the wizard now STORES the PVE token + PAT Fernet-encrypted at rest via the ADR-0015 store.)**
- [Phase ?]: Phase 12-02: missing-privileges/template-not-found are the cap SUCCESS path (200, success/exists=False); setup error codes reserved for hard failures (unreachable, rejected token)
- [Phase ?]: Phase 12-02: added a leak-free RequestValidationError handler (Rule 2 security) because FastAPI default 422 echoes raw input, leaking the SecretStr token (T-12-04)
- [Phase ?]: Phase 12-02: SETUP-07 sentinel-token leak hard gate locked RED-if-regressed across DB + envelope + logs (proven by a log-the-token regression, then reverted). **(v1.4 Phase 18 CRED-07 EXTENDS this sentinel leak test through `/setup/credentials` — plaintext in no DB cell, envelope, or log; only Fernet ciphertext + a 4-char last4 persist.)**
- [Phase 13]: [Plan 13-01]: SETUP-04/05 backend landed. DbProvider.setSetupCompleted() (ABC @abstractmethod + SQLite impl: UPDATE settings SET setupCompletedAt = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=1 + commit, returns the value via a getSetupState read-back so the envelope matches the row) + GET /api/v1/setup/state (read) + POST /api/v1/setup/complete (get_db + respond envelope, no body/token, idempotent, NO new error code). Idempotency is a plain WHERE id=1 UPDATE (no INSERT, no uniqueness to violate). Reused the existing deletedAt/migrate strftime timestamp shape (no new format). PostgresProvider gained BOTH getSetupState (missing since Phase 12 added it to the ABC) + setSetupCompleted NotImplementedError overrides for ABC parity (Rule 2 — restored hosted-path stub concreteness). 4 integration tests lock state-null -> complete-sets -> state-returns-it -> idempotent over the real-temp-SQLite + Fake app; setup -k 20 passed, full api suite 250 passed; ruff + mypy clean. Unblocks the Phase 13 UI gate (useSetupState/useCompleteSetup, App.tsx first-run gate).
- [Phase ?]: [Plan 13-02]: Setup hooks + persistent checkbox UI landed. useSetup.ts mirrors useWorkspaces.ts (useQuery/useMutation + api() envelope unwrap): useSetupState (queryKey setupState, NO refetchInterval - read on mount + invalidated, not polled), useTestConnection/useVerifyTemplate (mutations to Phase 12 /setup/test-connection + /verify-template), useCompleteSetup (POST /setup/complete, invalidates setupState onSuccess so the gate flips off). The Proxmox token (TestConnectionBody.tokenValue) is a TRANSIENT mutation arg ONLY - never written to query cache/Zustand/localStorage, never logged (T-13-04/T-13-05). setup.ts types the 5 wizard contracts; WorkspaceCreate gained optional persistent?:boolean (mirrors Phase 10 backend). NewWorkspaceModal: native persistent checkbox (default UNCHECKED=ephemeral) after the Node selector, accentColor:var(--accent) green not browser-blue, verbatim copy, wired into createWorkspace.mutateAsync persistent; resets via parent-unmount remount. vitest proves checked->persistent:true + default->not-true (MSW capture). tsc 0, biome clean, full UI suite 119/119. Unblocks 13-03 (App.tsx gate reads useSetupState) + 13-04 (wizard wires the 3 mutations). **(v1.4 Phase 18 CRED-02/03 adds admin-secret + credentials steps to this wizard; the token becomes a STORED credential, not a transient arg.)**
- [Phase ?]: [Plan 13-03]: First-run gate landed. SetupWizard.tsx is the full-page hard gate (role=dialog, aria-modal, aria-label=Set up Burrow, focus-on-mount, Escape-DOES-NOTHING, Enter-submits via an ActiveSubmitContext ref) with 4 auto-advancing steps - connection(useTestConnection)/template(useVerifyTemplate)/health(GET /health both db+compute ok)/create(useCreateWorkspace then useCompleteSetup = complete-AFTER-create). Re-probe derives step from live state via setStep only - NO persisted checkpoint. Mapped token-free errors (setup_unreachable/auth_failed/template_not_found); success=false renders the mono missing-priv list not an err strip. Tokens-only (no hex); gold reserved to StepSpinner; token lives ONLY in step-1 useState, never stored/logged (T-13-07). App.tsx gates on useSetupState: loading-blank / setupCompletedAt==null -> ONLY SetupWizard / set -> normal shell; gate flips off when useCompleteSetup invalidates [setupState]. Rule 1: added a default MSW /setup/state handler (configured Burrow) + awaited the gate in the 4 App-shell tests so the existing <App /> harness stays green. tsc 0, biome clean, full UI suite 125/125. **(v1.4 Phase 19 UX-01: the wizard create step no longer blocks — the async-202 create returns immediately and the 3s poll drives creating->running.)**
- [Phase ?]: 13-04: First-run gate e2e uses walkthrough-first ordering under mode:serial (gate-walk test runs before any test marks the shared setup row complete; configured-skip test runs second and leaves setup complete for sibling suites)
- [Phase ?]: 13-04: Shared-DB e2e determinism via a live-state-guarded gate-visible branch (test.skip when /setup/state already complete, no setup-reset endpoint exists) so the suite is green on a fresh CI DB and a persisted local DB
- [Phase ?]: [Plan 14-01]: ACC-02 automatable slice landed. ci.yml static-gates gains a SHA-pinned fail-fast actionlint gate, but rhysd/actionlint ships NO action.yml (CLI binary repo, verified via API) so a bare uses: rhysd/actionlint@<sha> would fail at runtime; substituted reviewdog/action-actionlint@6fb7acc99f4a1008869fa8a0f09cfca740837d9d (v1.72.0), actionlint's upstream-documented Actions integration, with reporter github-check + fail_level error to make it a real fail-fast gate (its defaults github-pr-check + fail_level none are advisory-only). actionlint RUN deferred to the live Linux runner (unavailable on the Windows dev box, RELX-02); local proof is STRUCTURAL only (parse + SHA-pin + reuse lint clean), NOT a claim it passed locally. All 5 harden-runner steps keep egress-policy: audit with a commented Fulcio/Rekor/TUF/OIDC/GHCR allowlist-prep block pointing at 14-ACCEPTANCE.md audit->block flip. release.yml publish path (4 perms, by-digest, cosign keyless + SLSA attest) byte-unchanged; every uses: across all 3 workflows is a full 40-hex SHA. Phase 14 verification stays human_needed (ACC-01/02/03 real-infra). **(v1.4: actionlint DID pass on the live runner 2026-07-12, run 29221779815 — carried ACC-02 item 13 done; Phase 20 ACC-06 completes the egress audit->block flip.)**
- [Phase ?]: 14-ACCEPTANCE.md references reviewdog/action-actionlint (the action 14-01 actually wired), not the plan's rhysd/actionlint which ships no action.yml
- [Phase ?]: ACC-01/02/03 stay human_needed; the 16-item 14-HUMAN-UAT checklist is all result: [pending], rolled up from Phase 03/04. **(v1.4 update: ACC-01 items 1-5 (H9 core) PASSED 2026-07-12 on den01; items 6-11 carry into v1.4 Phase 22 as ACC-04; the first signed release + egress block-flip carry into Phase 20 as ACC-06.)**

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

- 07r-harden-stop-start-e2e-cleanup (ui/e2e) — 3 Phase-7 review warnings, e2e cleanup robustness. **CLAIMED by v1.3 Phase 10 (TEST-02) — DONE; v1.4 Phase 17 ROB-01 files/closes the todo record.**
- 2026-06-18-support-multiple-ai-coding-agents-in-workers (general) — boot Cursor / GitHub Copilot / Codex in workers, not just Claude Code. **v1.4 Phase 21 (AGENT-02) produces the research-only ADR-0018; the build (AGENT-03+) stays a future milestone.**

### Blockers/Concerns

[Issues that affect future work]

- ADRs required before/within their phase: **Phase 0 — RESOLVED (Plan 00-05):** all eight v1.0 deviation ADRs authored (ADR-0001..0008). **Phase 3 — RESOLVED (Plan 03-03):** B4 plugin cadence → ADR-0009. **Phase 4 — RESOLVED:** in-process reconciler + capacity lock → ADR-0010. **v1.1/v1.2:** no baseline-architecture deviation emerged. **v1.3 — RESOLVED:** ADR-0011 setup-state store, ADR-0012 new ComputeProvider caps, ADR-0013 persistence model, ADR-0014 tmux scrollback. **v1.4 — THREE anticipated:** ADR-0017 async-202 create + background-task lifecycle (Phase 19), ADR-0018 multi-agent worker design contract (Phase 21), ADR-0016 CodeQL/Dependabot security-posture (Phase 17, only if a baseline deviation is recorded) — author each within its phase. ADR-0015 (GUI credential store) already authored; Phase 16 reconciles the docs to it.
- Real-infra-only validation: Phase 0 template, Phase 1 real-clone create, Phase 3 worker boot cannot be CI-verified — dev-homelab smoke gate is the acceptance authority. **v1.3 — Phase 14 was the milestone's real-infra acceptance phase; ACC-01 items 1-5 (H9 core) PASSED 2026-07-12 on den01. v1.4 — Phase 22 is the milestone's explicit real-infra acceptance capstone (ACC-04/05): human UAT on real Proxmox for ACC-01 items 6-11 (2nd live node confirmed for item 9) + a credential-store live smoke on den01 (migration `004` applies, GUI-set token applies without a restart + survives one). It is NOT CI-provable by design — downstream planning must treat it as acceptance/runbook, not feature code. Phase 20 (ACC-06) cuts + verifies the first signed v1.4.0 release on the runner; its live re-verify against a homelab-pulled image rides along in Phase 22.**
- v1.4 gating work (from the 2026-07-13 recon): the THREE live pipeline blockers are the true critical path — (1) the active `oss` ruleset rejects the release-please bot's ref update (Phase 15 RELX-03); (2) the mixed-case `BraveBearStudios` GHCR owner makes syft fail so images ship UNSIGNED, and the SBOM step lacks registry auth (Phase 15 RELX-04); (3) the Trivy HIGH/CRITICAL gate is RED on `main` (Phase 15 RELX-05). Phase 16 (merge PR #3) MUST land on a GREEN main, so Phase 15 gates the whole milestone. The credential-store BACKEND is complete + well-tested (PR #3 mergeable, +18/0 vs main); only the frontend + onboarding key (Phase 18) remain before the v1.4.0 tag (Phase 20) can be cut.
- v1.4 first-signed-release traps (carried from v1.3 Phase 14 runbook): verify by digest not tag; exactly 4 publish perms; `gh attestation verify` can exit-0-on-failure so assert on output; the harden-runner block-flip must pre-seed Fulcio/Rekor/TUF/OIDC/GHCR in the allowlist (Phase 20 ACC-06).

## Deferred Items

Items acknowledged and deferred at the v1.0/v1.1 milestone closes (all by-design real-infra
acceptances — CI never touches real Proxmox; see the milestone audits + each phase's
*-HUMAN-UAT.md). The v1.1 backlog rows were claimed by v1.2; the v1.2-deferred real-infra +
real-boot-v2 rows were claimed by v1.3; the v1.3-carried real-infra items 6-11 + first-signed-release
are now claimed by v1.4 Phases 20 + 22.

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 03 — 03-HUMAN-UAT.md (real worker boot + plugin load smoke) | passed via v1.3 Phase 14 (ACC-01 H9 core, 2026-07-12) | 2026-06-11 |
| uat_gap | Phase 04 — 04-HUMAN-UAT.md (real reaper/auto-stop/capacity + GHCR publish/cosign verify) | reaper/auto-stop/capacity **claimed by v1.4 Phase 22 (ACC-04)**; GHCR publish/cosign **claimed by v1.4 Phase 20 (ACC-06)** | 2026-06-11 |
| verification_gap | Phase 01 — 01-VERIFICATION.md (human_needed; CI-provable saga passed, real Proxmox = smoke) | passed via v1.3 Phase 14 (ACC-01 H9 core) | 2026-06-11 |
| verification_gap | Phases 00/02/04 — human_needed (CI-provable contracts passed; real-infra = dev-homelab smoke) | H9 core passed 2026-07-12; residual reaper/release **claimed by v1.4 Phases 20 + 22** | 2026-06-11 |
| backlog | WR-01 — LeafPanel onTerminalEvent fast-reconcile wiring | claimed by v1.2 Phase 7 (UI-12) — DONE | 2026-06-15 |
| backlog | WR-02 — stop/start e2e hardening (scoped locators + per-test isolation) | claimed by v1.2 Phase 7 (CICD-09) — DONE; todo record filed/closed in v1.4 Phase 17 (ROB-01) | 2026-06-15 |
| backlog | 07r — stop/start e2e cleanup robustness (W1/W2/W3) | claimed by v1.3 Phase 10 (TEST-02) — DONE; todo record filed/closed in v1.4 Phase 17 (ROB-01) | 2026-06-16 |
| release | First real CI run on a live runner (pinned reuse + harden-runner + release-please PR) | actionlint passed 2026-07-12 (run 29221779815); release-please unblock + egress block-flip **claimed by v1.4 Phases 15 + 20** | 2026-06-15 |
| release | Real GHCR release (publish + cosign verify + gh attestation verify) | **claimed by v1.4 Phase 20 (ACC-06)** — the first GREEN signed+attested v1.4.0 release | 2026-06-11 |
| v2 | WSX-02 persistent workspaces (Tier-1 stop/start) | claimed by v1.3 Phase 10 + 13 — DONE (CI); real-infra proof **claimed by v1.4 Phase 22 (ACC-04)** | 2026-06-15 |
| v2 | WSX-03 full scrollback restore (tmux in the worker) | claimed by v1.3 Phase 11 — DONE (CI); real-infra proof **claimed by v1.4 Phase 22 (ACC-04)** | 2026-06-15 |
| v2 | WSX-05/06/07 snapshots / CRIU suspend / cross-reboot scrollback | deferred beyond v1.4 (storage + VM.Snapshot priv + CRIU limits) | 2026-06-24 |
| milestone | AGENT multi-agent workers (Cursor / Copilot / Codex) | v1.4 Phase 21 (AGENT-02) = research-only ADR-0018; the build (AGENT-03+) is a future milestone | 2026-06-24 |

## Session Continuity

Last session: 2026-07-13 — v1.4 roadmap created (Phases 15-22)
Stopped at: roadmap complete, awaiting phase planning
Resume file: None
Next plan: Plan Phase 15 with `/gsd:plan-phase 15` (Pipeline Unblock & Green Main — RELX-03/04/05/06; the true gating work: unblock release-please via the `oss` ruleset, lowercase the GHCR owner + give syft registry auth so images ship signed+attested, green the Trivy HIGH/CRITICAL gate on main, reconcile the tag scheme to semver). Phase 15 gates everything: Phase 16 (merge PR #3) must land on a green main. Phases 17, 19, 21 are parallelizable off the earlier work.

## Operator Next Steps

- Plan Phase 15 with `/gsd:plan-phase 15` (the pipeline-unblock critical path).
