<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-25
title: ProxmoxProvider pre-existing robustness nits (getNodeMemory KeyError, lock substring)
area: api/compute
source: 12-REVIEW.md WR-02 + WR-04 (surfaced during Phase 12, pre-existing)
severity: warning
resolves_phase: none
files:
  - api/compute/proxmoxProvider.py
---

## Problem

Two pre-existing robustness nits in `api/compute/proxmoxProvider.py`, surfaced because the file
came into Phase 12 code-review scope but NOT introduced by SETUP work (so deliberately not swept
into the Phase 12 fix pass — scope discipline):

- **WR-02 (getNodeMemory, ~:348-351):** uses `status["mem"]` / `status["maxmem"]` directly, so a
  partial Proxmox status body raises a raw `KeyError` that escapes the typed compute seam as an
  opaque 500. It is the lone read method not using `.get(...)`. Fix: `.get("mem")` / `.get("maxmem")`
  with a typed `ComputeError` (or sensible default) when absent, matching the other read methods.

- **WR-04 (_is_running_or_locked, ~:471-478):** matches the bare substring `"lock"`, which also
  matches `"unlock"`, `"deadlock"`, `"blocked"` — redundant with the precise `"is locked"` clause.
  Fix: drop the bare `"lock"` match; keep `"is locked"`.

Neither is a SETUP-07 / Phase 12 concern; both predate this milestone's wizard work.

## Solution

- getNodeMemory: switch to `.get(...)` + typed error on missing keys.
- _is_running_or_locked: remove the bare `"lock"` substring match.
- Add a small regression test for each when next touching this file.
