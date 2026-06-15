---
phase: 06-ci-tooling-robustness
plan: 01
status: complete
requirements_completed: [CICD-07, CICD-08]
key_files:
  modified:
    - .github/workflows/ci.yml
    - REUSE.toml
    - .gitignore
  created:
    - .planning/phases/06-ci-tooling-robustness/06-CONTEXT.md
    - .planning/phases/06-ci-tooling-robustness/06-01-PLAN.md
commits:
  - 8728c59 docs(06): context + plan for CI/tooling robustness
  - b79730a ci(06): pin charset-normalizer for reuse lint (CICD-07)
  - 5cfdf83 chore(06): license .planning artifacts via REUSE.toml; gitignore uat-shots (CICD-08)
---

# Phase 6 Plan 01 — Summary

## What shipped

- **CICD-07** — `.github/workflows/ci.yml` `spdx · reuse lint` step pins the encoding
  module: `uvx --with charset-normalizer reuse lint` (was bare `uvx reuse lint`). Bare reuse
  raises `NoEncodingModuleError` on hosts without libmagic (this Windows dev box + slim
  runners); the pin supplies a pure-Python encoder so the gate actually executes.
- **CICD-08** — reconciled the SPDX-vs-parser tension. Root cause confirmed: `*-PLAN.md` must
  keep YAML frontmatter on line 1 for the gsd-sdk `phase-plan-index` parser (a leading SPDX
  HTML comment makes it fall back to wave-1/no-deps), so PLAN files can't carry an inline
  header. Resolution: **GSD planning artifacts are licensed via `REUSE.toml`, not inline
  headers** — added a `.planning/**` (`*.md`, `*.json`, `.gitignore`) annotation block with
  the convention documented in-comment. `ui/uat-shots/` (ephemeral UAT screenshots) added to
  `.gitignore`. CICD-06 preserved — only `.planning` is globbed; real source dirs still
  require their inline two-line header.

## Verification (oracle)

- `uvx --with charset-normalizer reuse lint` → **compliant, 309/309** ("Your project is
  compliant with version 3.3 of the REUSE Specification"). Was 299/312 (13 files missing).
- `gsd-sdk phase-plan-index 5` → waves **1,2,2,3** unchanged (parser regression clean); the new
  `06-01-PLAN.md` reads `wave: 1` / `depends_on: []`.
- CICD-06 intact: REUSE.toml adds no `api/**` or `ui/src/**` glob.

## Convention documented (for future plans)

> GSD planning artifacts (`.planning/**/*.md`, `*.json`) are licensed via `REUSE.toml`, NOT
> inline SPDX headers, so `*-PLAN.md` frontmatter stays on line 1 for the gsd-sdk
> `phase-plan-index` parser. Source files keep their inline two-line header (CICD-06).

Stated in the `REUSE.toml` comment block (the durable home next to the rule it governs).

## Deviations

- Phase executed **inline by the orchestrator** (not via the gsd-executor subagent), given the
  small, fully-specified, mechanical scope (4 files, hard pass/fail oracle). All standard GSD
  artifacts produced.
- Convention documented in `REUSE.toml` rather than `CONTRIBUTING.md`/`CLAUDE.md` — those are
  pre-existing **untracked** governance docs; committing them is out of this phase's scope
  (flagged to the operator).

## Notes / follow-ups

- Untracked governance + docs files (`CLAUDE.md`, `CONTRIBUTING.md`, `LICENSE`, `NOTICE`,
  `README.md`, `SECURITY.md`, `CLA/`, `docs/`, `design/`) predate this session and remain
  uncommitted — recommend a separate `docs:`/`chore:` commit to land them.
- First real CI run (ACC-02) will now exercise the pinned reuse step on Ubuntu; this phase
  proved it locally on Windows.
