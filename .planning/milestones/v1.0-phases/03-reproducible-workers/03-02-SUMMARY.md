<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 03-reproducible-workers
plan: 02
subsystem: infra
tags: [bash, boot, manifest, json-schema, jq, jsonschema, pytest, plugins, reproducibility, fail-closed]

# Dependency graph
requires:
  - phase: 03-reproducible-workers
    provides: "Plan 03-01's live pull-at-boot spine (resolve_vmid + fetch_bootconfig + clone_with_token + CLAUDE.md copy + FROZEN ttyd) and the hermetic api/tests/boot harness (fake control plane + file:// bare repos + stub ttyd) this plan extends"
  - phase: 01-control-plane
    provides: "the frozen GET /api/v1/internal/bootconfig endpoint contract the harness's fake control plane mirrors"
provides:
  - "The versioned plugin manifest (cc-worker-config/plugins/manifest.json) + the shared manifest.schema.json — the single source of truth for both the CI drift test and the boot-time jq gate"
  - "process_manifest (fail-closed jq required-keys + type-enum gate) + install_claude_plugin (rm -rf + pinned --branch clone + enabledPlugins write) in burrow-boot.sh, wired after the config clone, before the project clone"
  - "The CI manifest-drift gate (test_manifest_schema.py) + three boot-harness tests proving claude-plugin-only install, two-boots-identical idempotence (SC-2), and fail-closed unknown-type rejection"
affects: [03-03-adr-ci, dev-homelab-smoke]

# Tech tracking
tech-stack:
  added: []  # jsonschema (dev/CI) + jq (bake) already landed in Plan 03-01; this plan adds a confined jsonschema.* mypy override only
  patterns:
    - "Single-source-of-truth schema/enum: manifest.schema.json drives the CI test AND the boot-time jq gate enforces the IDENTICAL required-keys + type enum so CI and boot never diverge"
    - "Fail-closed manifest gate: unknown/unsupported type or missing key → non-zero → ERR trap → boot fails (never skip-and-continue)"
    - "Idempotent pinned-ref plugin install: rm -rf the dest + git clone --depth=1 --branch <immutable-ref> → byte-identical plugin tree across boots (SC-2)"
    - "Manifest-driven hermetic boot harness: a manifest_config_repo factory seeds claude-plugin source bare repos (file://, pinned tag) into the config repo's plugins/manifest.json"

key-files:
  created:
    - "cc-worker-config/plugins/manifest.json"
    - "cc-worker-config/plugins/manifest.schema.json"
    - "api/tests/integration/test_manifest_schema.py"
    - ".planning/phases/03-reproducible-workers/03-02-SUMMARY.md"
  modified:
    - "cc-worker-config/lxc/worker-template/burrow-boot.sh"
    - "api/tests/boot/conftest.py"
    - "api/tests/boot/test_burrow_boot.py"
    - "REUSE.toml"
    - "api/pyproject.toml"

key-decisions:
  - "manifest.schema.json is THE single source of truth: the boot-time jq gate enforces the same required-keys + type enum IN(claude-plugin,binary,npm-global) as the schema, so a CI-green manifest and a boot-passing manifest are the same set"
  - "install_claude_plugin prepends https:// only when the source has no scheme — a bare github.com/<org>/<repo> production form gets https://, while an already-schemed file:// hermetic-test source passes through unchanged"
  - "The committed manifest documents the bake-vs-pull split inline: one claude-plugin (pulled fresh, pinned v1.0.0) plus the baked rtk (binary) + gsd (npm-global) reference entries that the boot SKIPS"
  - "Both comment-less JSON files are licensed via a REUSE.toml [[annotations]] block (they cannot hold an inline // header a JSON parser would reject), reusing the existing comment-less-JSON block"

patterns-established:
  - "Fail-closed jq structural gate mirroring a JSON-Schema (required keys + enum) as the boot-time half of a shared CI/boot validation contract"
  - "Idempotent pinned-ref clone (rm -rf + --depth=1 --branch <tag/SHA>) for byte-reproducible plugin trees across boots"

requirements-completed: [WORK-05]

# Metrics
duration: 38min
completed: 2026-06-11
---

# Phase 3 Plan 02: Reproducible Plugin Manifest + Fail-Closed Boot Install Summary

**A versioned plugin manifest + a shared JSON-Schema (the single source of truth) drive both a CI drift gate and a fail-closed boot-time jq gate; burrow-boot.sh now installs only claude-plugin types fresh via an idempotent pinned-ref clone (byte-identical across two boots, SC-2) while binary/npm-global types are skipped (baked), with an unknown type rejecting the boot non-zero — all proven hermetically by pytest with zero real Proxmox.**

## Performance

- **Duration:** 38 min
- **Started:** 2026-06-11T14:45:00Z
- **Completed:** 2026-06-11T15:22:49Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 9 (4 created, 5 modified)

## Accomplishments

- Shipped the WORK-05 manifest slice: `cc-worker-config/plugins/manifest.json` (schemaVersion 1.0.0, one claude-plugin pinned to an immutable `v1.0.0` tag plus the baked rtk/gsd reference entries) validated against `cc-worker-config/plugins/manifest.schema.json` (draft 2020-12, `additionalProperties: false` at both levels, the fail-closed `type` enum) by a CI drift gate (`test_manifest_schema.py`).
- Added `process_manifest` + `install_claude_plugin` to `burrow-boot.sh`, wired AFTER the config clone and BEFORE the project clone. The jq gate enforces the SAME required-keys + `type` enum as the schema (single source of truth); only `claude-plugin` types are pulled fresh (idempotent `rm -rf` + `git clone --depth=1 --branch <ref>`); `binary`/`npm-global` are skipped (baked). The FROZEN ttyd tail was left untouched (`--interface 0.0.0.0` present, `--once` absent).
- Proved the four WORK-05 truths with tests: schema validation + unknown-type rejection (CI), and claude-plugin-only install + two-boots-identical idempotence (SC-2) + fail-closed unknown-type-fails-boot (boot harness). Full suite 139 passed.

## Task Commits

Each task was committed atomically (both TDD: RED test commit → GREEN implementation commit):

1. **Task 1 (RED): Manifest JSON-Schema + failing CI drift gate** - `01521b6` (test)
2. **Task 1 (GREEN): Committed plugin manifest + REUSE license entry** - `974d837` (feat)
3. **Task 2 (RED): Failing boot-harness tests for manifest processing** - `db744ce` (test)
4. **Task 2 (GREEN): Boot-time manifest processing (jq gate + idempotent install)** - `2a0d71f` (feat)

**Plan metadata:** committed with this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md + deferred-items.md.

_The schema (`manifest.schema.json`) and the CI test (`test_manifest_schema.py`) existed on disk from an earlier interrupted run; they were reconciled against the plan verbatim and committed RED-first (the manifest.json artifact was still missing, so the test legitimately failed)._

## Files Created/Modified

- `cc-worker-config/plugins/manifest.json` - The versioned manifest: schemaVersion 1.0.0, one `example-claude-plugin` (claude-plugin, pinned `v1.0.0`, placeholder/public source) + the baked `rtk` (binary) and `gsd` (npm-global) reference entries documenting the bake-vs-pull split. No secrets, no real topology.
- `cc-worker-config/plugins/manifest.schema.json` - The shared JSON-Schema (draft 2020-12): `required [schemaVersion, plugins]`, per-entry `required [source, ref, type]`, `type` enum `[claude-plugin, binary, npm-global]`, `additionalProperties: false` at both levels (fail-closed). The single source of truth shared with the boot-time jq gate.
- `cc-worker-config/lxc/worker-template/burrow-boot.sh` - Added `process_manifest` (fail-closed jq required-keys + type-enum gate) and `install_claude_plugin` (rm -rf + pinned `--branch` clone + `enabledPlugins[$n]=true` settings write); wired `process_manifest /tmp/cc-worker-config/plugins/manifest.json` between the config clone and the project clone. FROZEN ttyd tail unchanged.
- `api/tests/integration/test_manifest_schema.py` - The CI manifest-drift gate: validates the committed manifest, rejects an unknown type fail-closed, guards the `parents[3]` repo-root depth, and forbids a mutable `main` ref on a claude-plugin (Pitfall 1, SC-2).
- `api/tests/boot/conftest.py` - Hoisted the bare-repo seeder to a module helper; added the `manifest_config_repo` factory (seeds claude-plugin source bare repos + writes `plugins/manifest.json`, with `include_binary`/`bad_type` variants) and a `serve_bootconfig` context manager; the existing `bare_repos` fixture now seeds a manifest so the Plan-01 happy-path tests still pass under the now-required manifest.
- `api/tests/boot/test_burrow_boot.py` - Added `test_only_claude_plugins_installed`, `test_two_boots_identical_plugin_tree`, `test_bad_manifest_fails_boot`.
- `REUSE.toml` - Added both comment-less JSON files to the existing comment-less-JSON `[[annotations]]` block.
- `api/pyproject.toml` - Added a confined `jsonschema.*` `ignore_missing_imports` mypy override (mirrors the existing `proxmoxer.*` one) so `--strict` stays in force on first-party code.

## Decisions Made

- **Single source of truth, two enforcers:** `manifest.schema.json` is authoritative; the boot-time jq gate enforces the IDENTICAL required-keys + `type` enum `IN(claude-plugin,binary,npm-global)`. A manifest that passes CI passes the boot gate and vice-versa — CI and boot can never diverge (the locked decision).
- **Scheme-aware install source:** `install_claude_plugin` prepends `https://` only when the source lacks a `://` scheme, so the production `github.com/<org>/<repo>` form resolves to HTTPS while a hermetic `file://` test remote passes through unchanged. This keeps the same code path under test and in production.
- **Manifest documents the split:** the committed manifest carries the baked `rtk` (binary) and `gsd` (npm-global) entries alongside the pulled `claude-plugin`, so the bake-vs-pull contract is self-documenting and the skip path is exercised by `test_only_claude_plugins_installed`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CRLF-terminated jq output left a trailing carriage return on the ref**
- **Found during:** Task 2 (GREEN — first boot-harness run)
- **Issue:** `jq` on the Windows dev host emits `\r\n` line endings, so `IFS=$'\t' read ... ref` captured `ref="v1.0.0\r"`; `git clone --branch "v1.0.0\r"` failed with `Remote branch v1.0.0? not found`. The same hazard exists for a CRLF-saved manifest on any host.
- **Fix:** Added `\r` to the loop `IFS` (`IFS=$'\t\r'`) so a trailing carriage return is stripped from the last field. Harmless on Linux (no `\r` present).
- **Files modified:** `cc-worker-config/lxc/worker-template/burrow-boot.sh`
- **Verification:** All three manifest boot tests pass; the claude-plugin clones to the pinned `v1.0.0` tag.
- **Committed in:** `2a0d71f` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] The Plan-01 bare_repos fixture had no manifest, so process_manifest failed the boot fail-closed**
- **Found during:** Task 2 (GREEN — full boot-suite regression run)
- **Issue:** `process_manifest` now requires `plugins/manifest.json` in the cloned config repo (a missing manifest is fail-closed). The Plan-01 `bare_repos` fixture seeded a config repo WITHOUT a manifest, so `test_fetch_then_clone_happy_path` and `test_no_credential_leak` regressed to non-zero exits.
- **Fix:** Extended the `bare_repos` fixture to seed a `plugins/manifest.json` pinning one claude-plugin to a real seeded `file://` source repo (so the happy path installs cleanly). No production behavior change — the live config repo always carries a manifest.
- **Files modified:** `api/tests/boot/conftest.py`
- **Verification:** Full boot suite (8 tests) green; full api suite 139 passed.
- **Committed in:** `2a0d71f` (Task 2 GREEN commit)

**3. [Rule 3 - Blocking] jsonschema has no type stubs → mypy --strict failure**
- **Found during:** Task 2 (static gate)
- **Issue:** `import jsonschema` in `test_manifest_schema.py` tripped `mypy --strict` (`import-untyped` — jsonschema ships no `py.typed`/stubs).
- **Fix:** Added a confined `jsonschema.*` `ignore_missing_imports` override to `api/pyproject.toml`, mirroring the existing `proxmoxer.*` discipline (strict stays in force on all first-party code).
- **Files modified:** `api/pyproject.toml`
- **Verification:** `mypy --strict tests/boot tests/integration/test_manifest_schema.py` → no issues.
- **Committed in:** `2a0d71f` (Task 2 GREEN commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All three were necessary for correctness and to keep the existing gates green. No scope creep — the script's external manifest contract matches the plan; the CRLF fix is portable hardening, the fixture/manifest seed reflects the now-required manifest, and the mypy override follows the established confined-import discipline.

## Issues Encountered

- **Pre-existing REUSE non-compliance on planning docs (out of scope):** `uvx reuse lint` reports 4 files missing SPDX info — `03-01/02/03-PLAN.md` and `03-VALIDATION.md` — all GSD planning artifacts authored without an inline header, unrelated to this plan's change set. Logged to `deferred-items.md`; my two new JSON files ARE covered by the REUSE.toml annotation (233/237, the 4 gaps are exactly those planning docs). Resolution belongs in the 03-03 CI/docs plan, not here.
- **shellcheck unavailable on the Windows dev host** (carried from Plan 00-06/03-01): `burrow-boot.sh` passes `bash -n` (parse-clean); shellcheck static analysis is CI-wired by Plan 03-03.

## Known Stubs

- **`example-claude-plugin` manifest entry is a placeholder source** (`github.com/brave-bear-studios/example-claude-plugin`, pinned `v1.0.0`). This is intentional and documented inline: the manifest holds non-secret placeholder/public sources only (CLAUDE.md — no real topology). The operator replaces it with a real public claude-plugin repo before the dev-homelab smoke. It does not block WORK-05 — the schema/CI gate and the boot gate validate the SHAPE; the real plugin load is the smoke gate.

## [ASSUMED] details to confirm at the dev-homelab smoke (NOT CI)

- **`enabledPlugins[<name>]=true` on-disk shape for `claude-code@2.1.170`** (A1 / Open-Q-2): `install_claude_plugin` writes `~/.claude/settings.json` `enabledPlugins[$n]=true` for a directory install. The precise enablement shape for a non-marketplace directory install on 2.1.170 is [ASSUMED] — confirm at the smoke (`claude plugin list` / `--debug`). The master CLAUDE.md copy is independent and works regardless.
- **Real plugin-load + `enabledPlugins` round-trip** is the dev-homelab smoke (human-verify), NOT a CI gate — the harness proves the SHAPE (clone to `~/.claude/plugins/<name>`, settings write, idempotence), the homelab proves the live load.
- **Template rebuild:** the live worker runs the old boot script until `20-create-template.sh` is re-run on the homelab.

## Threat Flags

None — no new security surface beyond the plan's `<threat_model>`. The fail-closed jq gate (T-03-06) and the immutable-ref pin + idempotent clone (T-03-07) are implemented exactly as the threat register prescribes; the manifest holds only non-secret placeholder sources (T-03-08 accept). No new network listener, auth path, or trust boundary was introduced.

## Next Phase Readiness

- WORK-05 is delivered and CI-green: the manifest is schema-validated, only claude-plugin types are pulled fresh (idempotent, byte-reproducible), binary/npm-global are skipped, and an unknown type fails the boot fail-closed.
- WORK-02 is now fully delivered (Plan 03-01 fetch/clone/ttyd half + this plan's manifest clause).
- Plan 03-03 lands ADR-0009 (plugin cadence: boot-time-latest) + the CI wiring (shellcheck on burrow-boot.sh + the tests/boot and manifest pytest tiers) and should resolve the 4 deferred planning-doc SPDX gaps.

## Self-Check: PASSED

---
*Phase: 03-reproducible-workers*
*Completed: 2026-06-11*
