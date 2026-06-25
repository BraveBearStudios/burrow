---
phase: 11-scrollback-restore
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - cc-worker-config/lxc/worker-template/burrow-boot.sh
  - cc-worker-config/lxc/worker-template/provision-template.sh
  - api/tests/boot/test_burrow_boot.py
  - docs/adr/ADR-0014-tmux-scrollback.md
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 11 (WSX-03) wraps the worker shell in `tmux new-session -A -s burrow` so
terminal scrollback survives a ttyd/web-client reconnect to a still-running
worker, bakes `tmux` plus a minimal `/etc/tmux.conf` into the golden template,
and records the decision in ADR-0014.

The core implementation is correct and tightly scoped. Every load-bearing concern
flagged for scrutiny checks out:

- **tmux wrap quoting is sound.** The inner `bash -lc "cd '${START_DIR}' && exec
  tmux new-session -A -s burrow ${CLAUDE_CMD}"` keeps `${START_DIR}`
  single-quoted (space-safe via `cd`) and leaves `${CLAUDE_CMD}` unquoted on
  purpose so `rtk claude` word-splits into two tmux args. The first-boot Claude
  launch runs as the session's first process; a later reconnect reattaches via
  `-A` and the trailing command is ignored on attach (correct, intended). The
  ttyd flag tail is FROZEN: `--port 7681 --writable --interface 0.0.0.0`, no
  `--once` (verified against the diff and the `test_frozen_ttyd_line` /
  `test_two_boots_stable_tmux_session` assertions).
- **ADR-0014 is accurate, not over-claimed.** It explicitly states tmux alone
  does NOT preserve scrollback across a real `pct stop` (the CT halt kills the
  tmux server), records the honest contract as reattach-on-RECONNECT, and defers
  cross-reboot persistence to v1.4 (WSX-06). Zero em-dashes (U+2014), zero
  en-dashes, zero horizontal rules. The test docstring
  (`test_two_boots_stable_tmux_session`) carries the same disclaimer.
- **provision-template.sh** adds `tmux` to the apt line and bakes
  `/etc/tmux.conf` with exactly `set -g history-limit 50000` + `set -g
  window-size latest` via a single-quoted heredoc (`<<'TMUXCONF'`, so `$` cannot
  expand). `/etc/tmux.conf` is the correct system config path for the Ubuntu
  24.04 tmux 3.4 package and is read at first `new-session` before the first
  pane is created, so the 50000-line limit applies to the `burrow` session. SPDX
  header and `set -euo pipefail` intact.
- **Relay stays opaque.** `api/routers/terminal.py` is not touched by any Phase
  11 commit; none of the four reviewed files add server-side scrollback
  buffering (ADR-0014 §Decision bullet 4, confirmed in code).

One real defect surfaced: the boot harness advertises a `worker.env` write
contract that `burrow-boot.sh` does not actually implement (WR-01). Two
lower-severity items follow.

## Warnings

### WR-01: No-leak test asserts a `worker.env` write contract the boot script never exercises

**File:** `api/tests/boot/test_burrow_boot.py:157-158`, `cc-worker-config/lxc/worker-template/burrow-boot.sh:79`
**Issue:**
`test_no_credential_leak` reads `etc_burrow/worker.env` and asserts the sentinel
credential never lands in it ("credential persisted to worker.env (SC-3)"). But
`burrow-boot.sh` never writes to `worker.env` at all: `BURROW_ETC` is assigned on
line 79 and then referenced only in comments (lines 76, 265), never in any
executable statement. The script reads `worker.env` only via the harness-seeded
env file, and the credential lives solely in the subshell-local `GIT_CRED`. So
the assertion can never fail regardless of how the script behaves: it is a
tautology, not a regression guard. If a future edit DID start writing config to
`BURROW_ETC/worker.env` and leaked the token there, this test gives false
assurance only if the write path matches; today it proves nothing because the
script has no `worker.env` write path. The structural no-leak guarantee
(subshell-local `GIT_CRED`, `unset` after clones) is real and well-tested
elsewhere in this file, so this is a test-quality gap, not a live security hole.
This is a pre-existing condition (the `BURROW_ETC` seam predates Phase 11), but it
is in a file under review.
**Fix:** Either (a) remove the dead `BURROW_ETC` assignment and the
`worker.env`-write assertion if no `worker.env` write is intended, or (b) if the
seam is meant to guard a future write path, add a positive test that the script
writes the expected non-secret config to `${BURROW_ETC}/worker.env` so the
no-leak assertion has a real write to scrub. Minimal option (a):
```bash
# burrow-boot.sh: drop line 79 if nothing reads BURROW_ETC
# (remove: BURROW_ETC="${BURROW_ETC:-/etc/burrow}")
```
and drop the `worker.env` read+assert in `test_no_credential_leak`, keeping the
stdout/stderr scrub assertions which are the load-bearing ones.

## Info

### IN-01: In-comment em-dashes in the worker shell scripts violate the project no-em-dash convention

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh` (14 occurrences, e.g. lines 5, 14, 23, 116, 325); `cc-worker-config/lxc/worker-template/provision-template.sh` (3 occurrences, lines 5, 57, 71)
**Issue:**
Both shell scripts contain U+2014 em-dashes in comment prose. The project
convention bans em-dashes in output. ADR-0014 (the gated artifact for this phase)
is correctly clean (0 em-dashes, 0 horizontal rules), and these em-dashes are in
comments only (no functional impact), and predate Phase 11. Flagged for
consistency, not correctness.
**Fix:** Replace em-dashes with colons, commas, or restructure. Example
(burrow-boot.sh:116):
```bash
log "bootconfig fetch exhausted ${max} attempts: failing boot"
```
Defer if the maintainer treats pre-existing comment punctuation as out of scope.

### IN-02: `window-size latest` rationale comment is correct but the option is session-scoped — worth a one-word clarity note

**File:** `cc-worker-config/lxc/worker-template/provision-template.sh:80-81`, `docs/adr/ADR-0014-tmux-scrollback.md:62-65`
**Issue:**
`set -g window-size latest` is valid and correctly chosen (it sizes the window to
the most-recently-attached client, the right behavior for a single reconnecting
web client; tmux 2.9+, fine on 3.4). The comment says it "sizes the pane to the
newest attached client" — `window-size` governs the window/pane geometry, so the
description is accurate. No defect; noted only because the comment uses "pane"
where tmux names the knob `window-size`. No change required.
**Fix:** Optional wording tweak: "sizes the window to the newest attached
client." No functional change.

---

_Reviewed: 2026-06-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
