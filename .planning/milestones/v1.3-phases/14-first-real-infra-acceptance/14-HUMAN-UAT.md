<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: partial
phase: 14-first-real-infra-acceptance
source: [14-RESEARCH.md, 14-ACCEPTANCE.md, PRIMING.md, 03-HUMAN-UAT.md, 04-HUMAN-UAT.md]
started: 2026-06-26T00:00:00Z
updated: 2026-07-13T02:55:00Z
---

## Current Test

[ACC-01 H9 core PASSED 2026-07-12 (items 1-5) on den01 real Proxmox via the control-plane API + den01 verification. Remaining: ACC-01 items 6-11 (reaper / idle / capacity / node-select / persistence scenarios) + ACC-02/03 (first live signed GHCR release).]

## About this checklist

This is the single consolidated operator checklist for the v1.3 real-infra acceptance gate
(ACC-01 / ACC-02 / ACC-03). It is run by a human on the dev homelab and against the first
live release. Nothing here is CI-provable: CI is hermetic (no real Proxmox) and this run does
NOT trigger a live release, so every item below is `result: [pending]` until the operator runs
it on real infrastructure.

It rolls up and supersedes the still-pending Phase 03 and Phase 04 HUMAN-UAT items (see the
mapping in `## Supersedes` below). Run the verify / release commands from
`.planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md`; record digests and run URLs
back into both files.

## Tests

### ACC-01: real homelab lifecycle, capacity, and persistence

1. **create** a worker (the H9 gate, step 1, mirrors PRIMING.md STEP 4)
   - expected: pick a small repo + branch from a LAN browser and submit; a worker CT is cloned
     `--full`, boots, and the row appears with status running.
   - result: [passed 2026-07-12 — worker `burrow-w-975` (vmid 975) created via the real Proxmox path (2026-07-10): cloned `--full`, booted, row `running`, ip 10.0.0.207; lifecycle re-driven this session. Browser-submit UX = operator visual.]

2. **live terminal** (the H9 gate, step 2)
   - expected: the terminal panel shows an interactive, resizable `claude` session over the
     ttyd subprotocol bridge.
   - result: [passed (structural) 2026-07-12 — ttyd listening `0.0.0.0:7681`, den01 HTTP 200, argv `ttyd ... exec tmux new-session -A -s burrow claude`. Interactive/resizable browser render = operator visual sign-off.]

3. **stop** with disk preserved (the H9 gate, step 3)
   - expected: status `stopped`, the LXC is stopped on its node, and the rootfs disk is
     preserved (not deleted).
   - result: [passed 2026-07-12 — POST /stop -> API `stopped`; den01 `pct status 975: stopped`, ttyd down; disk preserved (subsequent start restored the same disk/ip).]

4. **start** reconnects to the SAME session (the H9 gate, step 4)
   - expected: status `running`, the terminal reconnects to the same `claude` session (the
     tmux `-A` reattach), not a fresh shell.
   - result: [passed 2026-07-12 — POST /start -> API `running`, SAME ip 10.0.0.207 (disk intact); ttyd back (pid 270) HTTP 200 with `tmux new-session -A` reattach argv (boot-harness proves -A idempotency). Same-session visual on reconnect = operator confirm.]

5. **destroy** frees the VMID (the H9 gate, step 5)
   - expected: the LXC is gone, the VMID is freed, the row is soft-deleted; out-of-pool CTs are
     untouched.
   - result: [passed 2026-07-12 — DELETE -> API `destroyed`; den01 `975.conf does not exist`, `pct list` worker range empty (VMID freed); row soft-deleted.]

6. **reaper destroys a real injected orphan LXC + frees its VMID** (rolls up Phase 04 item 1, CAP-03)
   - expected: inject an orphan CT in the worker pool on a non-default node, run a reconcile
     pass; the reaper destroys it on the correct node and frees the VMID; out-of-pool CTs
     untouched.
   - result: [pending]

7. **idle workspace auto-stops after the real window** (rolls up Phase 04 item 2, CAP-02)
   - expected: boot a workspace, disconnect the terminal, wait `idle_window_s`; auto-stop emits
     `workspace.stopped` with `reason: idle`; a brief reconnect does NOT trip it.
   - result: [pending]

8. **capacity holds under real concurrent creates** (rolls up Phase 04 item 3, CAP-02)
   - expected: fire concurrent creates near the node-RAM threshold; no overcommit (the atomic
     check + reserve lock holds on real metrics).
   - result: [pending]

9. **real least-loaded node selection** (ACC-01 auto node selection)
   - expected: with multiple real nodes, a new create lands on the genuinely least-loaded node
     per the live metrics, not a hardcoded default.
   - result: [pending]

10. **real PERSISTENT workspace survives stop -> start with disk intact AND scrollback restored** (WSX-02/03 live proof)
    - expected: create a persistent workspace, write work to disk, `stop`, then `start`; the
      rootfs disk is intact AND the terminal scrollback is restored on reconnect (the tmux `-A`
      reattach replays the buffered output).
    - result: [pending]

11. **reaper never destroys a persistent STOPPED workspace on real CTs** (WSX-04 live proof)
    - expected: leave a persistent workspace stopped across a reconcile pass; the reaper leaves
      it intact (only orphans / non-persistent expired CTs are destroyed).
    - result: [pending]

### ACC-02: first live release (run via 14-ACCEPTANCE.md Steps A to D)

12. **release-please PR merges and the v\* tag triggers release.yml**
    - expected: merging the open release-please PR produces a version-bump commit, a regenerated
      CHANGELOG entry, and a `vX.Y.Z` tag; the tag triggers a green `release.yml` run that
      publishes both images.
    - result: [pending]

13. **actionlint passes on the live runner**
    - expected: the SHA-pinned `reviewdog/action-actionlint` step in `ci.yml` `static-gates` runs
      on the live Linux runner and passes (fail-fast gate, `reporter: github-check`,
      `fail_level: error`); it cannot run on the Windows dev box, so the live run is its proof.
    - result: [pending]

14. **harden-runner egress flipped audit -> block with the discovered allowlist**
    - expected: read the live audit run's discovered egress allowlist, fill `allowed-endpoints`
      (Fulcio / Rekor / TUF / OIDC / GHCR / github.com / objects.githubusercontent.com plus any
      surfaced), flip `egress-policy: audit` to `block` on all five jobs, re-run, and confirm the
      block-mode run still signs and publishes.
    - result: [pending]

### ACC-03: real GHCR publish + signature / provenance verify (run via 14-ACCEPTANCE.md Steps E to F)

15. **cosign verify passes by digest (keyless, fails loudly)**
    - expected: `cosign verify` against `ghcr.io/<owner>/burrow-api@sha256:<digest>` (and
      `burrow-ui`) prints the verified-claims summary (matched Fulcio identity, OIDC issuer, Rekor
      entry) and exits 0.
    - result: [pending]

16. **gh attestation verify passes by digest (assert on OUTPUT, not exit code)**
    - expected: `gh attestation verify oci://...@sha256:<digest> --owner <owner>` prints an
      explicit verified line and the SLSA provenance predicate bound to the digest; the operator
      asserts on the OUTPUT / JSON (T-14-01 exit-0 trap), paired with the loud-passing cosign
      verify above.
    - result: [pending]

## Summary

- Total items: 16
- Passed: 5 (ACC-01 H9 core — create/terminal/stop/start/destroy, items 1-5, verified 2026-07-12 via control-plane API + den01 SSH; items 2/4 mechanism proven, browser-visual is operator sign-off)
- Pending: 11 (ACC-01 items 6-11 real-infra scenarios not yet exercised — reaper/idle/capacity/node-select/persistence; ACC-02/03 first live signed GHCR release)

This phase lands `human_needed`. Run the items above on the dev homelab and the first live
release, then flip each `result: [pending]` to passed and record the evidence (digests, the
`vX.Y.Z` tag, run URLs).

## Supersedes

These items consolidate and supersede the still-pending Phase 03 and Phase 04 HUMAN-UAT
files. The operator runs them from THIS Phase 14 checklist (the prior files are marked
superseded-by-v1.3-Phase-14 and keep their original items for history).

| Source | Source item | Mapped to (this file) |
|--------|-------------|-----------------------|
| Phase 03 (`03-HUMAN-UAT.md`) | 1. Real worker boot + ttyd Claude session | items 1, 2 (create + live terminal) |
| Phase 03 | 2. `resolve_vmid` hostname parse | items 1, 9 (create + real node / VMID) |
| Phase 03 | 3. `x-access-token` GIT_ASKPASS username | item 1 (real create clone path) |
| Phase 03 | 4. cc-worker-config bootconfig auth | item 1 (real create bootconfig) |
| Phase 03 | 5. `enabledPlugins` on-disk shape live load | item 2 (live `claude` session) |
| Phase 04 (`04-HUMAN-UAT.md`) | 1. Reaper destroys a real orphan LXC | item 6 |
| Phase 04 | 2. Idle workspace auto-stops | item 7 |
| Phase 04 | 3. Capacity holds under concurrent creates | item 8 |
| Phase 04 | 4. Image build + Trivy on the GitHub runner | item 12 (the live `release.yml` / CI run) |
| Phase 04 | 5. Real GHCR publish + signature / provenance verify | items 15, 16 |

## Gaps

- ACC-01 / ACC-02 / ACC-03 are MANUAL-ONLY: they require real Proxmox CTs and a live signed
  release, which CI cannot exercise. There is no automated proof in this run by design.
- The actionlint RUN (item 13) cannot run on the Windows dev box (Phase 8 RELX-02); the first
  live Linux CI run is its only proof.
- The harden-runner block flip (item 14) needs the live audit telemetry (Step Security insights);
  do not flip with a guessed allowlist.

## References

- `.planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md` (the release / verify
  command runbook for items 12 to 16).
- `cc-worker-config/PRIMING.md` STEP 4 (the canonical H9 five-step gate for items 1 to 5).
- `.planning/milestones/v1.0-phases/03-reproducible-workers/03-HUMAN-UAT.md` and
  `.planning/milestones/v1.0-phases/04-hardening-release/04-HUMAN-UAT.md` (the superseded
  source files).
