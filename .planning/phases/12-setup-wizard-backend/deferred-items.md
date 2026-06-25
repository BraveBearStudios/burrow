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
