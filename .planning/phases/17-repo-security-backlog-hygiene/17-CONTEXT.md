<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 17: Repo Security & Backlog Hygiene - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto (autonomous run) — config + mechanical fixes; grey areas resolved to standard defaults

<domain>
## Phase Boundary

Complete the repo security posture and clear the carried backlog: Dependabot
version-updates + automated-security-fixes, CodeQL SAST on the default branch for
Python + JS/TS with a triaged first-run baseline, and the four backlog nits
(ROB-01 `_is_running_or_locked` bare-`"lock"` + 07r/WR-02 todo closure; ROB-02
tautological `worker.env` leak assertion + worker-template em-dash sweep).
Touches `.github/` + one `compute/` predicate + one boot test — disjoint from the
credential/release surface.

</domain>

<decisions>
## Implementation Decisions

### Dependabot (SEC-01/02)
- Three ecosystems: `uv` for `/api` (pyproject + uv.lock), `npm` for `/ui`
  (package.json + package-lock.json), `github-actions` for `/`.
- Weekly cadence, grouped updates per ecosystem (one PR per ecosystem, not one
  per dependency) to keep review volume sane.
- automated-security-fixes enabled at the repo level (`PUT
  /repos/{owner}/{repo}/automated-security-fixes`) — requires vulnerability alerts
  on first. Attempt via `gh api`; if the token lacks repo-admin, record as an
  operator follow-up rather than fail the phase.

### CodeQL (SEC-03)
- New `.github/workflows/codeql.yml`: languages `python` + `javascript-typescript`,
  triggers push+PR on `main` plus a weekly schedule, `security-and-quality` query
  suite. SHA-pinned `github/codeql-action/*` with a trailing version comment
  (matches the ci.yml convention). SPDX header.
- First-run findings are triaged at the first live run on `main`: recorded /
  dismissed-with-reason / fixed. ADR-0016 authored ONLY if a baseline deviation
  needs recording (per the roadmap's conditional-ADR note); otherwise skipped.

### ROB-01
- Remove the over-broad bare `"lock" in text` from `_is_running_or_locked`
  (`api/compute/proxmoxProvider.py`); keep the precise `"is locked"` and
  `"can't lock"`. Add a failing-first unit test asserting a benign string
  containing `"lock"` (e.g. `"unlock"`, `"locked out"`) does NOT match, and that
  a real `"CT is locked"` / `"is running"` message still does.
- Move `proxmox-provider-preexisting-robustness.md` and
  `07r-harden-stop-start-e2e-cleanup.md` from `todos/pending/` to `todos/completed/`.

### ROB-02
- Replace the tautological `worker.env` assertion in
  `api/tests/boot/test_burrow_boot.py::test_no_credential_leak` (the harness
  itself writes `worker.env` with fixed content, so the assert can never fail)
  with a real scrub over the files the boot script actually writes under `$HOME`
  (walk HOME, assert the sentinel credential appears in no file).
- Sweep em-dashes in worker-template shell **comment** lines
  (`cc-worker-config/lxc/worker-template/burrow-boot.sh`, `provision-template.sh`)
  — comments only, leave `log "..."` string literals untouched to avoid changing
  runtime output. Move `boot-credential-leak-test-tautology.md` to completed.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` — the SHA-pin + trailing-version-comment convention
  and `harden-runner` step-0 pattern CodeQL should mirror.
- `api/tests/unit/` already exists (test_secret_box.py, test_wait_ttyd.py) — home
  for the ROB-01 predicate unit test.

### Established Patterns
- SHA-pinned third-party actions with `# vX.Y.Z` trailing comments.
- SPDX header on every source file (comment syntax per language).
- Failing-first regression test with every bug fix.

### Integration Points
- `.github/dependabot.yml` (new), `.github/workflows/codeql.yml` (new).
- `api/compute/proxmoxProvider.py::_is_running_or_locked` (lines 511-527).
- `api/tests/boot/test_burrow_boot.py::test_no_credential_leak` (lines 137-158).

</code_context>

<specifics>
## Specific Ideas

Dependabot uv ecosystem is GA; use it for `/api` rather than `pip`. CodeQL uses
the combined `javascript-typescript` language identifier (not separate `javascript`
+ `typescript`).

</specifics>

<deferred>
## Deferred Ideas

ADR-0016 (CodeQL/Dependabot security-posture) — authored only if the first CodeQL
run surfaces a baseline deviation worth recording. Repo-admin gated settings
(automated-security-fixes) fall back to an operator follow-up if the token lacks
admin.

</deferred>
