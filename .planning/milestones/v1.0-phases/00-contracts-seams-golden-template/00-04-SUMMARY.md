<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 00-contracts-seams-golden-template
plan: 04
subsystem: infra
tags: [ci, github-actions, biome, typescript, reuse, spdx, vite-scaffold, sha-pinning]

requires:
  - phase: 00-01
    provides: api/pyproject.toml gate config (ruff/mypy/pytest) + uv.lock the static-gates job mirrors
provides:
  - "static-gates CI job running every Tier-0 gate (ruff lint+format, mypy --strict, uv lock --check, tsc --noEmit, biome ci, reuse lint) and failing on any violation"
  - "Conventional-Commit PR-title validation job (squash-merge title gate)"
  - "minimal ui/ scaffold (Biome 2.4.16 + TS 6.0.3 + committed lockfile) giving the JS gates a real target"
  - "repo-wide SPDX compliance: LICENSES/AGPL-3.0-or-later.txt + REUSE.toml so reuse lint is green (100/100)"
affects: [phase-1-control-plane, phase-2-ui, phase-4-release, ci-cd]

tech-stack:
  added: [typescript@6.0.3, "@biomejs/biome@2.4.16", reuse(LICENSES+REUSE.toml), github-actions-ci]
  patterns: [sha-pinned-actions, least-privilege-permissions, reuse-toml-for-non-headerable-only, biome2-config-written-fresh]

key-files:
  created:
    - .github/workflows/ci.yml
    - REUSE.toml
    - LICENSES/AGPL-3.0-or-later.txt
    - ui/package.json
    - ui/package-lock.json
    - ui/tsconfig.json
    - ui/biome.json
    - ui/src/placeholder.ts
  modified:
    - .env.example
    - .gitignore
    - .planning/*.md (inline SPDX headers added to reach reuse-lint green)

key-decisions:
  - "Third-party actions SHA-pinned to commit (checkout v4.3.1, setup-uv v6.8.0, setup-node v4.4.0); amannn/action-semantic-pull-request carries a full-length placeholder SHA + literal '# TODO pin exact SHA' per plan (defers the exact pin without leaking the Action choice into implementation)"
  - "REUSE.toml declares license ONLY for non-headerable files (lockfiles, comment-less JSON, generated/binary design bundle); never blanket-globs source extensions so a missing inline header still surfaces (CICD-06)"
  - "biome.json written fresh from `biome init` against the 2.4.16 schema; vcs.useIgnoreFile=false (no ui/.gitignore) with includes scoped to src/**"

patterns-established:
  - "Tier-0 gates run with working-directory per app (api/ vs ui/) against committed lockfiles via uv sync --frozen / npm ci"
  - "Least-privilege permissions: top-level contents:read, per-job scoping; full per-job hardening deferred to Phase 4"
  - "Markdown sources with in-body example SPDX strings wrap their body in <!-- REUSE-IgnoreStart/End --> so only the real header tag is read"

requirements-completed: [CICD-01, CICD-06]

duration: 20min
completed: 2026-06-10
---

# Phase 0 Plan 04: Static CI Gates + REUSE/SPDX + ui/ Scaffold Summary

**Tier-0 static-gates GitHub Actions job (SHA-pinned, every ruff/mypy/tsc/biome/reuse/lockfile gate) plus a Conventional-Commit PR-title check, a minimal Biome 2 / TS 6 ui/ scaffold, and repo-wide REUSE/SPDX compliance (100/100, `reuse lint` exit 0).**

## Performance

- **Duration:** 20 min
- **Started:** 2026-06-10T05:17:44Z
- **Completed:** 2026-06-10T05:37:15Z
- **Tasks:** 3
- **Files modified:** 22 (across 3 atomic commits)

## Accomplishments

- `.github/workflows/ci.yml` `static-gates` job: api gates (`uv sync --frozen`, `ruff check`, `ruff format --check`, `mypy . --strict`, `uv lock --check`), ui gates (`npm ci`, `tsc --noEmit`, `biome ci`), and repo-wide `uvx reuse lint` — fails on any violation. Third-party actions SHA-pinned; top-level `permissions: contents: read`.
- `pr-title` job validates the squash-merge PR title against Conventional-Commit grammar via `amannn/action-semantic-pull-request` (placeholder SHA + `# TODO pin exact SHA`).
- Minimal `ui/` scaffold (`burrow-ui`, private) with pinned `typescript@6.0.3` + `@biomejs/biome@2.4.16`, committed `package-lock.json`, a strict `tsconfig.json` (noEmit, bundler resolution), a freshly-authored Biome 2 `biome.json`, and a `//`-headered `placeholder.ts`. `npm ci` + `tsc --noEmit` + `biome ci` all green.
- Repo-wide SPDX compliance: added `LICENSES/AGPL-3.0-or-later.txt` (canonical FSF text), authored `REUSE.toml` for non-headerable files only, and added inline headers to the planning/doc markdown + `.env.example`/`.gitignore` that lacked them. `reuse lint` reports 100/100 compliant (CICD-06).

## Task Commits

Each task was committed atomically (Conventional Commits + Signed-off-by):

1. **Task 1: minimal ui/ scaffold (Biome 2 + TS 6 + placeholder)** - `762f7a4` (feat)
2. **Task 2: static-gates CI workflow + conventional-commit validation** - `8898a9b` (feat)
3. **Task 3: REUSE.toml + repo-wide reuse lint green** - `c3d9154` (feat)

**Plan metadata:** (docs commit — SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `.github/workflows/ci.yml` - static-gates job (all Tier-0 gates, SHA-pinned actions, least-privilege permissions) + pr-title Conventional-Commit job
- `REUSE.toml` - license declaration for non-headerable files (lockfiles, JSON config, design bundle) only
- `LICENSES/AGPL-3.0-or-later.txt` - canonical AGPL-3.0-or-later text so SPDX tags resolve
- `ui/package.json` - burrow-ui, private, pinned typescript@6.0.3 + @biomejs/biome@2.4.16
- `ui/package-lock.json` - committed lockfile (npm ci reproduces it)
- `ui/tsconfig.json` - strict, noEmit, ES2022, moduleResolution bundler, include src
- `ui/biome.json` - fresh Biome 2.4.16 config (linter + formatter; src-scoped)
- `ui/src/placeholder.ts` - trivially-typed export with // SPDX header (Phase-2 placeholder)
- `.env.example`, `.gitignore` - added # SPDX headers (and now tracked)
- `.planning/**/*.md`, `.planning/research/STACK.md` - inline <!-- --> SPDX headers added to reach reuse-lint green

## Decisions Made

- **SHA-pinned every third-party action** to a commit (not a floating `@v` tag), with the resolved version in a trailing comment (T-00-CI mitigation). `amannn/action-semantic-pull-request` carries a deliberate placeholder SHA + `# TODO pin exact SHA` exactly as the plan instructed — the Action is named and pinned in shape, the exact pin is left as an explicit follow-up.
- **REUSE.toml scopes precisely to non-headerable files** (lockfiles, comment-less JSON, the generated/binary `design/Burrow-handoff/**` bundle). It intentionally does NOT blanket-license `**/*.{py,ts,tsx,sh,sql,md}` — every such source keeps its own inline header so a future missing header still fails the gate (protects CICD-06).
- **Biome 2 config written fresh** via `biome init` (2.4.16 schema URL), then trimmed; `vcs.useIgnoreFile` set false because Biome 2 requires the ignore file in its own working dir and the `includes` glob already scopes scanning to `src/**`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Resolved reuse-lint findings beyond REUSE.toml to reach green**
- **Found during:** Task 3 (REUSE.toml + reuse lint)
- **Issue:** `reuse lint` scans the whole working tree. Beyond the planned lockfile/JSON declarations, the baseline lint flagged (a) a missing `LICENSES/AGPL-3.0-or-later.txt` (every SPDX tag was unresolved), (b) planning/doc markdown sources + `.env.example`/`.gitignore` lacking inline headers, (c) one invalid SPDX expression in `00-05-PLAN.md` (an in-body example string with a trailing quote), and (d) the generated/binary `design/Burrow-handoff/**` bundle. Without these, the Task 3 acceptance criterion (`reuse lint` exit 0) could not be met.
- **Fix:** Downloaded the canonical AGPL license text into `LICENSES/`; added inline `<!-- -->`/`#` headers to the headerable sources (NOT via blanket glob — per the ban); wrapped in-body example SPDX strings in three plan files with `<!-- REUSE-IgnoreStart/End -->`; declared the design bundle + lockfiles + JSON config in `REUSE.toml`.
- **Files modified:** LICENSES/AGPL-3.0-or-later.txt, REUSE.toml, .env.example, .gitignore, .planning/**/*.md, .planning/research/STACK.md
- **Verification:** `uvx --with charset-normalizer reuse lint` → "Congratulations! ... compliant", 100/100, exit 0.
- **Committed in:** `c3d9154` (Task 3 commit)

**2. [Rule 3 - Blocking] biome.json vcs.useIgnoreFile flipped to false**
- **Found during:** Task 1 (ui scaffold verify)
- **Issue:** With `useIgnoreFile: true`, `biome ci .` errored ("couldn't find an ignore file in E:\repos\burrow\ui") because Biome 2 looks for the ignore file in its own working dir and there is no `ui/.gitignore`.
- **Fix:** Set `vcs.enabled`/`useIgnoreFile` to false; the `files.includes` glob already restricts scanning to `src/**`, so VCS ignore integration is unnecessary.
- **Files modified:** ui/biome.json
- **Verification:** `npx biome ci .` → "Checked 2 files", exit 0.
- **Committed in:** `762f7a4` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking)
**Impact on plan:** Both were required to satisfy the plan's own acceptance criteria (`reuse lint` exit 0; `biome ci` exit 0). No scope creep — the SPDX header additions were the explicit Task-3 instruction ("resolve every finding by adding the inline header OR declaring in REUSE.toml"); the ban on source-extension blanket globs was honored throughout.

## Known Stubs

Both are intentional and plan-mandated, not omissions:

- `ui/src/placeholder.ts` — a deliberate Phase-0 placeholder (`export const phase0Ready = true`) whose only purpose is to give `tsc`/`biome` a real target. The full UI runtime tree (React 19, Vite 8, xterm, react-mosaic) lands in **Phase 2** per STACK.md / ROADMAP.
- `amannn/action-semantic-pull-request@<sha> # TODO pin exact SHA` in `ci.yml` — the plan explicitly required a placeholder full-length SHA plus the literal `# TODO pin exact SHA` comment rather than a final pin. The exact pin is a tracked follow-up.

## Issues Encountered

- The local `reuse` workaround (`uvx --with charset-normalizer reuse ...`) was used throughout because plain `reuse` fails on this Windows host with `NoEncodingModuleError`. The CI workflow uses plain `uvx reuse lint` (the encoding bug is Windows-only; the Linux runner is unaffected).
- A one-shot helper script (`.spdx_fix.py`) was used to insert markdown headers consistently, then deleted before committing (it is NOT in the index; verified via `git ls-files`).

## User Setup Required

None - no external service configuration required. (When the first PR is opened, the `amannn` placeholder SHA should be replaced with the verified exact release SHA — tracked via the `# TODO pin exact SHA` comment.)

## Next Phase Readiness

- CICD-01 and CICD-06 are satisfied: every later phase is CI-greenable on commit, and the SPDX header is enforced repo-wide from day one.
- The `ui/` scaffold is ready for Phase 2 to layer the full UI tree onto (Vite 8 / React 19 / xterm / react-mosaic) without re-deciding TS/Biome pins.
- Follow-ups: (1) replace the `amannn` placeholder SHA on first PR; (2) Phase 1 adds the test-pyramid jobs (unit/integration/e2e) to `ci.yml`; (3) Phase 4 adds per-job permission hardening + the build/scan/sign release jobs.

## Self-Check: PASSED

- All created files present on disk (ci.yml, REUSE.toml, LICENSES/AGPL-3.0-or-later.txt, ui/ scaffold ×5, SUMMARY).
- All three task commits exist in git history (762f7a4, 8898a9b, c3d9154).
- All Tier-0 gates run green locally (api ruff/format/mypy/lock, ui npm ci/tsc/biome, repo reuse lint 100/100 exit 0).

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
