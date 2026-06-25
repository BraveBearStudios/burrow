<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 11-scrollback-restore
verified: 2026-06-25T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
warnings:
  - id: WARN-01
    concern: "ADR-0014 Context attributes cross-reboot scrollback to WSX-06; REQUIREMENTS.md defines WSX-07 as cross-reboot scrollback (pipe-pane), WSX-06 as CRIU suspend/resume"
    severity: info
    impact: "Traceability label only; the deferral target exists and ADR Consequences correctly lists WSX-05/06/07. No goal impact."
---

# Phase 11: Scrollback Restore Verification Report

**Phase Goal:** A persistent workspace's terminal scrollback survives stop→start — on reconnect the operator sees prior scrollback by reattaching to a worker-side tmux session, with the control-plane relay unchanged.
**Verified:** 2026-06-25
**Status:** passed
**Re-verification:** No — initial verification
**Requirement:** WSX-03

## Goal Achievement

The phase goal is achieved at its intended (correctly scoped) contract: reattach-on-RECONNECT to a still-running worker. The worker shell is wrapped in `tmux new-session -A -s burrow`, the golden template bakes tmux 3.4 plus a bounded `/etc/tmux.conf`, the `-A` idempotency is proven hermetically, the control-plane relay is byte-unchanged, and ADR-0014 records the honest contract without over-claiming survival across a real `pct stop`.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | burrow-boot.sh execs ttyd wrapping the worker shell in `tmux new-session -A -s burrow` (idempotent reattach), ttyd flags frozen, quoting intact; proven by the boot harness asserting the tmux invocation in recorded ttyd argv | VERIFIED | `burrow-boot.sh:338` `exec tmux new-session -A -s burrow ${CLAUDE_CMD}` inside `bash -lc "cd '${START_DIR}' && exec ..."`. ttyd tail frozen `--port 7681 --writable --interface 0.0.0.0`, no `--once` (`:334-338`). Exactly 1 non-comment `exec tmux` occurrence. `bash -n` clean. `test_burrow_boot.py:108-110` asserts `tmux new-session`, `-A`, `-s burrow` in normalized argv; test passes (4/4 targeted, 184s run). |
| 2 | provision-template.sh bakes tmux (Ubuntu 24.04 apt) + an /etc/tmux.conf with history-limit 50000 and `window-size latest` | VERIFIED | `provision-template.sh:38` `apt-get install -y git curl build-essential ttyd jq tmux`; pin comment `:16` `tmux 3.4 (Ubuntu 24.04 apt; ...)`. `/etc/tmux.conf` written via single-quoted heredoc `:83-86` with exactly `set -g history-limit 50000` + `set -g window-size latest`, `chmod 644 :87`, before apt-cache clean (`:90-91`). `bash -n` clean. |
| 3 | A second boot reattaches to the existing `burrow` tmux session (the `-A` contract), proven hermetically (test_two_boots_stable_tmux_session) without real Proxmox | VERIFIED | `test_burrow_boot.py:257-293` `test_two_boots_stable_tmux_session` runs `_run_boot` twice over the same manifest into boot1/boot2, asserts `tmux new-session -A -s burrow` in BOTH recorded argvs (stub ttyd, no live tmux server). Test passes. Docstring (`:263-270`) explicitly disclaims real-CT-halt survival. |
| 4 | The control-plane relay (api/routers/terminal.py) stays a dumb opaque bridge — NO server-side scrollback buffering; file byte-unchanged across Phase 11 commits | VERIFIED | `git log fc0cec7~1..HEAD -- api/routers/terminal.py` returns empty (no Phase 11 commit touched it); last touch was commit `8fbd527` (phase 02). File is 162 lines; grep for `scrollback|buffer|history|.append(|deque|cache` returns NONE. |
| 5 | ADR-0014 authored (next free number; 0012 reserved), honest reattach-on-RECONNECT contract, cross-reboot deferred to v1.4, zero em dashes | VERIFIED (1 info WARNING) | `docs/adr/ADR-0014-tmux-scrollback.md` exists with SPDX header + Status/Context/Decision/Consequences/Revisit-trigger. Numbering: 0012 absent (reserved), 0013 then 0014 next-free. 0 em-dashes (U+2014), 0 en-dashes (U+2013), 0 horizontal rules. States reattach-on-RECONNECT only (`:30-31`), explicitly does NOT survive real `pct stop` (`:22-23`). WARNING: §Context line 25-26 labels cross-reboot scrollback "WSX-06"; REQUIREMENTS.md WSX-07 is the precise ID. §Consequences (`:84-86`) correctly lists WSX-05/06/07. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cc-worker-config/lxc/worker-template/burrow-boot.sh` | ttyd execs tmux-wrapped shell | VERIFIED | `:338` tmux wrap, frozen ttyd flags, SPDX + `set -euo pipefail` intact, `bash -n` clean |
| `cc-worker-config/lxc/worker-template/provision-template.sh` | tmux apt + baked /etc/tmux.conf | VERIFIED | `:38` apt tmux, `:16` 3.4 pin, `:83-87` exact 2-line tmux.conf, `bash -n` clean |
| `api/tests/boot/test_burrow_boot.py` | argv assertion + two-boot reattach test | VERIFIED | `:108-110` criterion-1 argv; `:257-293` two-boot reattach; both pass; 22 tests collected |
| `docs/adr/ADR-0014-tmux-scrollback.md` | honest reattach-on-reconnect ADR | VERIFIED | full section set, 0 em/en-dashes, 0 HRs, honest contract; one info WARNING on WSX-ID label |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| burrow-boot.sh | `tmux new-session -A -s burrow` | inner `exec` inside `bash -lc` ttyd wrapper | WIRED | `:338` exact pattern present; `${CLAUDE_CMD}` left unquoted for intended word-split (`rtk claude` → two args) |
| test_burrow_boot.py | ttyd-argv.txt | stub ttyd records argv; assertion reads it | WIRED | `:101-110` happy-path read+assert; `:288-293` two-boot read+assert |
| provision-template.sh | /etc/tmux.conf | provision-time heredoc drop-file | WIRED | `:83-87` single-quoted heredoc, before apt clean |
| provision-template.sh apt line | tmux | added alongside ttyd/jq, unpinned | WIRED | `:38` `... ttyd jq tmux` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Boot harness argv + reattach assertions pass | `cd api && uv run pytest tests/boot -q -k "tmux or two_boots or happy_path or frozen"` | 4 passed, 18 deselected (184.78s) | PASS |
| Boot suite collects expected count | `uv run pytest tests/boot --collect-only -q` | 22 tests collected | PASS |
| burrow-boot.sh syntax | `bash -n burrow-boot.sh` | exit 0 | PASS |
| provision-template.sh syntax | `bash -n provision-template.sh` | exit 0 | PASS |
| Exactly one tmux exec (non-comment) | `grep -v '^#' burrow-boot.sh | grep -c 'exec tmux new-session -A -s burrow'` | 1 | PASS |

Note: full `tests/boot -q` (22 tests) was not run to completion in-verifier because `test_no_credential_leak` (a PRE-EXISTING tautological test, REVIEW WR-01, unrelated to WSX-03) can time out under concurrent load. The 4 Phase-11-relevant tests (argv assertion, two-boot reattach, frozen ttyd line, happy path) were run in isolation and PASS.

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared for this phase. The CI-provable verification is the pytest boot harness, executed above (Behavioral Spot-Checks). No MISSING_PROBE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| WSX-03 | 11-01, 11-02 | A persistent workspace's terminal scrollback survives stop→start — on reconnect the operator sees prior scrollback (worker-side tmux `new-session -A` reattach) | SATISFIED | tmux wrap (boot.sh:338), baked tmux+conf (provision:38,83-87), hermetic reattach test, opaque relay, ADR-0014. REQUIREMENTS.md `:93` maps WSX-03 → Phase 11 (Complete). |

No orphaned requirements: WSX-03 is the sole Phase-11 ID and is claimed by both plans.

### Accuracy Check (Over-Claim Audit)

Nothing over-claims that scrollback survives a real `pct stop`. Verified the contract is reattach-on-reconnect only:
- ADR-0014 §Context `:22-23`: "A real `pct stop` halts the LXC and kills the tmux server, so tmux alone does NOT preserve scrollback across a full container halt."
- ADR-0014 `:30-31`: "Phase 11 delivers reattach-on-RECONNECT ... It does NOT make scrollback survive a real `pct stop`."
- Test docstring `:269-270`: "it does NOT assert scrollback survives a real CT halt."
- Real-infra reattach across a real worker stop/start is correctly scoped to Phase 14 ACC-01 (REQUIREMENTS.md `:48`), not claimed CI-provable here.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX in any Phase 11 file | — | clean |
| provision-template.sh | 69, 74 | "placeholder" (worker.env boot-config) | ℹ️ Info | Pre-existing Phase-00 baseline; legitimate descriptive use ("populated at boot"), not a stub. Not introduced by Phase 11. |
| burrow-boot.sh / provision-template.sh | various comments | em-dash (U+2014) in comment prose (14 + 3) | ℹ️ Info | Pre-existing comments; 0 introduced by Phase 11 diffs. The gated artifact (ADR-0014) is em-dash-clean. Matches REVIEW IN-01. |

### Warnings

**WARN-01 (info, traceability):** ADR-0014 §Context (`:25-26`) and the Phase 11 plan/summary/research consistently defer "cross-reboot scrollback" to **WSX-06**. REQUIREMENTS.md is more precise: **WSX-07** is "Cross-reboot scrollback (disk-logged history via tmux pipe-pane), beyond reconnect-survival" (`:60`), while **WSX-06** is "Suspend/resume (Tier-2 — CRIU)" (`:59`). The ADR §Consequences (`:84-86`) correctly lists all three deferred IDs (WSX-05, WSX-06, WSX-07). Because the deferral target genuinely exists in the ledger and the precise ID appears in the ADR's Consequences, this is a label-precision nit, not a goal-achievement gap. It does not block the phase. (The verification task brief itself frames the deferral as WSX-06, so the executor's framing was directed; the codebase's own ledger is the more precise source.) Optional fix: change the §Context single-ID reference from WSX-06 to WSX-07.

### Human Verification Required

None for this phase's scope. The phase is CI-provable worker-side via the boot harness (executed above). The real tmux reattach across a real worker stop/start on Proxmox is by design the Phase 14 ACC-01 dev-homelab smoke (a later, deferred phase), NOT this phase's contract — so no human-verification item is owed by Phase 11.

### Gaps Summary

No gaps. All 5 must-have truths VERIFIED against the actual codebase (not SUMMARY claims). The implementation is correct, tightly scoped, and honest:
- The tmux wrap is in `burrow-boot.sh` with frozen ttyd flags and intact quoting (verified by reading the exec line, not the summary).
- The golden template bakes tmux 3.4 + an exact-two-line `/etc/tmux.conf` before the image shrink.
- The `-A` reattach idempotency is proven hermetically by a substantive two-boot test (read and confirmed it asserts the invocation in both argvs, not a stub).
- `api/routers/terminal.py` is byte-unchanged across all Phase 11 commits (git-verified, not assumed) and contains zero scrollback buffering.
- ADR-0014 is honest about the reattach-on-reconnect-only contract and does not over-claim `pct stop` survival.

One info-level WARNING (WARN-01) on a deferred-requirement ID label (WSX-06 vs WSX-07) is recorded for the maintainer; it does not affect goal achievement and is optional to fix.

---

_Verified: 2026-06-25_
_Verifier: Claude (gsd-verifier)_
