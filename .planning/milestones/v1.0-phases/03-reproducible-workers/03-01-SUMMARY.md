<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 03-reproducible-workers
plan: 01
subsystem: infra
tags: [bash, boot, git-askpass, credential-hygiene, jq, pytest, jsonschema, ttyd, pull-at-boot]

# Dependency graph
requires:
  - phase: 01-control-plane
    provides: "the frozen GET /api/v1/internal/bootconfig/{vmid} endpoint (camelCase .data envelope + per-fetch minted credential) the boot script consumes"
  - phase: 00-foundation
    provides: "the Phase-0 burrow-boot.sh stub (frozen ttyd tail), provision-template.sh bake, host-prime/lib/common.sh err_trap idiom, and the tests/integration loopback-fake substrate"
provides:
  - "Live burrow-boot.sh pull-at-boot spine: resolve_vmid + bounded-retry fetch_bootconfig + leak-proof clone_with_token + CLAUDE.md copy + the FROZEN ttyd exec"
  - "Credential-hygiene core (SC-3): in-memory GIT_ASKPASS one-shot in a subshell, never in a URL / worker.env / log line"
  - "Hermetic boot harness (api/tests/boot/): loopback fake control plane + file:// bare repos + stub ttyd on PATH; the worker-side analogue of test_bootconfig.py"
  - "jq baked into the golden template; jsonschema added as a dev/CI dep"
affects: [03-02-manifest, 03-03-adr-ci, dev-homelab-smoke]

# Tech tracking
tech-stack:
  added: ["jsonschema==4.26.0 (dev/CI dep)", "jq (golden-template apt bake)"]
  patterns:
    - "In-memory GIT_ASKPASS one-shot credential in a subshell (RESEARCH Pattern 1) — the leak-proof clone idiom"
    - "Bounded-retry + capped-backoff HTTP fetch echoing .data on stdout (RESEARCH Pattern 2)"
    - "Hermetic subprocess boot harness: stdlib http.server fake CP + git --bare file:// remotes + stub-binary-on-PATH"

key-files:
  created:
    - "api/tests/boot/__init__.py"
    - "api/tests/boot/conftest.py"
    - "api/tests/boot/test_burrow_boot.py"
    - "api/tests/boot/stub_ttyd_bin"
    - ".planning/phases/03-reproducible-workers/03-01-SUMMARY.md"
  modified:
    - "cc-worker-config/lxc/worker-template/burrow-boot.sh"
    - "cc-worker-config/lxc/worker-template/provision-template.sh"
    - "api/pyproject.toml"
    - "api/uv.lock"

key-decisions:
  - "log() writes to STDERR (was stdout) so command-substituted fetch_bootconfig stdout stays clean — the .data JSON is captured, log lines are not"
  - "CONTROL_PLANE is now REQUIRED (:? guard) — the live fetch depends on it; missing → fail the boot, not launch an unconfigured ttyd"
  - "BURROW_HOSTNAME + BURROW_ETC are test/override seams (default to real hostname -s / /etc/burrow) so the harness drives the script hermetically without changing production behaviour"
  - "Plan 03-01 is the THIN slice (fetch + clone + frozen ttyd + credential hygiene); manifest processing is Plan 02, the ADR + CI wiring are Plan 03 — per the plan objective, not the broader RESEARCH/PATTERNS scope"

patterns-established:
  - "Leak-proof clone_with_token: GIT_ASKPASS subshell, x-access-token username, GIT_TERMINAL_PROMPT=0, credential.helper= empty, helper rm'd after clone"
  - "Worker-side scrub-proof test: capture subprocess stdout+stderr + read worker.env, assert the _SENTINEL_CREDENTIAL + project URL are absent (mirrors test_bootconfig.py)"

requirements-completed: [WORK-02]  # plan-line 03-01 (fetch+clone+ttyd spine); WORK-02 also depends on Plan 03-02 manifest install

# Metrics
duration: 22min
completed: 2026-06-11
---

# Phase 3 Plan 01: Live Pull-at-Boot Spine + Hermetic Boot Harness Summary

**burrow-boot.sh now self-resolves its VMID, bounded-retries the frozen bootconfig endpoint, clones config + project via a leak-proof in-memory GIT_ASKPASS subshell, copies CLAUDE.md, and execs the frozen persistent/LAN-bound ttyd — proven CI-green by a hermetic pytest boot harness (fake control plane + file:// bare repos + stub ttyd) including the SC-3 credential-no-leak guarantee, with zero real Proxmox.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-11T14:16:45Z
- **Completed:** 2026-06-11T14:38:25Z
- **Tasks:** 3
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments

- Replaced the Phase-0 stub config block (lines 26-75) of `burrow-boot.sh` with the live pull-at-boot spine while preserving the FROZEN ttyd tail verbatim (`--interface 0.0.0.0` present, `--once` absent — ADR-0006/0007) and the frozen bootconfig endpoint contract (`api/routers/internal.py` untouched).
- Delivered the SC-3 credential-hygiene core: the short-lived git credential is fed to `git clone` via an in-memory `GIT_ASKPASS` helper inside a subshell (`x-access-token` username, `GIT_TERMINAL_PROMPT=0`, `git -c credential.helper=` empty), never embedded in a clone URL, never written to `/etc/burrow/worker.env`, and `unset` after the clones.
- Built the hermetic `api/tests/boot/` tier — a loopback stdlib `http.server` fake control plane (UP + down variants), a `git --bare` `file://` bare-repo factory, and a stub `ttyd` on `PATH` — with five passing tests: happy path, retry-then-fail, scrub-proof no-leak, frozen-ttyd-line, and no-`set -x`.
- Baked `jq` into the golden template's apt-install list (the live script's JSON dependency) and added `jsonschema==4.26.0` as a dev/CI dep with a refreshed lockfile.

## Task Commits

Each task was committed atomically:

1. **Task 1: Hermetic boot harness scaffold (RED happy path)** - `5c325c5` (test)
2. **Task 2: Live pull-at-boot fetch + leak-proof clone + frozen ttyd** - `b70f63b` (feat — TDD GREEN)
3. **Task 3: Bake jq into the golden template** - `d2d30df` (chore)

**Plan metadata:** committed with this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md.

## Files Created/Modified

- `cc-worker-config/lxc/worker-template/burrow-boot.sh` - Stub config block replaced with `resolve_vmid` / `fetch_bootconfig` / `clone_with_token`, an `err_trap` mirroring `common.sh` (+ `$BASH_COMMAND` redaction backstop), and `log()` now writing to stderr; FROZEN ttyd tail + `CLAUDE_CMD`/`START_DIR` blocks unchanged.
- `cc-worker-config/lxc/worker-template/provision-template.sh` - Added `jq` to the `apt-get install -y` bake list (single in-place edit; `python3-jsonschema` intentionally NOT added).
- `api/tests/boot/conftest.py` - Fake control plane (FROZEN `{data,meta,error}` camelCase envelope), bare-repo factory, stub-ttyd-on-PATH fixtures, `make_boot_env` seam helper, and the `_SENTINEL_CREDENTIAL`.
- `api/tests/boot/test_burrow_boot.py` - The five boot-harness tests driving `bash burrow-boot.sh` as a subprocess.
- `api/tests/boot/stub_ttyd_bin` - Fake `ttyd` that records its argv to `STUB_TTYD_ARGV_FILE` and exits 0.
- `api/tests/boot/__init__.py` - Boot test package docstring (mirrors `tests/integration/__init__.py`).
- `api/pyproject.toml` / `api/uv.lock` - `jsonschema==4.26.0` dev dep + refreshed lock (`uv lock --check` green).

## Decisions Made

- **`log()` → stderr (Rule 1 fix):** `fetch_bootconfig` echoes the `.data` JSON on stdout for capture via `$(...)`; the Phase-0 `log()` used stdout, which would have contaminated the captured JSON and swallowed the retry log lines. Moved `log()` to stderr (matching `host-prime/lib/common.sh`). Surfaced by the retry test counting zero `bootconfig attempt` lines.
- **`CONTROL_PLANE` required:** flipped the Phase-0 warn-and-skip to a `:?` fail-if-unset guard (the stub comment said "the `:?` guard returns in Phase 3"). A missing control plane now fails the boot rather than launching an unconfigured ttyd.
- **Test/override seams (`BURROW_HOSTNAME`, `BURROW_ETC`):** added so the hermetic harness can drive `resolve_vmid` and relocate `/etc/burrow` under a temp root without a real hostname; both default to the real worker values (production behaviour unchanged), mirroring the integration tier's env-override idiom.
- **Thin-slice scope:** Plan 03-01 deliberately implements only the fetch + clone + frozen ttyd + credential hygiene. The RESEARCH/PATTERNS docs describe a wider phase scope (manifest processing, `manifest.json`/`manifest.schema.json`, `test_manifest_schema.py`, `install_claude_plugin`, ADR-0009), but the PLAN objective is explicit: "Manifest-driven plugins land in Plan 02; the ADR + CI wiring land in Plan 03." Followed the plan (most-recent-doc-wins).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `log()` wrote to stdout, contaminating command-substituted data**
- **Found during:** Task 2 (live fetch implementation)
- **Issue:** `fetch_bootconfig` returns the `.data` JSON on stdout via `$(...)`, but the inherited `log()` printed to stdout — so log lines were captured into `$BOOTCONFIG` and the retry-then-fail test saw zero `bootconfig attempt` lines (and any logged context would have corrupted the parsed JSON).
- **Fix:** Changed `log()` to write to `>&2` (stderr), matching the canonical `host-prime/lib/common.sh log()`.
- **Files modified:** `cc-worker-config/lxc/worker-template/burrow-boot.sh`
- **Verification:** `test_bootconfig_retry_then_fail` now counts ~5 bounded `bootconfig attempt` lines; happy path parses `.data` cleanly.
- **Committed in:** `b70f63b` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Hermetic test-override seams for the boot script**
- **Found during:** Task 2 (making the harness drivable)
- **Issue:** The script read its hostname via `hostname -s` and `/etc/burrow` as a hard path — neither is controllable in a hermetic CI subprocess, so the harness could not drive `resolve_vmid` or assert on a temp `worker.env`.
- **Fix:** Added `BURROW_HOSTNAME` and `BURROW_ETC` override seams (operator/CI config, never client input), each defaulting to the real worker value so production behaviour is identical.
- **Files modified:** `cc-worker-config/lxc/worker-template/burrow-boot.sh`, `api/tests/boot/conftest.py`
- **Verification:** All five boot-harness tests run under a temp `HOME` + temp `/etc/burrow` + a synthetic `burrow-w-241` hostname.
- **Committed in:** `b70f63b` (Task 2 commit)

**3. [Rule 3 - Blocking] mypy --strict / ruff cleanups in the new test tier**
- **Found during:** Task 2 (static gate)
- **Issue:** an untyped `run = lambda ...`, an unused `Callable` import, `f"{host}"` on a possibly-bytes address, and a function-local `import os` tripped `mypy --strict` + `ruff`.
- **Fix:** typed nested `run(*args: str) -> None`, dropped the import, coerced `host`/`port` to `str`/`int`, hoisted `import os` to module level; `ruff format` applied.
- **Files modified:** `api/tests/boot/conftest.py`, `api/tests/boot/test_burrow_boot.py`
- **Verification:** `ruff check`, `ruff format --check`, and `mypy --strict` all green on `tests/boot`.
- **Committed in:** `b70f63b` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 1 missing-critical, 1 blocking)
**Impact on plan:** All three were necessary for correctness and to satisfy the project's static gates. No scope creep — the script's external behaviour matches the plan; the seams are inert in production.

## Issues Encountered

- **shellcheck not installed on the Windows dev host.** Per the critical constraints and STATE.md (Plan 00-06), shellcheck is wired into CI by Plan 03-03 — not a blocker here. Both scripts pass `bash -n` (parse-clean). `shellcheck` static analysis is deferred to CI/homelab.
- **`reuse` needs the `charset-normalizer` extra on Windows** (known from Plan 00-06): ran `uvx --with charset-normalizer reuse lint-file` — all new source files are SPDX-compliant.

## Threat Flags

None — no new security surface beyond the plan's `<threat_model>`. The boot script consumes the existing frozen endpoint over the operator-set `CONTROL_PLANE` and adds no new network listener, auth path, or schema change. The credential-disclosure surface (T-03-01..04) is mitigated exactly as the threat register prescribes and proven by `test_no_credential_leak`.

## [ASSUMED] details to confirm at the dev-homelab smoke (NOT CI)

- **`resolve_vmid` hostname-suffix parse** (A3 / ADR-0004): the authoritative VMID↔static-IP mapping is operator-recorded in `30-network-notes.md`; the `${host##*-}` suffix parse is illustrative. A wrong VMID 404s safely (T-03-05 accept).
- **`x-access-token` username convention** (A2 / A3): depends on the operator's pending `mint_repo_credential` mechanism. If it is a deploy-key / GitLab job token, the askpass `Username` branch changes.
- **Config-repo auth model** (A5 / Open-Q-1): the frozen endpoint mints a credential scoped to the project repo only; `cc-worker-config` is assumed operator-reachable (public / same-org). Separate auth would be an operator-contract question, not a code change (endpoint frozen).
- **Real template rebuild:** `jq` lands in the golden image only after `20-create-template.sh` is re-run on the homelab; the live script runs the old stub until then. CI cannot prove the real boot.

## Next Phase Readiness

- The live boot spine + credential hygiene are CI-green and ready. Plan 03-02 adds manifest processing (`process_manifest` jq gate + `install_claude_plugin`) on top of the now-live fetch/clone path; Plan 03-03 adds ADR-0009 + the CI wiring (shellcheck + the `tests/boot` + manifest pytest tiers).
- WORK-02 is delivered for its fetch/clone/ttyd half; its "pulls plugin manifest" clause completes with Plan 03-02.

## Self-Check: PASSED

---
*Phase: 03-reproducible-workers*
*Completed: 2026-06-11*
