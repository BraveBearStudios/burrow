<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 10 — Deferred / Out-of-Scope Items

Discovered during execution but NOT caused by the current task's changes. Logged
per the executor scope boundary; left untouched.

## Pre-existing mypy errors (out of scope for Plan 10-01)

- **File:** `api/tests/unit/test_node_selection.py:156-158`
- **Errors:** `"LogRecord" has no attribute "considered"` / `"threshold"` (3 errors)
- **Origin:** Phase 9 commit `759a5d6` (`fix(09): IN-03 log considered nodes + fractions`)
- **Why deferred:** Not introduced by Plan 10-01 (mocked-proxmoxer tier). The new
  files `mock_proxmox.py` + `test_mock_proxmox.py` are both ruff- and mypy-clean.
  `uv run ruff check .` is fully green; the only mypy hits are this pre-existing file.
- **Disposition:** Surface to a later Phase-10 plan or a dedicated cleanup; do not
  expand Plan 10-01 scope to fix unrelated test typing.
