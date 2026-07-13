---
phase: 15-pipeline-unblock-green-main
plan: 03
subsystem: infra
tags: [release-please, github-ruleset, branch-protection, operator-runbook, relx-03]
status: paused-human-action-checkpoint

# Dependency graph
requires:
  - phase: 08-release-hardening
    provides: "release-please.yml maintaining refs/heads/release-please--branches--main via the workflow GITHUB_TOKEN (github-actions[bot])"
provides:
  - "A durable operator runbook (15-RELX-03-RULESET-RUNBOOK.md) with the exact gh api fetch -> jq modify -> --method PUT sequence and the Settings -> Rules -> Rulesets UI fallback to exclude refs/heads/release-please--** from the oss ruleset (id 18189353)"
awaiting:
  - "Operator-run GitHub repo-admin action: apply the release-please exclusion to the oss ruleset (RELX-03 live proof is human-gated; the session gh token lacks admin:org/repo-admin)"
affects: [release-please, green-main, phase-16-land-credential-backend-reconcile-release-train]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Repo-admin config change documented as a durable fetch-modify-PUT runbook (not a repo file edit) when the session gh token lacks admin scope; the operator applies it"
    - "PUT-safety projection: strip GET-only server-managed fields and project the ruleset body to name/target/enforcement/bypass_actors/conditions/rules so a PUT cannot reset protections"

key-files:
  created:
    - .planning/phases/15-pipeline-unblock-green-main/15-RELX-03-RULESET-RUNBOOK.md
  modified: []

key-decisions:
  - "Surgical exclusion of refs/heads/release-please--** in conditions.ref_name.exclude, chosen OVER adding github-actions[bot] to bypass_actors, so branch protection stays intact everywhere else and no actor gains a standing bypass (CONTEXT RELX-03)"
  - "The runbook jq transform dedupes the appended glob (unique) and projects the PUT body to name/target/enforcement/bypass_actors/conditions/rules only, so the read-only GET fields (id/node_id/source/source_type/created_at/updated_at/_links/current_user_can_bypass) cannot silently reset the ruleset (T-15-08 mitigation)"
  - "RELX-03 is an operator/admin action, NOT a repo commit: the executor authored the runbook and stops at a blocking human-action checkpoint; the session gh token lacks admin:org/repo-admin so the live apply cannot be automated here"

requirements-completed: []
requirements-pending: [RELX-03]

# Metrics
duration: 10min
completed: pending-operator
---

# Phase 15 Plan 03: oss-Ruleset release-please Exclusion (RELX-03) Summary

**Authored a durable operator runbook giving the exact `gh api` fetch -> `jq` modify -> `--method PUT` sequence (plus the Settings -> Rules -> Rulesets UI fallback and a post-apply confirmation) to surgically exclude `refs/heads/release-please--**` from the `oss` ruleset (id 18189353); the live apply is an operator GitHub-admin action and this plan is paused at a blocking human-action checkpoint (RELX-03 NOT yet complete).**

## Status: PAUSED at a blocking human-action checkpoint

Task 1 (autonomous) is done and committed. Task 2 (the live ruleset exclusion) is an
operator-run GitHub repo-admin change and cannot be automated: the session `gh` token
lacks `admin:org` / repo-admin, and applying a ruleset PUT is an outward-facing mutation
the executor is not authorized to make. RELX-03 stays PENDING until the operator applies
the exclusion and confirms a clean release-please run.

## Performance

- **Duration:** ~10 min (autonomous task only)
- **Tasks:** 2 (Task 1 autonomous done; Task 2 operator-run, pending)
- **Files created:** 1 runbook + this SUMMARY

## Accomplishments

- Authored `.planning/phases/15-pipeline-unblock-green-main/15-RELX-03-RULESET-RUNBOOK.md`
  with the two-line HTML-comment SPDX header (matching 15-CONTEXT.md), no em-dashes.
- Encoded the exact numbered operator commands: fetch the ruleset
  (`gh api repos/BraveBearStudios/burrow/rulesets/18189353 > ruleset.json`), a `jq`
  transform that appends `refs/heads/release-please--**` to `conditions.ref_name.exclude`
  (deduped) and projects the body to `{name, target, enforcement, bypass_actors, conditions, rules}`,
  then apply (`gh api --method PUT repos/BraveBearStudios/burrow/rulesets/18189353 --input ruleset.new.json`).
- Documented the Settings -> Rules -> Rulesets UI fallback, a pre-PUT `diff` sanity-check,
  a post-apply verify (the exclude glob present + rules/enforcement/bypass_actors unchanged),
  and the confirmation step (a release-please run with NO
  `Error updating ref heads/release-please--branches--main`).
- Added an owner/repo substitution note and an emphasis line that ONLY the release-please
  glob is excluded (pull_request + non_fast_forward + required_linear_history stay enforced;
  no bypass actor added).

## Task Commits

1. **Task 1: Author the oss-ruleset exclusion runbook** - `17b5707` (docs)
2. **Task 2: Operator excludes the release-please branch from the oss ruleset** - OPERATOR-RUN, pending (blocking human-action checkpoint; no executor commit)

**Plan metadata:** this SUMMARY + STATE/ROADMAP - final docs commit below.

## Exact Operator Commands Captured (in the runbook)

Fetch, modify, apply (run in a bash shell with an admin-scoped `gh`):

```bash
gh api repos/BraveBearStudios/burrow/rulesets/18189353 > ruleset.json

jq '
  .conditions.ref_name.exclude =
    ((.conditions.ref_name.exclude // []) + ["refs/heads/release-please--**"] | unique)
  | {name, target, enforcement, bypass_actors, conditions, rules}
' ruleset.json > ruleset.new.json

gh api --method PUT repos/BraveBearStudios/burrow/rulesets/18189353 --input ruleset.new.json
```

UI fallback: Settings -> Rules -> Rulesets -> open `oss` -> Target branches -> Add target
-> Exclude by pattern -> `refs/heads/release-please--**` -> Save.

Verify it applied:

```bash
gh api repos/BraveBearStudios/burrow/rulesets/18189353 | jq '.conditions.ref_name.exclude'
```

## Deviations from Plan

Two small operator-correctness additions inside the runbook (Rule 2, no scope change):

**1. [Rule 2 - Correctness] Pre-PUT `diff` sanity-check + post-apply enforcement/bypass verify**
- Added a `diff <(jq -S . ruleset.json) <(jq -S . ruleset.new.json)` step and a
  `jq '{enforcement, rules: [.rules[].type], bypass_actors}'` verify so the operator can
  prove the ONLY change is the added glob (directly serves the T-15-07 / T-15-08 surgical
  guardrails and the Task 2 acceptance criteria that other rules stay intact).

**2. [Rule 2 - Correctness] Windows PowerShell UTF-8 note**
- The operator (and this repo's dev box) is on Windows; native PowerShell `>` writes UTF-16
  which breaks `jq`. Added a short note to run in Git Bash or use
  `Out-File -Encoding utf8`, so the documented commands do not silently fail on the actual
  operator shell.

Otherwise the plan executed exactly as written; the Task 1 automated verify one-liner
returned `OK`.

## Human-gated (Task 2, blocking) - RELX-03 NOT complete

- The live exclusion is an operator GitHub repo-admin action. The session `gh` token lacks
  `admin:org` / repo-admin, so the executor did NOT (and must not) run any
  `gh api ... -X PUT/PATCH` against the ruleset.
- RELX-03 is confirmed live only when: `conditions.ref_name.exclude` contains
  `refs/heads/release-please--**`; the other rules + enforcement + bypass list are
  unchanged; and a release-please run updates `refs/heads/release-please--branches--main`
  with no `Error updating ref`.
- Resume signal: the operator replies `applied` once the exclusion is live and a
  release-please run maintains the branch cleanly (or pastes the error to iterate).

## Next Phase Readiness

- RELX-03 documentation half landed; the live apply gates Phase 15 close-out. Once applied,
  Phase 15 (the pipeline-unblock critical path) closes so Phase 16 can merge PR #3 onto a
  green main. release-please can then maintain its release PR without the ref rejection.

## Self-Check: PASSED

- Created file exists: `15-RELX-03-RULESET-RUNBOOK.md` and `15-03-SUMMARY.md`.
- Task 1 commit exists: `17b5707`.
- Task 1 automated verify returned `OK` (SPDX header, `rulesets/18189353`, `--method PUT`,
  `refs/heads/release-please--**`, `ref_name.exclude`, `Error updating ref`, `Rulesets`, no em-dash).

*Phase: 15-pipeline-unblock-green-main*
*Status: paused at a blocking human-action checkpoint (RELX-03 awaiting operator apply)*
