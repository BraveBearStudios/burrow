<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 12 Deferred Items

Out-of-scope discoveries logged during execution (not fixed; not caused by this phase's changes).

## Plan 12-01

- **Pre-existing mypy errors in `api/tests/unit/test_node_selection.py` (lines 156-158):**
  `"LogRecord" has no attribute "considered" / "threshold"`. These are dynamic
  `extra=`-attached LogRecord attributes that mypy cannot see statically. The errors
  predate Plan 12-01 (the file is untouched by this plan, verified against committed
  history) and are unrelated to the setup-caps work. Out of scope per the executor
  SCOPE BOUNDARY rule. Candidate fix: `# type: ignore[attr-defined]` on those lines or a
  typed accessor, in a dedicated test-hardening change.

## Plan 12-02

- **Order-dependent flake in `tests/boot/test_burrow_boot.py::test_plugin_clone_fails_fast_without_harness_git_terminal_prompt`:**
  Fails in a full-suite run but passes in isolation (`uv run pytest tests/boot/test_burrow_boot.py::...`
  is green). The failure is a test-ordering / shared-state interaction in the boot-harness
  tier, NOT in any setup-wizard file this plan touches (`routers/setup.py`, `main.py`,
  `models/compute.py`, the setup tests). Pre-existing on the baseline before Plan 12-02's
  changes; out of scope per the executor SCOPE BOUNDARY rule. Candidate fix: isolate the
  boot test's git-terminal-prompt env/fixture so it is not contaminated by a prior test.
