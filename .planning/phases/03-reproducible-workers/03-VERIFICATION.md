<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 03-reproducible-workers
verified: 2026-06-11T00:00:00Z
status: human_needed
score: 4/4 success criteria verified (goal achieved); the SPDX/reuse-lint CI gap is RESOLVED (commit 607c49d) — only dev-homelab smoke items remain
overrides_applied: 0
mode: mvp
resolved_gaps:
  - truth: "CI `spdx · reuse lint` gate (CICD-06) passes on every push/PR"
    status: resolved
    resolution: >-
      Fixed in commit 607c49d: the SPDX two-line header was added (before the YAML
      frontmatter, matching the prior-phase convention) to all 5 flagged docs —
      03-01/02/03-PLAN.md, 03-REVIEW.md, 03-VALIDATION.md. `uvx --with charset-normalizer
      reuse lint` now reports 242/242 compliant (exit 0). NOTE: the local `uvx reuse`
      crashed with NoEncodingModuleError until charset-normalizer was bundled — a CI
      robustness follow-up (the reuse step works on Ubuntu runners via libmagic; harden
      with `--with charset-normalizer` in Phase 4).
    original_reason: >-
      The repo-wide `uvx reuse lint` step the CI runs (.github/workflows/ci.yml:91) is
      NON-COMPLIANT: 5 Phase-3 planning docs carry no SPDX two-line header and are not in
      REUSE.toml, so the build's SPDX gate fails. The SUMMARYs claimed "reuse lint green"
      but verified only with per-file `reuse lint-file` on the new source files, not the
      repo-wide `reuse lint` the CI actually invokes. deferred-items.md and the Plan 03-03
      SUMMARY both said the gap would be closed in the 03-03 CI plan; the 03-03 deviations
      section records "None — plan executed exactly as written," so it was never fixed.
      Earlier-phase PLAN docs escape the lint only incidentally (their task bodies quote
      literal `SPDX-FileCopyrightText:`/`SPDX-License-Identifier:` lines, which reuse's
      heuristic accepts); the Phase-3 PLAN bodies mention only the acronym, so they are flagged.
    artifacts:
      - path: ".planning/phases/03-reproducible-workers/03-01-PLAN.md"
        issue: "No SPDX header and not covered by REUSE.toml — flagged by reuse lint"
      - path: ".planning/phases/03-reproducible-workers/03-02-PLAN.md"
        issue: "No SPDX header — flagged by reuse lint"
      - path: ".planning/phases/03-reproducible-workers/03-03-PLAN.md"
        issue: "No SPDX header — flagged by reuse lint"
      - path: ".planning/phases/03-reproducible-workers/03-REVIEW.md"
        issue: "No SPDX header — flagged by reuse lint"
      - path: ".planning/phases/03-reproducible-workers/03-VALIDATION.md"
        issue: "No SPDX header — flagged by reuse lint"
    missing:
      - "Add the SPDX two-line header to the 5 planning docs, OR add a `.planning/phases/**` (or explicit-paths) `[[annotations]]` block to REUSE.toml so the repo-wide `uvx reuse lint` CI step is green."
human_verification:
  - test: "Re-run 20-create-template.sh on the dev homelab, then boot a real worker and confirm it fetches bootconfig, clones config+project, copies CLAUDE.md, and lands in a live ttyd Claude session."
    expected: "Worker boots into a persistent LAN-bound ttyd Claude session; a boot failure surfaces as a typed boot.error via the create-saga ttyd-health timeout (no silent hang)."
    why_human: "Requires a real Proxmox node + golden template; CI is hermetic (Out of Scope: real Proxmox in CI). SC-1 real-boot half."
  - test: "Confirm `resolve_vmid` (hostname-suffix parse, BURROW_HOSTNAME default `hostname -s`) yields the correct VMID against the operator-recorded 30-network-notes.md / ADR-0004 mapping."
    expected: "The parsed VMID matches the operator's static-IP↔VMID scheme; a wrong VMID 404s safely."
    why_human: "The `${host##*-}` parse is [ASSUMED]; the authoritative mapping is operator-recorded, not in-repo (T-03-05 accept)."
  - test: "Confirm the `x-access-token` GIT_ASKPASS username convention matches the operator's pending mint_repo_credential mechanism (GitHub App installation token / fine-grained PAT)."
    expected: "The clone authenticates; if the operator's mechanism is a deploy-key / GitLab job token, the askpass Username branch must change."
    why_human: "Depends on the operator's pending credential-mint mechanism (A2/A3) — not determinable from the repo."
  - test: "Confirm the config repo (cc-worker-config) is operator-reachable with the project-scoped bootconfig credential (or document its separate auth)."
    expected: "The config clone succeeds at boot; if cc-worker-config needs separate auth, that is an operator-contract decision, not a code change (endpoint frozen)."
    why_human: "The bootconfig endpoint mints a credential scoped to the project repo; the config-repo auth model (A5/Open-Q-1) is an operator contract."
  - test: "Confirm `~/.claude/settings.json` `enabledPlugins[<name>]=true` is the correct directory-install enablement shape for claude-code@2.1.170, and that the installed claude-plugin actually loads (`claude plugin list` / `--debug`)."
    expected: "The pulled claude-plugin is enabled and loaded by Claude Code on the real worker."
    why_human: "The on-disk enablement shape is [ASSUMED] for 2.1.170 (A1/Open-Q-2); the harness proves the clone+settings write+idempotence shape, the homelab proves the live load."
---

# Phase 3: Reproducible Workers Verification Report

**Phase Goal:** A booted worker pulls its CLAUDE.md and plugin set fresh from `cc-worker-config` so workspaces are reproducible and plugin drift is impossible, with no credentials left behind.
**Verified:** 2026-06-11
**Status:** human_needed (SPDX/reuse-lint gap resolved in commit 607c49d; only dev-homelab smoke remains)
**Mode:** mvp (roadmap goal is the phase-boundary statement; SC-1..SC-4 are the verified contract)
**Re-verification:** Gap closed post-verification — SPDX headers added to the 5 flagged docs; `reuse lint` now 242/242 compliant.

## Goal Achievement

The phase goal is **achieved in the codebase**: the live `burrow-boot.sh` fetches bootconfig, clones config + project with a leak-proof in-memory GIT_ASKPASS credential, copies CLAUDE.md, processes a versioned ref-pinned manifest (claude-plugin pulled fresh, binary/npm-global skipped), and execs the frozen persistent/LAN-bound ttyd — all proven by 25 passing hermetic tests with zero real Proxmox. The credential never reaches a URL, `worker.env`, or a log line (scrub-proof test green). ADR-0009 records the boot-time-latest cadence + ref-pinning reproducibility model.

The single gap is **not** a goal failure: the repo-wide `uvx reuse lint` CI gate (CICD-06, itself a Plan 03-03 deliverable) fails on 5 Phase-3 planning docs missing SPDX headers — a build-gate regression this phase introduced and left unfixed despite acknowledging it in deferred-items.md.

### Observable Truths (Roadmap Success Criteria SC-1..SC-4)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `burrow-boot.sh` fetches bootconfig (project repo/branch + short-lived credential) pull-at-boot, pulls CLAUDE.md + a versioned manifest, clones the project, launches ttyd into Claude Code, with error trapping so a failure surfaces (not a silent hang) | ✓ VERIFIED | `burrow-boot.sh`: `fetch_bootconfig` bounded-retry curl → `jq -e .data`; `clone_with_token` config+project; `cp …/claude/CLAUDE.md ~/CLAUDE.md`; frozen `exec ttyd … --interface 0.0.0.0`; `set -euo pipefail` + `err_trap` ERR trap (exits non-zero → create-saga ttyd-health timeout records `boot.error`). Tests `test_fetch_then_clone_happy_path`, `test_bootconfig_retry_then_fail` (~5 bounded retries then non-zero, no hang) PASS. Real boot = human (SC-1 real half). |
| 2 | Plugin set is manifest-defined: claude-plugin pulled fresh, binary/npm-global baked; two boots of the same manifest produce the same plugin set | ✓ VERIFIED | `process_manifest` jq gate + `install_claude_plugin` (`rm -rf` + `git clone --depth=1 --branch <ref>`); only `type=="claude-plugin"` iterated, binary/npm-global skipped. `provision-template.sh:52-59` bakes rtk(binary)/gsd(npm-global). Tests `test_only_claude_plugins_installed`, `test_two_boots_identical_plugin_tree` (byte-identical SHA-256 digest) PASS. |
| 3 | Git credential short-lived/scoped + scrubbed: no token in `worker.env` post-boot, no repo URL/credential in event-log data or structured logs | ✓ VERIFIED | In-memory `GIT_ASKPASS` subshell, `x-access-token` username, `GIT_TERMINAL_PROMPT=0`, `git -c credential.helper=`, helper `rm`'d, `GIT_CRED` `unset` after clones; never in a URL (`grep '://x-access-token:'` = 0). `test_no_credential_leak` asserts SENTINEL + project URL absent from stdout+stderr AND from `worker.env`. PASS. Mirrors the shipped server-side `_safe()` no-leak gate. |
| 4 | Plugin-cadence decision (boot-time-latest vs snapshot-at-create) resolved + recorded so reproducibility semantics are explicit | ✓ VERIFIED | `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md`: Accepted; full Nygard skeleton (Status/Context/Decision/Consequences/Revisit trigger); records boot-time-latest + manifest ref-pinning (Option B chosen over snapshot-at-create Option A); revisit trigger = per-workspace pinning. |

**Score:** 4/4 success criteria verified (goal achieved in code; real-boot acceptance is the documented human smoke).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cc-worker-config/lxc/worker-template/burrow-boot.sh` | Live fetch + GIT_ASKPASS clone + manifest + frozen ttyd | ✓ VERIFIED | 332 lines; substantive; `bash -n` clean; contains `GIT_ASKPASS`, `process_manifest`, `install_claude_plugin`, `credential.helper=`, `GIT_TERMINAL_PROMPT=0`. Wired (run by burrow-worker.service; driven by the harness). |
| `cc-worker-config/plugins/manifest.json` | Versioned ref-pinned manifest | ✓ VERIFIED | schemaVersion 1.0.0; one claude-plugin pinned `v1.0.0` + baked rtk/gsd; no `main` ref; placeholder/public sources, no secrets. Validates against the schema (CI test PASS). |
| `cc-worker-config/plugins/manifest.schema.json` | Shared JSON-Schema (CI + boot source of truth) | ✓ VERIFIED | draft 2020-12; `additionalProperties:false` both levels; `enum:[claude-plugin,binary,npm-global]`; `minLength:1` on source/ref. Boot-time jq gate enforces the identical enum (grep parity confirmed). |
| `api/tests/boot/test_burrow_boot.py` | Hermetic boot harness incl. scrub-proof + WR-fix regressions | ✓ VERIFIED | 509 lines; references `SENTINEL_CREDENTIAL`; happy/retry/no-leak/frozen-ttyd/manifest/idempotence + WR-01..05 regression tests. All PASS. |
| `api/tests/boot/conftest.py` | Fake CP + bare-repo factory + stub-ttyd-on-PATH | ✓ VERIFIED | Frozen `{data,meta,error}` camelCase envelope (`configRepo`…`gitCredential`); manifest_config_repo factory with bad_type/raw_manifest variants. |
| `api/tests/integration/test_manifest_schema.py` | CI manifest-drift gate | ✓ VERIFIED | `jsonschema.validate`; committed-manifest-valid + unknown-type-rejected + no-`main`-ref + repo-root-depth guard. PASS. |
| `docs/adr/ADR-0009-…md` | B4 cadence decision (SC-4) | ✓ VERIFIED | "boot-time-latest" present; all five `##` sections; snapshot-at-create in Revisit trigger. |
| `.github/workflows/ci.yml` | shellcheck on boot scripts + boot/manifest pytest tiers | ✓ VERIFIED | shellcheck step (both scripts) + `uv run pytest tests/boot tests/integration/test_manifest_schema.py` step present and well-formed; the same workflow's repo-wide `spdx · reuse lint` step now passes (242/242) after commit 607c49d added the SPDX headers. |
| `api/tests/boot/stub_ttyd_bin` | Fake ttyd records argv, exits 0 | ✓ VERIFIED | Present; shellcheck not gated on it (REVIEW IN-02, info only). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `burrow-boot.sh` | `GET /api/v1/internal/bootconfig/{vmid}` | `curl … && jq -e .data` over `$CONTROL_PLANE` | ✓ WIRED | `fetch_bootconfig` bounded-retry; `internal/bootconfig` present; consumes the frozen camelCase `.data` envelope. |
| `conftest.py` fake CP | `internal.py` response shape | emits `{data,meta,error}` camelCase | ✓ WIRED | `configRepo`/`gitCredential` keys match the frozen contract. |
| `test_manifest_schema.py` | `manifest.json` + `manifest.schema.json` | `jsonschema.validate(manifest, schema)` | ✓ WIRED | Validates the committed manifest; rejects unknown type. |
| `burrow-boot.sh` | `manifest.json` | jq enum/required-keys gate + iterate `claude-plugin` | ✓ WIRED | jq gate at schema parity; only claude-plugin entries cloned. |
| `ci.yml` | `burrow-boot.sh` + `provision-template.sh` | `shellcheck` step | ✓ WIRED | Both scripts targeted (first CI run confirms clean — unverifiable on the Windows dev host). |
| `ci.yml` | `tests/boot` + `test_manifest_schema.py` | `uv run pytest` step | ✓ WIRED | Exact command verified green locally (25 passed). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `burrow-boot.sh` bootconfig | `BOOTCONFIG`/`CONFIG_REPO`/`GIT_CRED` | `fetch_bootconfig` ← live `GET /internal/bootconfig` (real `internal.py` route in Phase 1) | Yes (hermetic fake CP in tests; real endpoint in prod) | ✓ FLOWING |
| plugin tree | `~/.claude/plugins/<name>` | `install_claude_plugin` ← real `git clone` of a pinned ref from the manifest | Yes (real file:// clones in tests; real https in prod) | ✓ FLOWING |
| manifest.json | committed entries | hand-authored ref-pinned manifest | Yes (real schema-valid content; example source is a documented placeholder for the smoke) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Boot harness + manifest schema tiers (the phase's automated proof) | `cd api && uv run pytest tests/boot tests/integration/test_manifest_schema.py -q` | 25 passed in 134.84s | ✓ PASS |
| Boot script parse-clean | `bash -n burrow-boot.sh` | exit 0 | ✓ PASS |
| Provisioner parse-clean | `bash -n provision-template.sh` | exit 0 | ✓ PASS |
| Frozen ttyd tail | non-comment `--once` count / `--interface 0.0.0.0` count | 0 / 3 | ✓ PASS |
| No token-in-URL | `grep '://x-access-token:'` | 0 | ✓ PASS |
| Boot enum == schema enum | grep `IN("claude-plugin","binary","npm-global")` | match | ✓ PASS |
| Repo-wide SPDX gate (what CI runs) | `uvx --with charset-normalizer reuse lint` | 242/242 compliant (exit 0) after commit 607c49d | ✓ PASS |
| Real worker boot / plugin load | (dev-homelab smoke) | n/a | ? SKIP → human |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| WORK-02 | 03-01, 03-03 | Worker boots via burrow-boot.sh: pulls CLAUDE.md + manifest, clones project, launches ttyd into Claude Code | ✓ SATISFIED | SC-1 + SC-3 truths verified; REQUIREMENTS.md marks WORK-02 Complete with the 03-01/03-02/03-03 breakdown. |
| WORK-05 | 03-02, 03-03 | Versioned manifest; claude-plugin pulled fresh, binary/npm-global baked | ✓ SATISFIED | SC-2 truth verified; manifest + schema + CI drift gate + idempotent install; REQUIREMENTS.md marks WORK-05 Complete. |

No orphaned requirements: ROADMAP maps exactly WORK-02 + WORK-05 to Phase 3, both claimed by plan frontmatter and both verified. (SC-4 / ADR-0009 is a phase deliverable, not a REQ ID.)

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (Phase-3 source files) | — | TBD/FIXME/XXX/HACK/PLACEHOLDER | — | None found in any modified source file. |
| `manifest.json` | 5-8 | `example-claude-plugin` placeholder source | ℹ️ Info | Documented intentional placeholder; the operator swaps in a real public repo before the smoke. Validates the SHAPE (schema + boot gate); does not block WORK-05. |
| `provision-template.sh` | 73-74 | `worker.env` placeholder created, not sourced by boot script | ℹ️ Info | REVIEW IN-04; CONTROL_PLANE arrives via the systemd unit EnvironmentFile (out of this phase's review set) — track at the smoke. |
| `burrow-boot.sh` | 289 | fixed `/tmp/cc-worker-config` + `rm -rf` | ℹ️ Info | REVIEW IN-01; safe in the v1 single-tenant LXC; harden if a shared user namespace is ever introduced. |

REVIEW.md WR-01..WR-05 (5 warnings) are all **confirmed fixed in code**, each with a dedicated regression test: WR-01 `redact_secrets` (format-aware + live-value, bounded `extglob`); WR-02 jq gate at schema parity (schemaVersion + additionalProperties + minLength); WR-03 `GIT_TERMINAL_PROMPT=0` on the plugin clone (+ static guard test); WR-04 captured-rows iteration (not process substitution); WR-05 null/empty bootconfig-field validation before any git/cp. All corresponding tests pass.

### Human Verification Required

5 items require the dev-homelab / real-Proxmox smoke (none are CI failures — they are the documented "looks done but isn't" acceptance gate):

1. **Real worker boot + ttyd Claude session** — re-run `20-create-template.sh`, boot a real worker, confirm fetch→clone→CLAUDE.md→live ttyd; a failure surfaces as `boot.error` (SC-1 real half).
2. **`resolve_vmid` hostname parse** vs the operator-recorded `30-network-notes.md`/ADR-0004 mapping ([ASSUMED]).
3. **`x-access-token` username convention** vs the operator's pending `mint_repo_credential` mechanism (A2/A3).
4. **Config-repo (cc-worker-config) auth model** with the project-scoped credential (A5/Open-Q-1).
5. **`enabledPlugins` on-disk shape for claude-code@2.1.170** + real plugin load (A1/Open-Q-2).

### Gaps Summary

**RESOLVED (post-verification, commit 607c49d).** The single actionable gap — the repo-wide `uvx reuse lint` CI gate (CICD-06) flagging 5 Phase-3 planning docs without SPDX headers — has been fixed: the SPDX two-line header was added before the YAML frontmatter of all 5 docs (matching the prior-phase convention), and `reuse lint` now reports **242/242 compliant (exit 0)**. The remaining open items are the 5 dev-homelab smoke confirmations (human verification), which are the documented "looks done but isn't" acceptance gate, not CI failures — hence status `human_needed`.

_Original gap (now resolved), for the record:_ **the repo-wide `uvx reuse lint` CI gate (CICD-06) was NON-COMPLIANT.** `uvx reuse lint` flags exactly 5 Phase-3 planning docs — `03-01-PLAN.md`, `03-02-PLAN.md`, `03-03-PLAN.md`, `03-REVIEW.md`, `03-VALIDATION.md` — none of which carry the SPDX two-line header or a REUSE.toml annotation. CI's `static-gates` job runs `uvx reuse lint` repo-wide (`.github/workflows/ci.yml:91`), so this step fails the build. The phase SUMMARYs asserted "reuse lint green," but that was verified with per-file `reuse lint-file` on the newly-added *source* files, not the repo-wide `reuse lint` the CI actually invokes — so the claim did not cover the gap. Plan 03-03 (CI wiring) was the intended fix site (deferred-items.md + the 03-03 SUMMARY say so), but 03-03's deviations record "None," leaving it unclosed.

Fix is small and unambiguous: add the SPDX two-line header to the 5 docs, or add a `.planning/phases/**` (or explicit-path) `[[annotations]]` block to `REUSE.toml`. Either makes the repo-wide gate green.

Everything else is verified: the goal is achieved in code, all 4 success criteria hold, both requirement IDs are satisfied, all key links are wired, the credential-hygiene guarantee is structural and test-proven, and the 5 review warnings are genuinely fixed with regression tests.

---

_Verified: 2026-06-11_
_Verifier: Claude (gsd-verifier)_
