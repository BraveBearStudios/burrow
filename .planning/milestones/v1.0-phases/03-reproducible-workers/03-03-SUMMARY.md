<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 03-reproducible-workers
plan: 03
subsystem: infra
tags: [adr, ci, shellcheck, pytest, plugin-cadence, boot-time-latest, reproducibility, github-actions]

# Dependency graph
requires:
  - phase: 03-reproducible-workers
    provides: "Plan 03-01's live boot spine + hermetic api/tests/boot harness and Plan 03-02's manifest.json + manifest.schema.json + api/tests/integration/test_manifest_schema.py — the exact test paths the new CI pytest step runs"
  - phase: 00-foundation
    provides: "the Tier-0 static-gates CI job (SHA-pinned actions, working-directory: api pattern, permissions: contents: read) this plan extends, and the ADR-0002 Nygard template ADR-0009 mirrors"
provides:
  - "ADR-0009 (plugin cadence: boot-time-latest) — the recorded B4 decision making reproducibility semantics explicit (SC-4): cadence is boot-time-latest, reproducibility via manifest ref-pinning (NOT config-repo snapshotting)"
  - "CI enforcement of the Phase-3 gates: a shellcheck step on burrow-boot.sh + provision-template.sh, and an api pytest step running tests/boot + test_manifest_schema.py so boot-script regressions and manifest drift fail the build"
affects: [dev-homelab-smoke]

# Tech tracking
tech-stack:
  added: []  # no new dependency, no new third-party action — shellcheck is preinstalled on ubuntu-latest; pytest runs via the already-SHA-pinned setup-uv
  patterns:
    - "Phase-gate CI step placement: hermetic pytest tier runs after `api · install (frozen)` (working-directory: api); shellcheck is a repo-root step (no working-directory)"
    - "No-new-action discipline: a preinstalled runner tool (shellcheck) over a third-party action keeps the SHA-pin convention intact (T-03-09 mitigation)"

key-files:
  created:
    - "docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md"
    - ".planning/phases/03-reproducible-workers/03-03-SUMMARY.md"
  modified:
    - ".github/workflows/ci.yml"

key-decisions:
  - "ADR-0009 mirrors ADR-0002's Nygard skeleton exactly (Status/Context/Decision/Consequences/Revisit trigger) — the repo's established ADR house style (## headings only, SPDX comment front-matter)"
  - "shellcheck runs via the ubuntu-latest preinstalled binary, NOT a third-party action — preserves the repo's SHA-pin convention and adds zero new CI trust surface (T-03-09)"
  - "The pytest step runs the SAME command verified green locally (uv run pytest tests/boot tests/integration/test_manifest_schema.py -q) — scoped to the Phase-3 tiers, not the full suite, so the new gate is targeted"
  - "shellcheck + pytest steps were ADDED to the existing static-gates job, not a new job — keeps one runner/one uv install; existing gates, SHA pins, and permissions: contents: read untouched"

patterns-established:
  - "CI gate-wiring without unpinning: ADD steps to static-gates, prefer a preinstalled runner tool over a new action when one exists"

requirements-completed: []  # WORK-02 (03-01) + WORK-05 (03-02) were already marked complete; this plan delivers SC-4 (the recorded cadence ADR) and CI-enforces those gates — no new requirement closes here

# Metrics
duration: 9min
completed: 2026-06-11
---

# Phase 3 Plan 03: ADR-0009 (Plugin Cadence) + CI Gate Wiring Summary

**The B4 plugin-cadence decision is now recorded as ADR-0009 — cadence is boot-time-latest (pull cc-worker-config HEAD each boot) with reproducibility delivered by manifest ref-pinning (immutable tag/SHA per claude-plugin), NOT config-repo snapshotting — making reproducibility semantics explicit (SC-4); and CI now lints burrow-boot.sh + provision-template.sh with shellcheck and runs the boot-harness + manifest-schema pytest tiers, so a boot-script regression or manifest drift fails the build instead of the homelab.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-11T15:40:00Z
- **Completed:** 2026-06-11T15:49:00Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- Authored `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` mirroring ADR-0002's Nygard skeleton exactly (SPDX comment front-matter, `# ADR-0009` title, `## Status` (Accepted) / `## Context` / `## Decision` / `## Consequences` / `## Revisit trigger`). The Decision records cadence = boot-time-latest (pull `cc-worker-config` branch HEAD each boot, tech-spec §988) with reproducibility from manifest ref-pinning (immutable tag/SHA per `claude-plugin`), explicitly NOT config-repo snapshotting; the Context records the plugin-type split (`binary`/`npm-global` baked at provision, only `claude-plugin` pulled fresh) and why boot-time-latest was chosen over snapshot-at-create; the Consequences note two boots of the same manifest → identical plugin tree (SC-2) and that a `ref: "main"` is intentionally non-reproducible "latest" (Pitfall 1); the Revisit trigger names per-workspace pinning / snapshot-at-create, deferred until the manifest stabilizes. SC-4 satisfied.
- Wired `.github/workflows/ci.yml`: added a `shellcheck` step (the `ubuntu-latest` preinstalled binary — no third-party action) linting `burrow-boot.sh` + `provision-template.sh`, and an `api · pytest (boot + manifest tiers)` step running `uv run pytest tests/boot tests/integration/test_manifest_schema.py -q` (working-directory: api). Both steps were ADDED to the existing `static-gates` job; the existing static gates, SHA pins, and `permissions: contents: read` are untouched.
- Verified the exact CI pytest command green locally (12 passed in 74s) before wiring it, and confirmed the full api suite still green (139 passed — no regression).

## Task Commits

Each task was committed atomically:

1. **Task 1: Author ADR-0009 (plugin cadence: boot-time-latest)** — `05ca051` (docs)
2. **Task 2: Wire CI — shellcheck on burrow-boot.sh + a pytest job for the boot + manifest tiers** — `f508b65` (ci)

**Plan metadata:** committed with this SUMMARY + STATE.md + ROADMAP.md.

## Files Created/Modified

- `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` — The B4 plugin-cadence decision record: boot-time-latest cadence + manifest ref-pinning reproducibility, full Nygard section skeleton mirroring ADR-0002, SPDX two-line header in the markdown comment front-matter. `uvx reuse lint-file` clean.
- `.github/workflows/ci.yml` — Added a `shellcheck · worker boot scripts` step (repo-root, no working-directory, preinstalled binary) and an `api · pytest (boot + manifest tiers)` step (working-directory: api, after `api · ruff check`). No third-party action added; all four existing `uses:` lines keep their SHA pin + trailing version comment; `permissions: contents: read` on both the top-level and the static-gates job unchanged.

## Decisions Made

- **ADR-0009 mirrors ADR-0002 verbatim in structure:** the repo's ADR house style is the Nygard five-section skeleton with `##` headings only and an SPDX comment front-matter (lines 1-4). Copied that skeleton exactly so the ADR set stays consistent; the content is the CONTEXT.md B4 decision.
- **shellcheck via the preinstalled binary, not an action:** `shellcheck` ships on `ubuntu-latest`, so a plain `run: shellcheck …` adds the gate with zero new third-party action — preserving the repo's SHA-pin convention and adding no new CI trust surface (T-03-09 mitigation). No inline `# shellcheck disable=` directive was needed (none added to the scripts).
- **pytest step scoped to the Phase-3 tiers:** the new step runs only `tests/boot` + `test_manifest_schema.py` (the boot-harness + manifest-drift gates), not the full suite — the targeted gate the ci.yml header reserved for "the test pyramid … lands later", scoped here to Phase-3. Verified green locally first (the exact command).
- **Steps ADDED to static-gates, not a new job:** one runner, one `uv sync --frozen`, one Node install — the pytest step reuses the already-installed api deps and the shellcheck step is a cheap repo-root run. No reorder or removal of existing gates.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed their planned artifacts (ADR-0009 + the two CI steps) with no auto-fixes, no blocking issues, and no architectural decisions. No new third-party action was needed (as the plan anticipated), so the SHA-pin convention required no change.

## Issues Encountered

- **shellcheck remains unavailable on the Windows dev host** (carried from Plans 00-06/03-01/03-02): the new `shellcheck` CI step is therefore unverifiable locally — CI is the authority, exactly the gap this plan closes. Both scripts pass `bash -n` locally and were authored against the `common.sh` strict-mode/`err_trap` idiom; the first CI run is the confirmation that they are shellcheck-clean (the plan's verification note explicitly flags this).
- **`reuse lint` on the Windows host needs the `charset-normalizer` extra** (known): verified ADR-0009's SPDX header with `uvx --with charset-normalizer reuse lint-file` (exit 0).

## Threat Flags

None — no new security surface beyond the plan's `<threat_model>`. The plan added NO new third-party action (shellcheck is preinstalled on `ubuntu-latest`; pytest runs via the already-SHA-pinned `setup-uv`), so the repo's SHA-pin convention and `permissions: contents: read` least-privilege posture are unchanged (T-03-09 mitigated as prescribed). The new pytest + shellcheck steps are the T-03-10 mitigation — manifest drift and boot-script regressions now fail the build, not the dev-homelab smoke. No package-manager install was added (docs + CI YAML only; T-03-SC accept).

## Next Phase Readiness

- **Phase 3 is complete.** SC-4 (the recorded cadence decision) is delivered via ADR-0009; the WORK-02 (boot spine, Plan 03-01) and WORK-05 (manifest, Plan 03-02) gates are now CI-enforced (shellcheck + the boot/manifest pytest tiers).
- **Carried to the dev-homelab smoke (NOT CI):** the real worker boot + template rebuild (`20-create-template.sh` re-run), the `enabledPlugins` on-disk shape for `claude-code@2.1.170` [ASSUMED], the `resolve_vmid` hostname-suffix parse vs `30-network-notes.md`/ADR-0004, the `x-access-token` username convention, and the config-repo auth model (A2/A3/A5). The first CI run after merge confirms the shellcheck step is clean on both scripts (the only locally-unverifiable item).

## Self-Check: PASSED

- `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` — FOUND (contains "boot-time-latest" ×8, all five `##` sections, "snapshot-at-create" in the Revisit trigger).
- `.github/workflows/ci.yml` — FOUND with the shellcheck step + the `uv run pytest tests/boot …` step; YAML parses; all four `uses:` SHA-pinned; `permissions: contents: read` intact.
- Commit `05ca051` (ADR-0009) — FOUND.
- Commit `f508b65` (ci.yml) — FOUND.

---
*Phase: 03-reproducible-workers*
*Completed: 2026-06-11*
