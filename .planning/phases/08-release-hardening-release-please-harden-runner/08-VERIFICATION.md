<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 08-release-hardening-release-please-harden-runner
verified: 2026-06-15T22:30:00Z
status: passed
score: 5/5 must-have truths verified
overrides_applied: 0
deferred:
  - truth: "The first real release-please PR is created from Conventional Commits on main (semantic bump + generated changelog)"
    addressed_in: "Deferred ACC-02 (on-runner acceptance)"
    evidence: "ROADMAP success criterion 2: 'the first real release PR is the deferred on-runner acceptance'; CONTEXT.md locks this as ACC-02 (cannot run on the dev box / PR-CI)."
  - truth: "egress-policy flipped from audit to block with the discovered allowlist"
    addressed_in: "Deferred ACC-02 (on-runner acceptance)"
    evidence: "ROADMAP success criterion 5: 'the first real enforcement is the deferred on-runner run'; CONTEXT.md decision: audit-then-block, discover endpoints on first live runner then flip."
  - truth: "GITHUB_TOKEN-pushed v* tag re-triggers release.yml publish job (confirmed live)"
    addressed_in: "Deferred ACC-02 (on-runner acceptance)"
    evidence: "release-please.yml inline note + CONTRIBUTING.md 'First-release caveat' (Open Q1 / ACC-02): GitHub suppresses GITHUB_TOKEN-raised events; first releaser must confirm or use a scoped App token."
---

# Phase 8: Release Hardening (release-please + harden-runner) Verification Report

**Phase Goal:** A merge to main maintains an automated release PR (semantic version bump + generated changelog) that tags `v*` on merge, and the CI workflows run under a locked-down, egress-restricted runner with every third-party action pinned to a commit SHA — so cutting a release is one click and the runner surface is hardened.
**Verified:** 2026-06-15T22:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

This phase is CI-config + docs only and is dev-box statically verifiable. Every must-have was checked against the actual files on disk, not against SUMMARY claims. The three live-runner behaviors (live release-please PR, egress block flip, GITHUB_TOKEN-tag retrigger) are correctly fenced as deferred ACC-02 on-runner acceptance by ROADMAP success criteria 2 and 5, and are recorded under Deferred Items, not as gaps.

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | release-please.yml triggers on push:main with least-privilege per-job perms (contents:write + pull-requests:write) and uses only GITHUB_TOKEN | VERIFIED | `release-please.yml` lines 27-28 (`push: branches:[main]`), 40-41 (`contents: write` + `pull-requests: write`), 51 (`token: ${{ secrets.GITHUB_TOKEN }}`); workflow default `contents: read` (line 31). No PAT / non-GITHUB_TOKEN secret present. |
| 2 | config declares release-type simple, single root package '.', bootstrap-sha = v1.1 COMMIT (not tag object) | VERIFIED | `release-please-config.json`: `release-type: simple` (l.3), `packages: { ".": {} }` (l.6-8), `bootstrap-sha: 9bccec85…` (l.5). `git rev-parse "v1.1^{commit}"` = `9bccec85…` MATCH; tag object `f900a95…` correctly NOT used. |
| 3 | manifest seeds root version 1.1.0 (first PR proposes v1.2.0; v1.2 not yet tagged) | VERIFIED | `.release-please-manifest.json` = `{ ".": "1.1.0" }`; valid JSON; `git tag` confirms only v1.0/v1.1 tagged, v1.2 in progress. |
| 4 | both comment-less JSON configs licensed via REUSE.toml and reuse lint green | VERIFIED | `REUSE.toml` l.29-30 lists `release-please-config.json` + `.release-please-manifest.json`. `uvx --with charset-normalizer reuse lint` = compliant, 331/331 files, 0 missing licenses. |
| 5 | harden-runner is literal step 0 (egress-policy audit) of every job, every `uses:` is a 40-hex SHA (no floating @vN), PR-title gate repinned to amannn v5.5.3 SHA | VERIFIED | YAML-parsed all 3 workflows: 5/5 jobs have `step-security/harden-runner@9af89fc7…` as steps[0] with `egress-policy: audit`. All 25 `uses:` lines are `@<40-hex>`; floating-tag grep returns empty; non-SHA grep returns empty. PR-title gate `amannn/action-semantic-pull-request@0723387… # v5.5.3` (ci.yml l.126). |

**Score:** 5/5 truths verified

### Deferred Items

Items not yet met but explicitly fenced as deferred ACC-02 on-runner acceptance by ROADMAP success criteria 2 and 5. These require a real GitHub Actions runner and are out of scope for dev-box / PR-CI verification by design.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | First real release-please PR (live bump + changelog) | Deferred ACC-02 | ROADMAP SC2: "the first real release PR is the deferred on-runner acceptance" |
| 2 | egress-policy audit → block flip + discovered allowlist | Deferred ACC-02 | ROADMAP SC5: "the first real enforcement is the deferred on-runner run"; CONTEXT.md audit-then-block decision |
| 3 | GITHUB_TOKEN-tag re-triggers release.yml (live confirm) | Deferred ACC-02 | release-please.yml inline note l.20-22 + CONTRIBUTING.md "First-release caveat" (Open Q1 / ACC-02) |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `release-please-config.json` | release-type simple, package '.', bootstrap-sha = v1.1 commit | VERIFIED | Valid JSON; all fields present and correct (l.3, l.5, l.6-8); `include-v-in-tag: true` so merge tags `v*`. |
| `.release-please-manifest.json` | seeded root version 1.1.0 | VERIFIED | Valid JSON; `{ ".": "1.1.0" }`. |
| `.github/workflows/release-please.yml` | push:main workflow, harden-runner audit step 0, min 25 lines | VERIFIED | 54 lines; SPDX header l.1-2; harden-runner step 0; release-please action pinned; config-file + manifest-file wired. |
| `REUSE.toml` | licenses the two new comment-less JSON files | VERIFIED | Both files in the comment-less-JSON annotation block (l.29-30); reuse lint green. |
| `.github/workflows/ci.yml` | harden-runner step 0 on all 3 jobs + amannn repin + actions:read | VERIFIED | 3 jobs hardened; amannn pinned to v5.5.3 SHA (l.126); build-scan has `actions: read` (l.144, WR-02 fix). |
| `.github/workflows/release.yml` | harden-runner step 0 on publish (trigger + perms untouched) | VERIFIED | publish job step 0 = harden-runner (l.58-61); `tags: ["v*"]` trigger unchanged (l.26); 4-scope perms unchanged. |
| `CONTRIBUTING.md` | release chain + audit-then-block + version.txt note documented | VERIFIED | "## Release process" section l.100-140: release chain, version.txt note, PR-title linkage, audit-then-block, GITHUB_TOKEN caveat. No em dashes / horizontal rules in this section. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| release-please.yml | release-please-config.json | config-file input | WIRED | `config-file: release-please-config.json` (l.52) + `manifest-file: .release-please-manifest.json` (l.53). |
| release-please-config.json | v1.1 commit 9bccec85 | bootstrap-sha field | WIRED | `bootstrap-sha: 9bccec85…` == `git rev-parse "v1.1^{commit}"`. |
| ci.yml | step-security/harden-runner | step 0 of each job | WIRED | `@9af89fc7…` (40-hex SHA) as steps[0] on all 3 jobs. |
| ci.yml | amannn/action-semantic-pull-request | repinned PR-title gate | WIRED | `@0723387faaf9b38adef4775cd42cfd5155ed6017 # v5.5.3` (l.126). |
| release-please.yml (tag) | release.yml publish job | v* tag chain | WIRED (static) | release.yml `tags: ["v*"]` trigger present and unchanged; live retrigger confirmation is deferred ACC-02. |

### Data-Flow Trace (Level 4)

N/A — this is CI-config + docs only; no runtime artifact renders dynamic application data. The data-flow analog (config values flowing into the release pipeline) is covered by the Key Link table and is exercised only on a live runner (deferred ACC-02).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Both JSON configs parse | `python -c json.load(...)` | release-please-config.json VALID; manifest VALID (root=1.1.0) | PASS |
| All 3 workflows parse as YAML | PyYAML safe_load + step0 walk | 5/5 jobs hardened step0/audit | PASS |
| bootstrap-sha == v1.1 commit | `git rev-parse "v1.1^{commit}"` | 9bccec85… MATCH; tag obj f900a95… not used | PASS |
| No floating @vN action tags | grep `uses:.*@v[0-9]` | empty (exit 1) | PASS |
| All `uses:` are 40-hex SHA | grep `uses:` minus `@[0-9a-f]{40}` | empty (exit 1) | PASS |
| REUSE compliance | `uvx --with charset-normalizer reuse lint` | compliant, 331/331 | PASS |
| No debt markers in phase files | grep TODO/FIXME/XXX/TBD/HACK/PLACEHOLDER | empty (exit 1) | PASS |

### Probe Execution

No project probe scripts declared for this phase (CI-config + docs phase; no `scripts/*/tests/probe-*.sh`). Static validation (JSON/YAML parse + reuse lint + SHA-pin grep) serves as the dev-box verification surface per ROADMAP success criterion 2. Live runner probes are deferred ACC-02.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| RELX-01 | 08-01, 08-02 | Release automation via release-please (release PR, semantic bump + changelog, tags v* on merge); config buildable + lintable locally | SATISFIED | release-please.yml + config + manifest authored and valid; `include-v-in-tag: true`; documented in CONTRIBUTING.md. First live PR = deferred ACC-02 per SC2. |
| RELX-02 | 08-01, 08-02 | CI under harden-runner with egress allowlist (audit-then-block), all actions SHA-pinned, policy documented | SATISFIED | harden-runner audit step 0 on all 5 jobs; all `uses:` 40-hex SHA-pinned (PR-title gate repinned to v5.5.3); audit-then-block documented in CONTRIBUTING.md. Block flip = deferred ACC-02 per SC5. |

No orphaned requirements. REQUIREMENTS.md line 95 maps Phase 8 to exactly RELX-01 + RELX-02, matching both plans' declared IDs. Both marked Complete (l.88-89).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none) | — | — | — | No debt markers, stubs, em dashes (in phase-8 sections), or horizontal rules found in any phase-8-touched file. The prior `# TODO pin exact SHA` placeholder on the PR-title gate was resolved (now pinned to `0723387…`). |

Note: em dashes exist in pre-existing CONTRIBUTING.md sections (l.23, 30, 83, 94 — CLA/licensing/SPDX/commit-types), but NONE in the phase-8-authored "Release process" section (l.100-140). Out of scope for this phase.

### Human Verification Required

None for dev-box acceptance. All success-criteria items that are statically verifiable are VERIFIED. The three live-runner behaviors are recorded as Deferred Items (ACC-02), not human-verification items — they are out of scope for this phase by ROADMAP design (SC2 + SC5 explicitly fence them) and will be exercised on the first real GitHub Actions runner.

### Gaps Summary

No gaps. Every must-have truth (5/5), every required artifact (7/7), every key link, and both requirement IDs (RELX-01, RELX-02) are verified against the actual codebase. JSON/YAML parse clean, `reuse lint` is green (331/331), all 25 `uses:` lines are 40-hex SHA-pinned with zero floating tags, harden-runner is step 0 (egress audit) on all 5 jobs, the bootstrap-sha is the v1.1 commit (not the tag object), the manifest seeds 1.1.0, and the release process + audit-then-block policy + version.txt note are documented in CONTRIBUTING.md. The only outstanding items (live release-please PR, egress block flip, GITHUB_TOKEN-tag retrigger) require a real runner and are correctly deferred to ACC-02 on-runner acceptance by ROADMAP success criteria 2 and 5 — they are not gaps.

---

_Verified: 2026-06-15T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
