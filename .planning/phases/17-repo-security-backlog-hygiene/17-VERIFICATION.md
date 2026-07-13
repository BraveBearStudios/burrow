<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: passed
phase: 17
verified: 2026-07-13
---

# Phase 17: Repo Security & Backlog Hygiene - Verification

## Must-Haves

1. **Dependabot version-updates (SEC-01)** - PASSED. `.github/dependabot.yml` v2
   with weekly grouped updates for `uv` (`/api`), `npm` (`/ui`), `github-actions`
   (`/`). Valid YAML. Dependabot opens its first grouped PRs on the first weekly
   tick once on `main`.

2. **automated-security-fixes (SEC-02)** - PASSED. Enabled repo-wide via `gh api`
   PUT (vulnerability-alerts + automated-security-fixes); read-back
   `{"enabled":true,"paused":false}`. Token held repo-admin, so no operator
   follow-up was needed.

3. **CodeQL SAST on the default branch (SEC-03)** - PASSED (structural; first-run
   triage realizes at the first `main` run). `.github/workflows/codeql.yml` runs
   `python` + `javascript-typescript` with `security-and-quality`, push+PR on
   `main` + weekly cron, SHA-pinned to real resolved commits, minimal perms +
   harden-runner. Source SAST now exists alongside the Trivy image CVE scan. The
   first-run findings are triaged/baselined at the first live `main` run (its
   push trigger); ADR-0016 is authored only if that surfaces a baseline deviation.

4. **Precise CT-locked predicate + failing-first test (ROB-01)** - PASSED. The
   over-broad bare `"lock"` substring is removed from `_is_running_or_locked`
   (refined to `"is locked ("` to match Proxmox's `is locked (reason)` message).
   `api/tests/unit/test_proxmox_predicates.py` is RED (3 failed) on the unmodified
   source and GREEN (7 passed) after. The `proxmox-provider-preexisting-robustness`
   and `07r-harden-stop-start-e2e-cleanup` todos are moved to `completed/`.

5. **Real leak assertion + em-dash sweep (ROB-02)** - PASSED. The tautological
   `worker.env` assertion in `test_no_credential_leak` is replaced with an on-disk
   scrub walking every file under `$HOME` for the sentinel credential (the files
   the boot actually writes); the stdout/stderr assertions are unchanged. Em-dashes
   swept from 14 worker-template shell comment lines (log-string literals left
   intact). The `boot-credential-leak-test-tautology` todo is moved to `completed/`.

## Evidence

- `ruff check` + `ruff format --check` clean; `mypy . --strict` → 89 files, no issues.
- `pytest tests/unit tests/boot -q` → **194 passed**.
- Predicate test RED (3 fail) → GREEN (7 pass) across the one-line source fix.
- `reuse lint` → 473/473 compliant.
- Repo setting read-back: automated-security-fixes `{"enabled":true,"paused":false}`.
- Commits: `ci(17)` config, `fix(17)` ROB-01, `test(17)` ROB-02.

**Verdict: PASSED** — all five requirements delivered and verified over the api
unit + boot suites; the CodeQL first-run triage realizes at the first `main` run
(the roadmap's CI-provable-at-merge pattern), not a Phase 17 gap.
