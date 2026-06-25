<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
created: 2026-06-25
title: Host-prime kit GitHub-delivered via signed release (fetch+verify, not curl|bash)
area: cc-worker-config/host-prime
source: operator request during v1.3 autonomous run
severity: enhancement
resolves_phase: none
repo: cc-worker-config (separate repo)
files:
  - cc-worker-config/PRIMING.md
  - cc-worker-config/lxc/host-prime/
---

## Problem

Today `PRIMING.md` precondition P5 requires the operator to clone `cc-worker-config` on
the Proxmox node before running the numbered host-prime scripts. Operator wants a
GitHub-delivered "fetch and run on the node" flow instead (one command, no manual clone).

The scripts already exist and are idempotent/strict-mode/gated (`00-api-user-role.sh`,
`10`/`20` template, `40-control-plane.sh`, `lib/common.sh`). This is a DELIVERY change, not
a script rewrite.

Hard constraint: `00-api-user-role.sh` runs as `root@pam` and mints a high-value privsep
API token. Raw `curl … | bash` for that is a supply-chain footgun (no integrity check, no
inspection, MITM-able). Must not pipe the privileged step straight to bash.

## Solution

- Publish a **signed release asset** of `cc-worker-config` — `host-prime-vX.Y.Z.tar.gz`
  (the kit is multi-file: `lib/common.sh`, `.env`, `30-network-notes.md` — a single piped
  script can't carry it).
- Reuse the integrity machinery Burrow CI already has: cosign sign the tarball + GitHub
  attestations. Operator verifies with `cosign verify-blob` / `gh attestation verify`
  before extracting.
- **Download-then-run, pinned to a tag**: one bootstrap line curls the pinned-tag tarball
  to disk, verifies signature, extracts; operator then runs the numbered scripts (still
  inspectable, still gated). NOT `curl | bash`.
- Update `PRIMING.md` P5 to the fetch+verify flow; keep clone-on-node as the fallback.

## Notes

- Pairs with the v1.3 setup wizard: script provisions token/ACL → Phase 12 wizard
  validates it read-only → first workspace. Complementary, not a dependency.
- Scope decision (2026-06-25, autonomous run): kept OUT of v1.3 Phases 10-14 (Option A).
  Standalone `cc-worker-config` change; revisit independently.
