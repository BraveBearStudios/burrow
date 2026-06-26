<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 11-scrollback-restore
plan: 02
subsystem: infra
tags: [tmux, lxc, golden-template, provision, scrollback, ubuntu-24.04]

# Dependency graph
requires:
  - phase: 00-contracts-seams-golden-template
    provides: provision-template.sh golden-template provisioner (apt baseline, pin-by-comment convention, worker.env drop-file precedent)
  - phase: 11-scrollback-restore (Plan 11-01)
    provides: burrow-boot.sh tmux new-session -A -s burrow wrap that needs a baked tmux binary + /etc/tmux.conf to exec against
provides:
  - tmux 3.4 baked into the golden worker template (Ubuntu 24.04 apt, recorded in the pin comment)
  - a minimal /etc/tmux.conf baked at provision time (history-limit 50000 + window-size latest)
affects: [phase-14-real-infra-acceptance, scrollback-restore, worker-template]

# Tech tracking
tech-stack:
  added: [tmux 3.4 (Ubuntu 24.04 apt)]
  patterns: [pin-by-comment for distro apt packages, provision-time drop-file via quoted heredoc]

key-files:
  created: []
  modified:
    - cc-worker-config/lxc/worker-template/provision-template.sh

key-decisions:
  - "tmux is unpinned in the apt-install line (matching ttyd/jq); the 3.4/Ubuntu-24.04 version is recorded in the top-of-file pin comment, satisfying the pin-by-comment convention without an apt =version lock"
  - "/etc/tmux.conf kept minimal: exactly history-limit 50000 + window-size latest, no mouse/status/theme (YAGNI per CONTEXT Deferred Ideas)"
  - "Written via a single-quoted heredoc (cat > ... <<'TMUXCONF') to prevent any shell expansion of the config body; placed before the apt-cache clean so it survives in the baked image"

patterns-established:
  - "Pin-by-comment for distro apt packages: unpinned in the install line, version recorded in the top-of-file pin block alongside CLAUDE_CODE_VERSION"
  - "Provision-time system-config drop-file: quoted heredoc write + explicit chmod 644, landed before the image-shrink step"

requirements-completed: [WSX-03]

# Metrics
duration: 4min
completed: 2026-06-25
---

# Phase 11 Plan 02: Worker-Template tmux Baseline Summary

**Bakes tmux 3.4 into the Ubuntu 24.04 golden worker template and writes a minimal `/etc/tmux.conf` (history-limit 50000 + window-size latest) at provision time, so every clone has the tmux binary and scrollback config the Plan 11-01 reattach wrap depends on.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-25T21:39:29Z
- **Completed:** 2026-06-25T21:43:22Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `tmux` to the golden-template apt-install baseline (unpinned in the line, alongside ttyd/jq) and recorded `tmux 3.4 (Ubuntu 24.04 apt)` in the top-of-file pin comment.
- Baked a minimal `/etc/tmux.conf` drop-file at provision time containing exactly `set -g history-limit 50000` and `set -g window-size latest`, written before the apt-cache clean so it survives in the baked image.
- Completes WSX-03 criterion 2 (the worker-side software baseline for scrollback restore); the relay stays untouched (criterion 4 trivially upheld, this plan is worker-side only).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add tmux to the apt baseline + record the 3.4 pin** - `6d783fc` (feat)
2. **Task 2: Bake /etc/tmux.conf with history-limit 50000 + window-size latest** - `8693e2f` (feat)

**Plan metadata:** (docs: complete plan — see final commit)

## Files Created/Modified

- `cc-worker-config/lxc/worker-template/provision-template.sh` - tmux added to the apt-install line + `tmux 3.4` recorded in the pin comment (Task 1); a baked `/etc/tmux.conf` drop-file (history-limit 50000 + window-size latest) written before the apt-cache clean (Task 2). SPDX header and `set -euo pipefail` left intact.

## Decisions Made

- **tmux unpinned in the apt line, version recorded by comment.** Matches the existing ttyd/jq convention. The project's "pinned" requirement is satisfied via the documented version (3.4) plus the reproducible Ubuntu 24.04 base, not an apt `=version` lock string (an `=` pin would break the unpinned-in-line convention).
- **`/etc/tmux.conf` is exactly two settings.** `history-limit 50000` is the bounded per-pane scrollback cap (~a few MB/pane, vs the tmux default 2000, and the T-11-03 DoS mitigation); `window-size latest` is the single-reconnecting-web-client resize fix (sizes the pane to the newest attached client, not the smallest historical one). No mouse/status/theme lines (YAGNI, CONTEXT Deferred Ideas).
- **Single-quoted heredoc.** `cat > /etc/tmux.conf <<'TMUXCONF'` prevents any shell expansion of the config body; explicit `chmod 644` gives root-owned 0644 mode parity with the worker.env precedent and the installed systemd unit.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The baked tmux + `/etc/tmux.conf` take effect on the next golden-template rebuild; the real tmux reattach across a real worker stop/start is the Phase 14 (ACC-01) homelab smoke by design.

## Next Phase Readiness

- Phase 11 (Scrollback Restore) is now complete: Plan 11-01 wired the `tmux new-session -A -s burrow` reattach in `burrow-boot.sh`; Plan 11-02 bakes the tmux binary + `/etc/tmux.conf` it execs against. Both halves of WSX-03 are CI-provable / baked.
- No `api/` or `ui/` change; the control-plane relay is byte-unchanged (criterion 4). Ready for Phase 12 (Setup Wizard Backend), which parallelizes off Phase 10 and is independent of this worker-side work.
- Real-infra acceptance of the scrollback reattach remains the Phase 14 ACC-01 dev-homelab smoke (not CI-provable by design).

## Self-Check: PASSED

- FOUND: `.planning/phases/11-scrollback-restore/11-02-SUMMARY.md`
- FOUND: `cc-worker-config/lxc/worker-template/provision-template.sh`
- FOUND commit: `6d783fc` (Task 1 — tmux apt baseline + 3.4 pin)
- FOUND commit: `8693e2f` (Task 2 — baked /etc/tmux.conf)

*Phase: 11-scrollback-restore*
*Completed: 2026-06-25*
