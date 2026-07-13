<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 17: Repo Security & Backlog Hygiene - Summary

**Completed:** 2026-07-13
**Requirements:** SEC-01, SEC-02, SEC-03, ROB-01, ROB-02

## What shipped

- **SEC-01 Dependabot** — `.github/dependabot.yml` (v2): weekly grouped
  version-updates for `uv` (`/api`), `npm` (`/ui`), `github-actions` (`/`), one
  grouped PR per ecosystem.
- **SEC-02 automated-security-fixes** — enabled at the repo level via `gh api`:
  `PUT /repos/BraveBearStudios/burrow/vulnerability-alerts` then
  `.../automated-security-fixes`. Read-back confirmed `{"enabled":true,"paused":false}`.
- **SEC-03 CodeQL SAST** — `.github/workflows/codeql.yml`: matrix
  `python` + `javascript-typescript`, push+PR on `main` + weekly cron,
  `security-and-quality` suite, harden-runner step 0, minimal `security-events:
  write` perms. All actions SHA-pinned to real commits resolved via `gh api`
  (`github/codeql-action@02c5e83…` v3, `actions/checkout@34e11487…` v4.3.1,
  `harden-runner@9af89fc…` v2.19.4). First-run findings are triaged at the first
  live run on `main` (the workflow's push:main trigger).
- **ROB-01** — dropped the over-broad bare `"lock"` substring from
  `_is_running_or_locked`; refined `"is locked"` → `"is locked ("` to match the
  canonical Proxmox guest-lock message (`CT … is locked (reason)`) so benign
  strings like `"user is locked out"` no longer match. Failing-first unit test
  `api/tests/unit/test_proxmox_predicates.py` (RED 3-fail on unmodified source →
  GREEN 7-pass after). Closed `proxmox-provider-preexisting-robustness.md` +
  `07r-harden-stop-start-e2e-cleanup.md` todos.
- **ROB-02** — replaced the tautological `worker.env` assertion in
  `test_no_credential_leak` (the harness itself wrote that file; the boot never
  touched it) with a real on-disk scrub that walks every file under `$HOME` and
  asserts the sentinel credential is absent — the meaningful "credential never
  persists" guard. Swept em-dashes from 14 worker-template shell **comment** lines
  (`burrow-boot.sh` ×13, `provision-template.sh` ×1); `log "…"` string literals
  left intact. Closed `boot-credential-leak-test-tautology.md` todo.

## Deviation

ROB-01 refined the lock clause to `"is locked ("` rather than leaving a bare
`"is locked"`, because the required benign case `"user is locked out"` contains
the substring `is locked`. The parenthetical form matches every real Proxmox
guest-lock message (the lock reason is always emitted) while excluding the benign
phrasing — a net-more-precise predicate, consistent with the phase's stated goal.

## Verification evidence

- `uv run ruff check .` + `ruff format --check` clean; `uv run mypy . --strict`
  → no issues in 89 files.
- `uv run pytest tests/unit tests/boot -q` → **194 passed**.
- Predicate test RED (3 failed) on unmodified source → GREEN (7 passed) after.
- `reuse lint` → compliant 473/473 (SPDX on the two new workflow/config files +
  the new test).
- Both new YAML files parse (`yaml.safe_load`).
- Zero em-dashes remain on comment lines of the two worker-template shell files.
