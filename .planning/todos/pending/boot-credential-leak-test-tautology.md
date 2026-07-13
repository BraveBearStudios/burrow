<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-25
title: test_no_credential_leak asserts against a file burrow-boot.sh never writes (tautology)
area: api/tests/boot
source: 11-REVIEW.md WR-01 (surfaced during Phase 11, pre-existing)
severity: warning
resolves_phase: 17
resolves_phase: none
files:
  - api/tests/boot/test_burrow_boot.py
  - cc-worker-config/lxc/worker-template/burrow-boot.sh
---

## Problem

`test_no_credential_leak` (api/tests/boot/test_burrow_boot.py:157-158) asserts the git
credential never lands in `worker.env`, but `burrow-boot.sh` never writes `worker.env`
(`BURROW_ETC` is assigned ~line 79 and only referenced in comments). The assertion is a
tautology, not a regression guard — it passes vacuously. CLAUDE.md: "a test that always
passes is worse than no test."

The actual no-leak guarantee (subshell-local `GIT_CRED`, `unset` after clones) IS real and
IS covered by the stdout/stderr scrub assertions in the same test — so there is no live
exposure; only the worker.env assertion is dead.

Pre-existing: the credential seam predates Phase 11. Surfaced only because Phase 11 added
tests to the same file (the file came into code-review scope). NOT introduced by WSX-03, so
it was deliberately not swept into the Phase 11 fix pass (scope discipline).

Separately (INFO, same review): a few pre-existing in-comment em-dashes remain in the
worker-template shell scripts (the ADR is clean). The project forbids em-dashes; worth a
sweep when these files are next touched.

## Solution

- Replace the dead `worker.env` assertion with a real one: assert the credential is absent
  from every file the boot script actually writes (or drop it and rely on the stdout/stderr
  scrub assertions, with a comment explaining why).
- Optionally: strip the pre-existing em-dashes from the worker-template shell-script comments.

## Notes

Flaky-timeout aside: under concurrent agent load this test (it spawns a subprocess with a
timeout) intermittently times out; it passes reliably in isolation (~9s). Not a logic
failure. Consider a more generous subprocess timeout if CI parallelism grows.
