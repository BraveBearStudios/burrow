<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: human_needed
phase: 22
verified: pending
---

# Phase 22: Live Homelab Acceptance Capstone - Verification

**Goal:** Prove the v1.4 milestone on the real Proxmox homelab. The remaining ACC-01
lifecycle items (6 to 11) pass on real CTs across two live worker nodes, the GUI
credential store is verified live on den01, and the signed v1.4 release re-verifies
against a homelab-pulled image. This is the human-UAT capstone that closes v1.4.

This phase is ACCEPTANCE / HUMAN-UAT, not code. It is NOT CI-provable: CI is hermetic
and never touches real Proxmox. It lands `human_needed` until the operator runs the
runbook in `22-HUMAN-UAT.md` and records evidence. The phase is complete, and v1.4 is
closed, once the operator marks all UAT items passed.

## Success Criteria (pending checklist)

Each criterion maps to a UAT item in `22-HUMAN-UAT.md`. Flip to `[x]` when the mapped
item passes with recorded evidence.

- [ ] **Criterion 1 (ACC-04): reaper + idle + capacity** (UAT-1). The reaper destroys
  a real injected orphan LXC and frees its VMID on a non-default node; idle auto-stop
  fires after the real `idle_window_s` and a brief reconnect does not trip it; capacity
  holds under real concurrent creates (distinct VMIDs, no overcommit).
- [ ] **Criterion 2 (ACC-04 item 9): least-loaded node selection** (UAT-2). A
  node-auto-select create lands on the genuinely least-loaded of two live worker nodes
  per live metrics, not a hardcoded default.
- [ ] **Criterion 3 (ACC-04): persistence** (UAT-3). A persistent workspace survives a
  real stop then start with disk and scrollback intact (same VMID/IP, tmux `-A`
  scrollback replayed), and the reaper never destroys a persistent stopped workspace.
- [ ] **Criterion 4 (ACC-05): GUI credential store live on den01** (UAT-4). Migration
  `004` applied on the real SQLite (credential columns + `audit_log`); a GUI-set
  Proxmox token applies WITHOUT a restart (a create still works, async-202, no 504) AND
  survives a restart (reloaded at startup, last4 unchanged).
- [ ] **Criterion 5 (ACC-06 rider): live re-verify** (UAT-5). A homelab-pulled
  `@sha256:` image re-verifies: `cosign verify` (keyless, by digest) and
  `gh attestation verify --owner BraveBearStudios` both pass on the OUTPUT.

Precondition (UAT Step 0): the v1.4 release is deployed to lintool03 with the Phase 18
credential GUI and the Phase 19 async-202 create, `BURROW_SECRET_KEY` unchanged, and
health `ok/ok/ok` on `:8081` and the NPM domain.

## Evidence (to be filled by the operator)

Record the concrete artifact for each item as you run it.

- **Step 0 (deploy):** release commit / tag deployed, image source (local build vs
  pulled `<REL>`), `BURROW_SECRET_KEY` last-6 unchanged (yes/no), health output on
  `:8081` and the NPM domain, Credentials screen renders (yes/no).
- **UAT-1A (reaper orphan):** injected VMID + node, the `reaper.destroyed` log line,
  `pct list` confirming the VMID freed.
- **UAT-1B (idle auto-stop):** workspace id, the `terminal.disconnected` last event,
  the `workspace.stopped` event with `reason: idle`, and the brief-reconnect
  stayed-running observation. Note the `idle_window_s` value used.
- **UAT-1C (capacity):** the distinct VMIDs the concurrent creates received (no
  duplicate), and any capacity-refusal envelope observed.
- **UAT-2 (node selection):** per-node RAM fractions at create time and the `node` the
  auto-select create landed on (the least-loaded one).
- **UAT-3 (persistence):** vmid/ip before and after stop/start (same), the
  disk-file-intact check, the scrollback-restored observation, and the
  reaper-spared-it result for the stopped persistent workspace.
- **UAT-4 (credentials):** migration-004 column list + `audit_log present`, the token
  `last4` after the GUI set, the no-restart create reaching `running`, and the
  last4 before/after the restart (unchanged) with health `ok/ok/ok`.
- **UAT-5 (re-verify):** the pulled `@sha256:` digest, the cosign verified-claims
  summary, and the `gh attestation verify` verified output. Reference release run
  `29355954285` (ACC-06 proven on the runner in Phase 20).

## Verdict

**Status: human_needed.** No automated proof exists or is possible for this phase by
design. When the operator has run `22-HUMAN-UAT.md`, flipped all five criteria to
passed above, and recorded the evidence, set this file's frontmatter to
`status: passed` / `verified: <date>` and mark v1.4 complete. Passing this phase closes
the v1.4 "Ship & Harden" milestone.
