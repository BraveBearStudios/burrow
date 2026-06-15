<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 6: CI / Tooling Robustness - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — infrastructure phase; one locked convention decision

<domain>
## Phase Boundary

Make the SPDX/REUSE gate and the gsd-sdk `phase-plan-index` parser both run clean on
this Windows host and in CI. Covers CICD-07 (pin the `reuse` encoding dependency) and
CICD-08 (reconcile the SPDX-header-vs-frontmatter convention so PLAN `wave`/`depends_on`
metadata is read AND the repo is REUSE-compliant). Pure CI/tooling/docs — no app code,
no runtime behavior change.

Ground truth captured before planning:
- `uvx reuse lint` (bare) crashes on Windows with `NoEncodingModuleError`. `uvx --with
  charset-normalizer reuse lint` runs. **CICD-07.**
- With reuse running, the project is **NOT compliant: 299/312**. 13 files lack license
  info: the 4 Phase-5 `*-PLAN.md`, `05-REVIEW.md`, `.planning/MILESTONES.md`,
  `.planning/HANDOFF.json`, `.planning/ui-reviews/.gitignore`, and 5 `ui/uat-shots/*.png`.
- `gsd-sdk phase-plan-index 5` **already** reads waves/deps correctly from the
  frontmatter-first PLANs (no SPDX comment before frontmatter). So CICD-08's parser half
  is already satisfied — PLAN.md files MUST keep YAML frontmatter on line 1; the open part
  is making those header-less planning artifacts REUSE-compliant + documenting the rule.
</domain>

<decisions>
## Implementation Decisions

### CICD-07 — reuse encoding dependency
- Pin the encoding module in CI: `.github/workflows/ci.yml` `spdx · reuse lint` step
  becomes `uvx --with charset-normalizer reuse lint` (was bare `uvx reuse lint`).
- Document the same local command (it is the only form that runs on this Windows host).

### CICD-08 — SPDX-vs-parser convention (LOCKED: blanket .planning coverage)
- **GSD planning artifacts are licensed via REUSE.toml, NOT inline headers.** Add a
  REUSE.toml annotation covering `.planning/**/*.md` and `.planning/**/*.json` (and the
  `.planning/**/.gitignore`). This lets `*-PLAN.md` keep YAML frontmatter on line 1 (parser
  requirement) with no leading SPDX comment, and stops every future planning artifact from
  tripping the gate. Source files under `api/`, `ui/`, `cc-worker-config/`, scripts, etc.
  KEEP their inline two-line header (CICD-06 — a missing header on a real source must still
  surface; do NOT blanket-glob those).
- **`ui/uat-shots/`** are ephemeral UAT screenshots → add to `.gitignore` (remove from the
  working tree noise + the REUSE scope), not REUSE.toml.
- **Document the convention** so future PLANs follow it: a clear comment block in REUSE.toml
  + a recorded note. (CONTRIBUTING.md / project CLAUDE.md are currently UNTRACKED governance
  docs — committing them is out of this phase's scope; flag separately.)

### Claude's Discretion
- Exact REUSE.toml annotation grouping/comments.
- Whether to also remove now-redundant inline SPDX from existing `.planning` prose docs
  (CONTEXT/RESEARCH already carry it) — leave them; `aggregate` precedence means both coexist
  harmlessly, and churning every planning file is needless.
</decisions>

<code_context>
## Existing Code Insights

- `REUSE.toml` (repo root) — REUSE 3.x, `version = 1`, `[[annotations]]` blocks with
  `precedence = "aggregate"` already cover lockfiles, comment-less JSON, and the design
  bundle. Add a `.planning` planning-artifacts block here.
- `.github/workflows/ci.yml:100-101` — the `spdx · reuse lint` step (`run: uvx reuse lint`).
- `.gitignore` (repo root) — add `ui/uat-shots/`.
- Verification oracle: `uvx --with charset-normalizer reuse lint` → "compliant" (0 missing),
  and `gsd-sdk phase-plan-index 5` still returns the correct waves (regression guard).
</code_context>

<specifics>
## Specific Ideas

- Keep CICD-06 intact: REUSE.toml must NOT blanket-cover real source dirs — only planning
  artifacts + the already-listed comment-less/binary files.
- The convention statement to document: "GSD planning artifacts (`.planning/**/*.md`,
  `*.json`) are licensed via REUSE.toml, not inline SPDX headers, so `*-PLAN.md` frontmatter
  stays on line 1 for the gsd-sdk `phase-plan-index` parser. Source files keep their inline
  two-line header."
</specifics>

<deferred>
## Deferred Ideas

- Committing the untracked governance docs (CLAUDE.md, CONTRIBUTING.md, LICENSE, NOTICE,
  README.md, SECURITY.md, docs/, design/) — pre-existing untracked repo state, not this
  phase's scope. Flag to the operator separately.
- Converting existing inline-SPDX `.planning` prose docs to REUSE.toml-only — unnecessary churn.
- The actual first CI run / GHCR release (ACC-02/ACC-03) — real-infra acceptance, deferred.
</deferred>
