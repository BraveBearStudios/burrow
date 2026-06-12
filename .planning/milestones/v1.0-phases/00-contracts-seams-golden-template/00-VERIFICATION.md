<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
verified: 2026-06-10T06:12:35Z
status: human_needed
score: 6/6 success criteria verified (CI-provable); 3 req-groups deferred to dev-homelab smoke
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
human_verification:
  - test: "Run provision-template.sh inside a CT, then `pct template` it on a real Proxmox node"
    expected: "Template VMID exists and is marked a template; CT carries Ubuntu 24.04 + Node 22 + pinned claude-code + ttyd + enabled burrow-worker.service"
    why_human: "Requires a real Proxmox node; not reachable from the Windows dev box and not CI-automatable (WORK-01 / SETUP-01)"
  - test: "`--full` clone the template by hand; from the control plane `curl http://<worker-ip>:7681/`"
    expected: "ttyd answers on the worker LAN interface (port 7681, not lo-only) — HTTP < 500; the proxy can reach it (WORK-04 / SC-9)"
    why_human: "Needs a real CT on a real LAN; ttyd LAN reachability cannot be proven in CI"
  - test: "Open the cloned worker's ttyd, launch claude, close the browser tab, reconnect"
    expected: "The Claude session is still alive after tab close (persistent ttyd, NO --once — SC-8); detach != terminate"
    why_human: "Requires a live real terminal session against real ttyd"
  - test: "Run 00-api-user-role.sh as root@pam; then `pvesh get /access/permissions --token 'burrow@pve!burrow=<secret>'` and attempt a scoped clone"
    expected: "Token resolves to pool/template/storage/node-scoped rights only (nothing on out-of-pool VMIDs); a scoped --full clone succeeds (SETUP-02/03)"
    why_human: "Requires real Proxmox auth + ACL enforcement"
  - test: "Execute the PRIMING.md STEP 4 five-step acceptance gate end-to-end from a LAN browser"
    expected: "create -> live terminal -> stop -> start -> destroy all succeed against real Proxmox + the golden template; GET /api/v1/health reports compute: ok"
    why_human: "Full real-infra create-to-destroy path; the 'looks done but isn't' gate (SETUP-04) — CI cannot prove it"
deferred:
  - truth: "WORK-01 — golden template provisions all worker software reproducibly on real Proxmox"
    addressed_in: "Phase 1/3 dev-homelab smoke (decisions frozen here)"
    evidence: "ROADMAP Phase 0 Infra note + REQUIREMENTS traceability mark WORK-01 'Pending' (script half shipped 00-07; real-infra acceptance deferred). VALIDATION.md Manual-Only table."
  - truth: "WORK-04 — ttyd reachable by the proxy over the worker LAN address (not lo)"
    addressed_in: "Dev-homelab smoke; ADR-0007 + burrow-boot.sh --interface 0.0.0.0 record/implement the decision here"
    evidence: "REQUIREMENTS WORK-04 'Pending (ADR-0007 records the decision; impl/validation half lands with burrow-boot.sh + dev-homelab smoke)'"
  - truth: "SETUP-01..05 — host-prime kit primes a bare Proxmox host end-to-end"
    addressed_in: "Operator-run dev-homelab smoke (kit + runbook authored here)"
    evidence: "ROADMAP Phase 0 Infra note: host-prime kit 'can only be validated against real Proxmox in the dev homelab'. CONTEXT Deferred Ideas + VALIDATION Manual-Only table."
---

# Phase 0: Contracts, Seams & Golden Template — Verification Report

**Phase Goal:** The seam contracts, hermetic test substrate, and golden-template + host-prime decisions exist so every later phase can be built and CI-greened without real Proxmox, and the worker template can be frozen.
**Verified:** 2026-06-10T06:12:35Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

The phase goal splits cleanly (per 00-VALIDATION.md) into a **CI-provable** half — contracts, envelope, Fake provider, app factory, static gates, ADRs — and a **real-infra** half (template boot, ttyd LAN reachability, host priming) that is **deferred by design** to the dev-homelab smoke gate. Every CI-provable success criterion was verified against the actual codebase and passing commands. The real-infra items are surfaced as `human_needed`, not gaps, per the operator's full-autonomous choice (no Proxmox reachable from this dev box).

### Observable Truths (ROADMAP Success Criteria 1-6)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `DbProvider` + `ComputeProvider` ABCs exist in `api/db/`+`api/compute/`; `FakeComputeProvider` implements compute in-memory (zero Proxmox) | ✓ VERIFIED | `compute/provider.py` (ABC, 12 `@abstractmethod`s), `db/provider.py` (ABC, 7 abstract methods), `compute/fakeProvider.py` fully implements all methods deterministically (no sleeps/randomness; `_fake_ip` from VMID). `test_fake_compute.py::test_is_compute_provider` + determinism/lifecycle tests pass. |
| 2 | Pydantic models map snake_case → camelCase JSON; reusable envelope produces `data`/`meta`/`error` with `requestId`+`timestamp` in `meta` | ✓ VERIFIED | `models/base.py` `CamelModel` (`alias_generator=to_camel`, `populate_by_name`); `models/workspace.py` snake fields. `lib/envelope.py` `respond`/`respond_error` emit `{data, meta:{requestId,timestamp}, error}`. `test_models.py` round-trip + `test_envelope.py` shape tests pass. |
| 3 | App factory wires providers by env (`BURROW_COMPUTE=fake\|proxmox`, `BURROW_DB=sqlite`) — swap = one-line, never a service edit | ✓ VERIFIED | `main.py` `get_compute()`/`get_db()` branch on `settings`; sole place concrete providers are named (verified by reading + seam-leakage test). `config.py` binds `BURROW_COMPUTE`/`BURROW_DB` via `validation_alias`. |
| 4 | CI static gates run green (ruff+biome, mypy strict+tsc, SPDX check, conventional-commit, lockfile) AND every source file carries SPDX | ✓ VERIFIED | Ran locally: ruff `All checks passed`, ruff format `26 files already formatted`, mypy `--strict` `no issues found in 26 files`, `uv lock --check` OK, ui `tsc --noEmit` OK, ui `biome ci` clean, `reuse lint` `111/111 files` compliant. `.github/workflows/ci.yml` wires all gates + PR-title check. |
| 5 | `provision-template.sh`+`burrow-boot.sh` exist with persistent ttyd (no `--once`) LAN-bound; template provisions Ubuntu 24.04+Node 22+claude-code+ttyd reproducibly | ✓ VERIFIED (script half) | `burrow-boot.sh`: `exec ttyd --port 7681 --writable --interface 0.0.0.0 ...` — NO `--once` (grep confirms it appears only in comments), no `lo`/127.0.0.1 bind. `provision-template.sh`: apt base + ttyd, NodeSource `setup_22.x`, pinned `@anthropic-ai/claude-code@2.1.170`, enables `burrow-worker.service`. `bash -n` clean. Real boot = deferred. |
| 6 | Re-runnable host-prime kit + `PRIMING.md` prime a bare Proxmox host (least-priv user+role+privsep token scoped; CT template; control plane) → operator reaches `/health` compute:ok and clones `--full` by hand | ✓ VERIFIED (kit/runbook half) | `lxc/host-prime/{00..40}` + `lib/common.sh` (all `bash -n` clean, idempotent check→act, reversal notes). `00-api-user-role.sh`: exact 9-priv role, privsep=1 token to BOTH user+token at pool/template/storage/node, secret→gitignored `.env` never echoed. `PRIMING.md` orders steps with per-step gates + five-step STEP 4 acceptance gate. Real run = deferred. |

**Score:** 6/6 CI-provable criteria verified. Criteria 5 and 6 are verified at the **authored-artifact** level (scripts/kit/runbook exist, are syntactically valid, encode the frozen SC decisions); their **real-infra acceptance** is the deferred dev-homelab smoke gate.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | WORK-01 real template boot on Proxmox | Phase 1/3 dev-homelab smoke | ROADMAP Phase 0 Infra note; REQUIREMENTS WORK-01 Pending (script half shipped 00-07) |
| 2 | WORK-04 ttyd LAN reachability over real LAN | Dev-homelab smoke (ADR-0007 + boot script implement the decision here) | REQUIREMENTS WORK-04 traceability note |
| 3 | SETUP-01..05 host-prime real run | Operator dev-homelab smoke | ROADMAP Infra note; CONTEXT Deferred; VALIDATION Manual-Only table |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/compute/provider.py` | ComputeProvider ABC | ✓ VERIFIED | ABC + 12 abstract methods + typed `ComputeError` hierarchy; no driver symbols |
| `api/compute/fakeProvider.py` | In-memory deterministic impl | ✓ VERIFIED | Full impl; failure-injection hooks for Phase-1 compensation tests |
| `api/compute/proxmoxProvider.py` | Phase-1 skeleton | ✓ VERIFIED (skeleton by design) | `NotImplementedError` bodies; imports `proxmoxer` (dep resolves + seam-confined). Phase-1 work per CONTEXT/ROADMAP. |
| `api/db/provider.py` | DbProvider ABC | ✓ VERIFIED | ABC + 7 abstract methods; no driver symbols |
| `api/db/sqliteProvider.py` | aiosqlite impl | ✓ VERIFIED | Full CRUD + soft-delete + event log + healthcheck + migration; camelCase↔snake bridging |
| `api/db/postgresProvider.py` | Hosted-path stub | ✓ VERIFIED (stub by design) | Behind the ABC; v1 ships SQLite only |
| `api/db/migrations/001_init.sql` | Schema | ✓ VERIFIED | workspaces/events/templates + indexes + seed. (Partial unique VMID index = WS-10 = Phase 1, correctly absent here) |
| `api/lib/envelope.py` | Envelope helper | ✓ VERIFIED | `respond`/`respond_error` + `Meta`/`ApiError` |
| `api/models/{base,workspace,compute,event,template}.py` | camelCase models + DTOs | ✓ VERIFIED | `CamelModel` base; secret-free `BootConfig` |
| `api/main.py` | App factory + DI seam | ✓ VERIFIED | `create_app` + env-driven `get_compute`/`get_db` + envelope error boundary |
| `api/config.py` | pydantic-settings | ✓ VERIFIED | `BURROW_COMPUTE`/`BURROW_DB` via `validation_alias`; TLS-validate posture |
| `api/tests/unit/*` | Test substrate | ✓ VERIFIED | 28 tests pass (seam-leakage, fake-compute, db, envelope, models) |
| `.github/workflows/ci.yml` | Static gates | ✓ VERIFIED | All Tier-0 gates + PR-title check; least-priv perms; SHA-pinned actions |
| `REUSE.toml` | SPDX coverage | ✓ VERIFIED | reuse lint 111/111 compliant |
| `docs/adr/ADR-0001..0008` | 8 Nygard ADRs | ✓ VERIFIED | All 8 carry Status/Context/Decision/Consequences |
| `cc-worker-config/.../burrow-boot.sh` | Persistent LAN ttyd | ✓ VERIFIED | No `--once`; `--interface 0.0.0.0` |
| `cc-worker-config/.../provision-template.sh` | Reproducible template | ✓ VERIFIED | Ubuntu 24.04 + Node 22 + pinned claude-code + ttyd |
| `cc-worker-config/systemd/burrow-worker.service` | Boot unit | ✓ VERIFIED | Runs boot script; Restart=on-failure; no secrets baked |
| `cc-worker-config/lxc/host-prime/*` | Day-0 kit | ✓ VERIFIED | 5 scripts + lib; idempotent; reversal notes |
| `cc-worker-config/PRIMING.md` | Day-0 runbook | ✓ VERIFIED | Ordered steps + gates + five-step acceptance gate |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| All 7 plans (SDK) | declared artifacts | `gsd-sdk verify.artifacts` | ✓ WIRED | `all_passed: true` for every plan (4/5/3/3/3/4/3) |
| All 7 plans (SDK) | declared links | `gsd-sdk verify.key-links` | ✓ WIRED | `all_verified: true` for every plan |
| `main.py` | `FakeComputeProvider`/`SqliteProvider` | env-branched `get_compute`/`get_db` | ✓ WIRED | Sole concrete-provider site; confirmed by read + seam-leakage test |
| `sqliteProvider.py` | `001_init.sql` | `migrate()` reads + `executescript` | ✓ WIRED | `test_db_provider` round-trips on temp DB |
| `provision-template.sh` | `burrow-boot.sh` + unit | `install` + `systemctl enable` | ✓ WIRED | Script installs both, enables unit |
| `burrow-worker.service` | `burrow-boot.sh` | `ExecStart=/opt/burrow-boot.sh` | ✓ WIRED | Unit runs the boot orchestration |

### Data-Flow Trace (Level 4)

No dynamic-data-rendering artifacts in this phase (no routers/UI views ship yet — routers are Phase 1, UI is Phase 2). The Fake provider's data-flow is exercised directly by unit tests (`test_fake_compute` determinism/lifecycle). N/A for HOLLOW-prop checks.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit suite passes | `uv run pytest -q` | `28 passed in 0.81s` | ✓ PASS |
| Lint clean | `uv run ruff check .` | `All checks passed!` | ✓ PASS |
| Format clean | `uv run ruff format --check .` | `26 files already formatted` | ✓ PASS |
| Type-strict clean | `uv run mypy . --strict` | `Success: no issues found in 26 source files` | ✓ PASS |
| Lockfile fresh | `uv lock --check` | resolved, no drift | ✓ PASS |
| UI typecheck | `npx tsc --noEmit` (ui/) | clean | ✓ PASS |
| UI lint | `npx biome ci .` (ui/) | `Checked 2 files... No fixes applied` | ✓ PASS |
| SPDX coverage | `uvx reuse lint` | `111/111 files` compliant | ✓ PASS |
| Boot script syntax | `bash -n burrow-boot.sh` | OK | ✓ PASS |
| Template script syntax | `bash -n provision-template.sh` | OK | ✓ PASS |
| Host-prime scripts syntax | `bash -n *.sh` (5 files) | all OK | ✓ PASS |

### Probe Execution

No probes apply. This is a contracts/seams phase, not a migration/tooling phase; 00-VALIDATION.md explicitly classifies the script/template/host-prime correctness as "not CI-automatable / dev-homelab". `find scripts -path '*/tests/probe-*.sh'` returned none. The unit suite + static gates are the phase's runnable checks (all green above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PLAT-02 | 00-01 | Standard envelope w/ requestId+timestamp | ✓ SATISFIED | `lib/envelope.py` + `test_envelope.py` |
| PLAT-09 | 00-01 | snake→camel mapping | ✓ SATISFIED | `models/base.py` + `test_models.py` |
| PLAT-06 | 00-02 | Abstract DbProvider + SQLite impl, no leak | ✓ SATISFIED | `db/provider.py`+`db/sqliteProvider.py` + seam-leakage test |
| PLAT-07 | 00-02 | First-class `api/compute/` ComputeProvider, no leak (SC-13) | ✓ SATISFIED | `compute/` package + seam-leakage test |
| PLAT-08 | 00-02 | FakeComputeProvider hermetic | ✓ SATISFIED | `compute/fakeProvider.py` + `test_fake_compute.py` |
| CICD-01 | 00-04 | Static gates green | ✓ SATISFIED | All gates ran clean locally; `ci.yml` wires them |
| CICD-06 | 00-04 | SPDX header on every source file | ✓ SATISFIED | `reuse lint` 111/111 |
| WORK-01 | 00-07 | Golden template provisions worker software reproducibly | ? NEEDS HUMAN | `provision-template.sh` authored + valid; real `pct template` = dev-homelab |
| WORK-04 | 00-07 | ttyd reachable over worker LAN (not lo) | ? NEEDS HUMAN | ADR-0007 + `--interface 0.0.0.0` in boot script; real reachability = dev-homelab |
| SETUP-01 | 00-06 | Re-runnable host-prime kit | ? NEEDS HUMAN | Kit authored, idempotent, valid; real run = dev-homelab |
| SETUP-02 | 00-06 | Minimal 9-priv role scoped | ? NEEDS HUMAN | Exact priv set in `00-api-user-role.sh`; real ACL enforcement = dev-homelab |
| SETUP-03 | 00-06 | privsep token to user+token, secret hygiene | ? NEEDS HUMAN | Implemented w/ gitignore guard; real auth = dev-homelab |
| SETUP-04 | 00-06 | PRIMING.md runbook + 5-step acceptance gate | ? NEEDS HUMAN | Runbook authored w/ gates; real five-step run = dev-homelab |
| SETUP-05 | 00-06 | Static-IP-from-VMID + DHCP exclusion recorded | ✓ SATISFIED | `30-network-notes.md` records the scheme (placeholders); ADR-0004 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cc-worker-config/.../burrow-boot.sh` | 38 | `TODO(Phase 3)` | ℹ️ Info | Legitimate scoped deferral — references a formal future phase; the live pull-at-boot fetch is Phase 3 by design (CONTEXT/ROADMAP). Not unresolved debt. |
| `.github/workflows/ci.yml` | 88 | `# TODO pin exact SHA` | ⚠️ Warning | Stale/misleading comment: the action is ALREADY pinned to a full 40-char SHA (`e32d7e6...596825`). The comment contradicts the file's own "Third-party actions are SHA-pinned" header. Cosmetic — recommend removing the comment. Does not affect any gate. |

No BLOCKER anti-patterns. No `TBD`/`FIXME`/`XXX` debt markers anywhere in phase files (grep confirmed clean). `proxmoxProvider.py` and `postgresProvider.py` `NotImplementedError`/stub bodies are intentional Phase-1/hosted-path skeletons, explicitly scoped in CONTEXT — not stubs masquerading as done work.

### Human Verification Required (dev-homelab smoke gate)

All five items below require a real Proxmox node + LAN, unreachable from this dev box. Deferred per the operator's full-autonomous choice; decisions are frozen here, validation lands in the dev-homelab smoke.

1. **Template build + freeze** — Run `provision-template.sh` in a CT, then `pct template`. Expect: template VMID exists/is-a-template, carries Ubuntu 24.04 + Node 22 + pinned claude-code + ttyd + enabled boot unit. (WORK-01 / SETUP-01)
2. **ttyd LAN reachability** — `--full` clone the template; from the control plane `curl http://<worker-ip>:7681/`. Expect: ttyd answers on the worker LAN interface (HTTP < 500), proxy can reach it. (WORK-04 / SC-9)
3. **Persistent ttyd (detach != terminate)** — Open ttyd, launch `claude`, close the tab, reconnect. Expect: session still alive (no `--once`, SC-8).
4. **Scoped token + clone** — Run `00-api-user-role.sh`; `pvesh get /access/permissions --token 'burrow@pve!burrow=<secret>'`; attempt a scoped clone. Expect: pool/template/storage/node-scoped rights only; scoped `--full` clone succeeds. (SETUP-02/03)
5. **Five-step acceptance gate** — Execute PRIMING.md STEP 4: create → live terminal → stop → start → destroy from a LAN browser. Expect: all five succeed; `GET /api/v1/health` → `compute: ok`. (SETUP-04)

### Gaps Summary

**No gaps.** Every CI-provable success criterion is verified against the actual codebase with passing commands (28 unit tests, ruff/format/mypy-strict/tsc/biome/lockfile/reuse all green), and every authored artifact for criteria 5 and 6 exists, is syntactically valid, and encodes the frozen SC decisions (no `--once`, LAN bind, 9-priv role, privsep token, pull-at-boot, `--full`, eight Nygard ADRs). The only unverified items are the real-Proxmox acceptance behaviors (WORK-01, WORK-04, SETUP-01..05) which are **deferred by design** to the dev-homelab smoke gate and surfaced as `human_needed` — exactly as 00-VALIDATION.md, 00-CONTEXT.md, and the ROADMAP Infra note prescribe. Per the verification method's explicit rule (CI-provable set passes + only real-infra items remain), the correct status is **human_needed**, not gaps_found.

Two cosmetic notes (non-blocking): the stale `# TODO pin exact SHA` comment in `ci.yml:88` (the action is in fact already SHA-pinned), and the expected `TODO(Phase 3)` deferral marker in `burrow-boot.sh:38`.

---

_Verified: 2026-06-10T06:12:35Z_
_Verifier: Claude (gsd-verifier)_
