<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 11-scrollback-restore
plan: 01
subsystem: infra
tags: [tmux, ttyd, worker-template, scrollback, boot-harness, adr]

# Dependency graph
requires:
  - phase: 00-foundation
    provides: burrow-boot.sh frozen ttyd exec line + the hermetic boot harness (stub ttyd records argv)
  - phase: 10-persistence-data-model
    provides: ADR-0013 Tier-1 persistence (files-on-disk, not live-session) - the seam this fills
provides:
  - Worker shell wrapped in tmux new-session -A -s burrow (reattach-on-reconnect)
  - Boot harness argv assertion (tmux new-session, -A, -s burrow) + two-boot reattach idempotency test
  - ADR-0014 recording the honest reattach-on-reconnect contract, cross-reboot deferred to v1.4
affects: [11-02-provision-tmux, 14-real-infra-acceptance]

# Tech tracking
tech-stack:
  added: [tmux 3.4 (Ubuntu 24.04 distro, wired in burrow-boot.sh; baked by Plan 11-02)]
  patterns:
    - "Worker shell runs inside one fixed tmux session (burrow); -A makes reconnect idempotent"
    - "Hermetic boot harness asserts the tmux invocation in recorded ttyd argv, no live tmux server"

key-files:
  created:
    - docs/adr/ADR-0014-tmux-scrollback.md
  modified:
    - cc-worker-config/lxc/worker-template/burrow-boot.sh
    - api/tests/boot/test_burrow_boot.py

key-decisions:
  - "Wrap exec ${CLAUDE_CMD} in exec tmux new-session -A -s burrow ${CLAUDE_CMD}; ttyd flags frozen"
  - "One fixed session named burrow per worker; -A reattaches on reconnect, never respawns on attach"
  - "Honest contract: reattach-on-reconnect now; cross-reboot scrollback (pipe-pane/CRIU) deferred to v1.4 (WSX-06)"
  - "Relay (api/routers/terminal.py) stays opaque, zero lines added (criterion 4)"

patterns-established:
  - "tmux argv proven hermetically via stub-ttyd-records-argv + argv.replace newline normalization"
  - "ADR section order matches ADR-0013 (Status/Context/Decision/Consequences/Revisit trigger); no em dashes, no horizontal rules"

requirements-completed: [WSX-03]

# Metrics
duration: 9min
completed: 2026-06-25
---

# Phase 11 Plan 01: tmux scrollback reattach (WSX-03) Summary

**Worker shell wrapped in `tmux new-session -A -s burrow` so a ttyd/web-client reconnect to a still-running worker reattaches to the live session and its scrollback, proven hermetically by the boot harness, with ADR-0014 recording the honest reattach-on-reconnect contract.**

## Performance

- **Duration:** ~9 min (excluding the 3m16s boot suite run)
- **Started:** 2026-06-25T21:16:54Z (orchestrator), execution after context load
- **Completed:** 2026-06-25
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `burrow-boot.sh` inner ttyd shell now execs `tmux new-session -A -s burrow ${CLAUDE_CMD}`; `-A` reattaches to the live `burrow` session on reconnect instead of starting fresh. All ttyd flags frozen (`--port 7681 --writable --interface 0.0.0.0`, no `--once`); `bash -n` clean.
- Boot harness gains criterion-1 argv assertion (`tmux new-session`, `-A`, `-s burrow` in the normalized recorded ttyd argv) plus a new `test_two_boots_stable_tmux_session` proving the `-A` reattach idempotency across two boots over the same manifest. `cd api && uv run pytest tests/boot -q` is green (22 passed).
- ADR-0014 authored in the ADR-0013 format (SPDX header, Status/Context/Decision/Consequences/Revisit trigger), naming the tmux wrap, `history-limit 50000`, `window-size latest`, and the opaque-relay discipline; states reattach-on-reconnect only and defers cross-reboot scrollback to v1.4 (WSX-06). Zero em dashes, zero horizontal rules.
- `api/routers/terminal.py` is byte-unchanged across all plan commits (criterion 4, relay stays opaque).

## Task Commits

Each task was committed atomically:

1. **Task 1: Wrap the ttyd-exec'd shell in tmux new-session -A -s burrow** - `fc0cec7` (feat)
2. **Task 2: Assert the tmux wrap in recorded argv + prove -A reattach across two boots** - `d7c0ed4` (test)
3. **Task 3: Author ADR-0014 (tmux scrollback - reattach-on-reconnect; cross-reboot deferred)** - `3d23228` (docs)

**Plan metadata:** committed separately (docs: complete plan)

## Files Created/Modified

- `cc-worker-config/lxc/worker-template/burrow-boot.sh` - inner ttyd `bash -lc` shell wraps `${CLAUDE_CMD}` in `tmux new-session -A -s burrow`; log line and comment updated to note the session wrap; ttyd flags untouched.
- `api/tests/boot/test_burrow_boot.py` - happy-path test asserts the normalized argv contains `tmux new-session`, `-A`, `-s burrow` (criterion 1); new `test_two_boots_stable_tmux_session` proves both boots carry `tmux new-session -A -s burrow` (criterion 3).
- `docs/adr/ADR-0014-tmux-scrollback.md` - new ADR for worker-side tmux scrollback; reattach-on-reconnect contract, cross-reboot deferred.

## Decisions Made

- Kept the `cd '${START_DIR}' &&` prefix and the `bash -lc "..."` double-quote boundary exactly as-is so `${START_DIR}`/`${CLAUDE_CMD}` keep expanding and word-splitting; only the inner `exec` target changed (no nested quotes around `${CLAUDE_CMD}`, avoiding the RESEARCH quoting pitfall).
- Used the established `argv.replace("\n", " ")` normalization for both the happy-path and the two-boot assertions; asserted on the contiguous invocation string, not raw per-line argv elements (the stub records each argv element on its own line via `printf '%s\n'`).
- Ordered ADR-0014 sections Status -> Context -> Decision -> Consequences -> Revisit trigger to match ADR-0013 exactly (initial draft had Decision before Context; corrected before commit).

## Deviations from Plan

None - plan executed exactly as written. No bugs, missing functionality, or blocking issues were encountered; no package installs; no architectural changes. All three task verifications passed on first run.

## Issues Encountered

None. The boot suite is slow (~3m16s for 22 tests) but passed clean. The pre-existing working-tree changes to `.planning/` (config.json, STATE.md, a deleted v1.2 audit, untracked HANDOFF/ui-reviews) were present at session start from the orchestrator and were left untouched by this plan.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced. The tmux wrap, the argv assertions, and the ADR are all live and complete; the actual tmux binary + `/etc/tmux.conf` are baked by Plan 11-02 (provision-template), which this plan's ADR and boot wrap reference by design (not a stub - a documented split across the two-plan phase).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 11-02 (provision-template) is the natural next step: `apt install tmux` + bake `/etc/tmux.conf` (`history-limit 50000`, `window-size latest`) into the golden template so the wrap this plan added has tmux present and configured on every clone.
- The real tmux reattach across a real worker stop/start stays the Phase 14 dev-homelab acceptance smoke (ACC-01), not a CI command, by design.
- No blockers.

*Phase: 11-scrollback-restore*
*Completed: 2026-06-25*

## Self-Check: PASSED

All created/modified files exist on disk and all three task commits are present in git:

- FOUND: cc-worker-config/lxc/worker-template/burrow-boot.sh
- FOUND: api/tests/boot/test_burrow_boot.py
- FOUND: docs/adr/ADR-0014-tmux-scrollback.md
- FOUND: .planning/phases/11-scrollback-restore/11-01-SUMMARY.md
- FOUND commit: fc0cec7 (Task 1, feat)
- FOUND commit: d7c0ed4 (Task 2, test)
- FOUND commit: 3d23228 (Task 3, docs)
