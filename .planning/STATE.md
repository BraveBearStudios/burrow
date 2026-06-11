---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 02-06-PLAN.md — the phase e2e gate. Full Playwright journey (create → echo → split/tile → detach→reconnect → terminate) RAN GREEN over Fake + a standalone protocol-accurate stub ttyd; UI-05 restore-after-refresh integration test green; terminate confirm + non-destructive detach wired (Rule 2). Commits f714da1, 8fbd527. Phase 2 (Terminal Proxy + React UI) is now complete (6/6 plans).
last_updated: "2026-06-11T14:11:45.846Z"
last_activity: 2026-06-11 -- Phase 3 planning complete
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 21
  completed_plans: 18
  percent: 60
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-09)

**Core value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.
**Current focus:** Phase 2 — Terminal Proxy + React UI

## Current Position

Phase: 2 of 4 (Terminal Proxy + React UI)
Plan: 6 of 6 complete in current phase
Status: Ready to execute
Last activity: 2026-06-11 -- Phase 3 planning complete

Progress: [██████████] 100% (Phase 2: 6/6 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 13
- Average duration: 16 min
- Total execution time: 3.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 7 | 137 min | 20 min |
| 1 | 5 | 75 min | 15 min |

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

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
- [Plan 00-07]: Golden-template shell artifacts authored from the SC-corrected RESEARCH skeletons, NOT the tech-spec §9.3 snippet (its --once and --interface lo are both SC-reversed). burrow-boot.sh ttyd is FROZEN: --port 7681 --writable --interface 0.0.0.0, NO --once (SC-8 persistent) + LAN bind (SC-9 / WORK-04). Pull-at-boot is a documented TODO(Phase 3) stub; no secret is written to /etc/burrow/worker.env (SC-4). WORK-01/WORK-04 script half done; real-template build/boot is the dev-homelab gate.
- [Plan 00-07]: Unit-location conflict resolved — burrow-worker.service canonicalized under cc-worker-config/systemd/ (Plan 00-07, most-recent-doc-wins) rather than worker-template/ where 00-06's 20-create-template.sh expected it; 20-create-template.sh's WORKER_UNIT repointed at the systemd/ path.
- [Plan 00-02]: ComputeProvider ABC exposes the COMPLETE Phase-1 saga method set + typed ComputeError hierarchy; the surface is frozen before the saga is written (PLAT-07, SC-13).
- [Plan 00-02]: FakeComputeProvider is in-memory + deterministic (IP=10.99.0.<vmid%256>, no random/sleep), lifecycle-accurate, with an injectable FakeFailures(raise_on_nth_call) hook shaped for Phase-1 compensation tests (PLAT-08).
- [Plan 00-02]: Scoped mypy override module='proxmoxer.*' ignore_missing_imports (no py.typed) keeps --strict on all first-party code; proxmoxer stays confined to proxmoxProvider.py.
- [Plan 00-02]: SQLite columns are camelCase (tech-spec §7.1 verbatim); snake<->camel bridge lives ONLY in sqliteProvider.py. 001_init.sql omits the UNIQUE(vmid) partial index (Phase-1 002_* migration, SC-4).
- [Phase ?]: [Plan 00-04]: Tier-0 static-gates CI job (CICD-01) runs ruff lint+format, mypy --strict, uv lock --check (api/), tsc --noEmit + biome ci (ui/), uvx reuse lint (repo); third-party actions SHA-pinned (checkout v4.3.1, setup-uv v6.8.0, setup-node v4.4.0), contents:read. PR-title gate via amannn/action-semantic-pull-request with placeholder SHA + '# TODO pin exact SHA' (exact pin deferred).
- [Phase ?]: [Plan 00-04]: REUSE/SPDX green repo-wide (CICD-06, 100/100) via LICENSES/AGPL-3.0-or-later.txt + REUSE.toml scoped to non-headerable files ONLY (uv.lock, package-lock.json, comment-less JSON, design/Burrow-handoff bundle) -- never blanket-globs source extensions so a missing inline header still fails. Headerable sources got inline headers; in-body example SPDX strings wrapped in REUSE-IgnoreStart/End.
- [Phase ?]: [Plan 00-04]: ui/ scaffold minimal-by-design (typescript@6.0.3 + @biomejs/biome@2.4.16 only); full UI tree is Phase 2. biome.json written fresh from biome init (2.4.16 schema); vcs.useIgnoreFile=false, includes scoped to src/**.
- [Phase ?]: [Plan 00-03]: App factory is the lone composition root — get_compute()/get_db() in main.py are the ONLY place concrete impls are named; BURROW_COMPUTE/BURROW_DB flip the backend with no service edit (both branches verified at runtime).
- [Phase ?]: [Plan 00-03]: Envelope shipped this phase as an ASGI error boundary only (Exception -> respond_error); success-wrapping middleware + routers are Phase 1 per plan.
- [Phase ?]: [Plan 00-03]: Seam-leakage guard uses Python tokenize to drop COMMENT + STRING tokens so seam-contract prose in docstrings is exempt while real driver usage is caught; negative-tested red on an injected leak, green on the tree (PLAT-06/07).
- [Phase ?]: [Plan 01-02]: ProxmoxComputeProvider blocks on every UPID via Tasks.blocking_status (assert exitstatus OK) before returning (SC-1); each proxmoxer call wrapped in asyncio.to_thread so no sync call runs on the event loop (Pitfall 2).
- [Phase ?]: [Plan 01-02]: cloneCt adds the new VMID to /pool/burrow-workers (ADR-0003) and sets net0 static IP from the VMID (ADR-0004) before blocking on the clone UPID; CA-pinned TLS via verify_ssl=proxmox_ca_cert_path, verification never disabled (block_on=high).
- [Phase ?]: [Plan 01-02]: proxmoxer's requests leg is mocked with responses (NOT respx, which is httpx-only); respx reserved for the httpx ttyd-health leg in Plan 04. destroyCt is idempotent (404 -> no-op success) for compensation safety.
- [Plan 01-03]: createWorkspace runs the SC-corrected 8-step saga (capacity guard -> reserve VMID + creating row BEFORE clone -> clone -> injectBootConfig -> start -> resolve IP -> ttyd health -> running) over the two provider ABCs only; any post-reservation failure runs idempotent stop+destroy compensation, frees the VMID, logs a redacted boot.error, and lands the row in error (never creating, no orphan) — SC-1/2/11, proven by FakeFailures at clone/start/getIp/ttyd.
- [Plan 01-03]: lib/statemachine.py is the policy authority — a single TRANSITIONS table + assert_transition called BEFORE every stop/start/destroy mutation; creating is internal-only (never an action target) and error exits only via destroy (A4). Illegal transitions raise a typed IllegalTransitionError at the service boundary (WS-09).
- [Plan 01-03]: lib/errors.py service-tier errors each carry a stable .code class attribute (illegal_transition / capacity_exceeded / no_free_vmid / boot_failed / not_found) so the Plan-04 router maps error.code without an isinstance ladder. NoFreeVmidError is a distinct service error (not the compute one) so it carries the policy code.
- [Plan 01-03]: In-flight serialization = a per-workspace asyncio.Lock (lazily created, keyed by id) with the transition read done INSIDE the lock; the DB partial-unique index covers create-create and the in-lock status read-then-act covers stop/destroy double-fire. A cross-process status-CAS UPDATE is deferred to the DB/router layer if --workers >1 is confirmed at deploy (A2).
- [Plan 01-03]: Capacity guard refuses strictly ABOVE the threshold (node mem > 0.80); a node at exactly 0.80 is allowed (boundary-tested). _safe() redacts git/CI tokens, URL userinfo, and long opaque tokens from event/log text and caps length, preserving the exception type for triage (ASVS V7, T-01-09).
- [Phase ?]: Plan 01-04: /api/v1 thin routers (workspaces CRUD + stop/start/destroy/events, templates, degrade-not-500 health) wired via get_service DI; ServiceError/.code + ComputeError mapped to envelope statuses (409/404/502). JSON logging (stdlib JsonFormatter, extra-key whitelist, no secrets), SecurityHeadersMiddleware (4 headers, no HSTS), non-* CORS from Settings (outermost). get_compute is a process-wide singleton so the Fake state survives across requests (Rule 1); DbProvider.listTemplates added (Rule 2). Integration tier (ASGITransport + real temp SQLite + Fake + respx stub-ttyd) proves CRUD/health/security. Full gate green: 94 pytest + ruff + format + mypy --strict + uv lock --check + reuse.
- [Plan 01-05]: GET /api/v1/internal/bootconfig/{vmid} is the phase's one ASVS L1 surface (WORK-03 endpoint contract). vmid is an int path param + an [worker_pool_start, worker_pool_end] gate; out-of-pool → IllegalVmidError → 404 with a generic "Not found." message that never echoes the probe (T-01-17 enumeration resistance). The SAME IllegalVmidError is reused for a source-IP mismatch so out-of-pool / wrong-source-IP / no-workspace are indistinguishable to a prober.
- [Plan 01-05]: Credential issuance is a pluggable seam — WorkspaceService.mint_repo_credential reads the short-lived, repo-scoped settings.git_credential_token (gitignored .env, Plan-01 key) and returns it, or a marked placeholder when unset (A3). NO long-lived PAT is hard-coded; the real issuer (GitHub App installation token / deploy token / ephemeral PAT) is operator config to confirm before Phase 3 wires burrow-boot.sh. The credential is a response-body field ONLY (gitCredential) — never a log extra; a sentinel-token caplog + event-data test proves it appears in zero logs and zero event blobs (T-01-18, block_on=high).
- [Plan 01-05]: Source-IP binding (request.client.host == ws.lxc_ip, ADR-0004) is defense-in-depth, NOT auth — gated off by default (bootconfig_source_ip_check) and pass-through when lxc_ip is unresolved, so it never blocks a legitimate boot and preserves the v1 LAN no-auth posture. WORK-03 endpoint contract done + CI-proven (99 pytest + ruff + format + mypy --strict + reuse + lock); the live burrow-boot.sh consumer pull-step is deferred to Phase 3.
- [Plan 02-01]: The terminal bridge is an OPAQUE, type-preserving relay — forward every frame verbatim (str→send_text, bytes→send_bytes) on BOTH legs, NEVER .encode() (SC-7). It lives OUTSIDE /api/v1 at prefix /ws (CLAUDE.md /ws/* convention). Teardown races the two pump directions under asyncio.wait(FIRST_COMPLETED), cancels + gather(return_exceptions=True)s the loser, and dials upstream with ping_interval keepalive so a dead browser leg can never leave a half-open upstream (T-02-04). Pre-accept access gate (getWorkspace + status==running + lxc_ip) closes 1008 before accept (T-02-02); an explicit Origin gate vs settings.allowed_origin handles CSWSH since Starlette WS bypasses CORS (T-02-03); the upstream URL is built ONLY from the DB row's lxc_ip via a single _ttyd_url() (SSRF, T-02-01); connect/disconnect events carry {} only (T-02-05).
- [Plan 02-01]: The protocol-accurate stub_ttyd_ws fixture (websockets.serve, asserts the tty subprotocol + JSON init, echoes preserving frame type) is what makes the SC-7 bug un-hideable — a bare echo would pass a relay that drops the subprotocol or re-encodes a text frame. Tests redirect the production ws://{lxc_ip}:7681/ws dial at the stub by monkeypatching routers.terminal._ttyd_url (test-only seam; production construction unchanged).
- [Plan 02-01]: GET /api/v1/nodes returns per-node {node, memoryUsedFraction, capacityThreshold, overThreshold} over the Fake's real getNodeMemory fraction — no fabricated "free GB". overThreshold is the strict CAP-01 guard (fraction > threshold; boundary == is NOT over), and capacity_threshold is read LIVE per request. Degrade-not-500 (mirrors health.py): a raising getNodeMemory yields a null fraction + overThreshold=false at HTTP 200, never a 500 oracle (T-02-06). Backend half of UI-04; the UI capacity chip lands in 02-05. Full gate green: 127 pytest + ruff + format + mypy --strict + reuse.
- [Plan 02-02]: UI foundation stands the real Vite 8 + React 19 + Tailwind v4 (CSS-first @theme, no tailwind.config.ts — ADR-0008) project on the bare Phase-0 scaffold. react-mosaic-component pinned EXACT 6.2.0 (no caret) so a future npm install can never resolve the 7.0.0-beta on `latest`; lockfile verified to hold zero 7.x. client.ts (api<T> envelope unwrap + typed ApiError on error!=null), types/workspace.ts (camelCase mirror of the CamelModel JSON: lxcIp/projectRepo/…), and lib/ttyd.ts (the single source of the verified ttyd opcodes + initFrame/inputFrame/resizeFrame) are the importable blueprints every later UI plan consumes without re-deriving the envelope, types, or protocol. The four-theme token sheet is lifted VERBATIM from 02-UI-SPEC; each [data-theme] block defines the full token set so a swap is complete.
- [Plan 02-02]: Fonts ship CDN-free. No woff2 was vendorable at build time (no font package, none in the design bundle, no network), so per the UI-SPEC's sanctioned fallback the --font-* tokens resolve to the _ds system stacks (ui-sans-serif… / ui-monospace…) and the @font-face blocks stay commented; public/fonts/README.md is the drop-in activation contract. The CSP comment + README were reworded to not embed the literal forbidden CDN hostnames because Vite copies public/ into dist/, which would otherwise trip the binding `grep googleapis|gstatic|jsdelivr` assert (UI-SPEC criterion 6). Shipped src/dist are CDN-clean. MSW handlers mock the /api/v1 surface in the {data,meta,error} envelope, wired into tests/setup.ts (listen/reset/close, onUnhandledRequest:error). Green build/tsc/biome (15 files) + 11 vitest; reuse 185/185. App.tsx is an intentional placeholder — the real shell is Waves 2-4.
- [Phase 02]: [Plan 02-03] The MVP terminal slice: useTerminal owns the full xterm.js + WebSocket + FitAddon + ResizeObserver lifecycle in ONE effect with ref-held resources (term/fit/socket/observer/timer) so teardown is idempotent under StrictMode double-mount (flat over 50 mount/unmount cycles, TERM-07). Jittered exponential backoff (min(30000,500*2^n)+random()*250, cap 5, reset on onopen) drives connecting->open->reconnecting->error + reconnectAttempts behind the spec reconnecting overlay; the stop-on-terminal rule does NOT retry on close 1008 or an LXC_NOT_READY frame (TERM-06). A debounced ResizeObserver fits only when visible/non-zero and sends the ttyd '1'+JSON resize frame so the TUI reflows, never stuck 80x24 (TERM-05). ttyd frames are sent as a fresh-ArrayBuffer copy to satisfy the TS6 BufferSource generic.
- [Phase 02]: [Plan 02-03] App kept at ui/src/App.tsx (not the plan's components/App.tsx) so main.tsx's ./App import keeps resolving (Rule-3 blocking). useTerminal exposes an additive reattach() to back the overlay Reattach/Retry buttons. Terminal->list reconciliation is wired via an onTerminalEvent callback the panel hands to queryClient.invalidateQueries(['workspaces']) rather than calling useQueryClient inside useTerminal, keeping the hook provider-free and unit-testable (Pitfall 4). xterm/FitAddon/ResizeObserver are mocked in vitest (jsdom can't lay out xterm) so render/echo/fit/reconnect/dispose are CI-provable with zero real infra; the real ttyd/live-claude echo is the deferred dev-homelab smoke. UI-01 is partial (useWorkspaces poll done; sidebar rows land in 02-05).
- [Phase ?]: [Plan 02-04]: layoutStore is the ONLY persisted client state (zustand persist, partialized to mosaicNode + activeWorkspaceId; status stays in TanStack Query, Pitfall 11). Tree mutations are pure helpers over react-mosaic getLeaves + createBalancedTreeFromLeaves (deep util import to dodge the nested react-dom). reconcile(liveIds) drops gone leaves, rebalances, retargets active id (UI-05).
- [Phase ?]: [Plan 02-04]: react/react-dom 19.2.7 overrides collapse react-mosaic's nested react-dom@18 (else <Mosaic> crashes on ReactCurrentDispatcher); <Mosaic> 6.2.0 bundles its own DndProvider (never double-wrap); Blueprint chrome suppressed via className=burrow-mosaic. Node 25 localStorage shadow fixed by an in-memory Storage polyfill in tests/setup.ts.
- [Phase ?]: [Plan 02-05]: WorkspaceList sidebar + Navbar capacity chips + NewWorkspaceModal + StatusBar + useNodes + the assembled four-theme App shell complete the operator surface (UI-01/03/04). Status discipline is single-sourced in lib/status.ts; four themes in lib/themes.ts (swatch hex is theme-identity DATA, components stay hex-free). Node capacity is the REAL memoryUsedFraction % (no fabricated GB). Boot-progress is COSMETIC over the SYNCHRONOUS create (A3/Pitfall 5) with single-shot submit+mounted guards; async-202+poll deferred. App kept at ui/src/App.tsx (Rule 3). Tests assert real layoutStore state for leak-proof isolation. Gate: 77 vitest + tsc + biome(39) + build + REUSE 212/212 + no CDN/hex.
- [Phase 02]: [Plan 02-06]: The phase e2e gate. The full Playwright journey (create → terminal echoes → split/tile → detach→reconnect → terminate) RAN GREEN locally (21.7s) over BURROW_COMPUTE=fake + a STANDALONE protocol-accurate stub ttyd (api/tests/e2e/stub_ttyd_server.py) — the SAME tty handler the Plan-01 pytest fixture uses, factored into one shared module so a .encode()/subprotocol regression fails BOTH tiers (T-02-07). The stub also answers the create saga's HTTP health GET (websockets process_request → 200) so the synchronous create resolves. A BURROW_E2E_TTYD_HOST override (operator env, NEVER client input — SSRF posture unchanged) retargets the bridge dial + the saga health poll at the single local stub instead of the unroutable 10.99.0.x Fake worker IP. The UI-05 restore-after-refresh integration test (vitest+MSW) proves reconcile (gone leaf dropped) + live reconnect (running panel re-mounts, fresh WS) + NO scrollback (Pitfall 7). DEVIATION (Rule 2): the terminate confirm gate (Destroy {name}? …) + non-destructive detach (useTerminal.detach closes the live socket → reconnect overlay, session survives) were unwired before this plan despite being must_haves truths — added + unit-covered (UI-SPEC criterion 12). Harness: playwright.config.ts webServer (stub+uvicorn-on-fake+vite preview) / BURROW_E2E_USE_COMPOSE toggle + docker-compose.e2e.yml + nginx.e2e.conf (Docker not on this host → compose validated by YAML parse, first CI run confirms boot). Gate: 81 vitest + 127 pytest + tsc + biome + ruff + mypy --strict all green. Real ttyd handshake + live claude TUI stays the deferred dev-homelab smoke.

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

Last session: 2026-06-10T22:37:03.780Z
Stopped at: Completed 02-06-PLAN.md — the phase e2e gate. Full Playwright journey (create → echo → split/tile → detach→reconnect → terminate) RAN GREEN over Fake + a standalone protocol-accurate stub ttyd; UI-05 restore-after-refresh integration test green; terminate confirm + non-destructive detach wired (Rule 2). Commits f714da1, 8fbd527. Phase 2 (Terminal Proxy + React UI) is now complete (6/6 plans).
Resume file: None
Next plan: Phase 2 is complete — run /gsd:verify-work on Phase 2, then plan Phase 3. Carried open items: real ttyd `tty` handshake + live claude TUI = deferred dev-homelab smoke (human_needed); `docker compose -f docker-compose.e2e.yml config` not validated here (no Docker on this host) — first CI run confirms the compose stack boots; A3 operator-confirm of the real git-credential-minting mechanism before Phase 3; B4 plugin-cadence ADR before/within Phase 3.
