<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: partial
phase: 03-reproducible-workers
source: [03-VERIFICATION.md]
started: 2026-06-11T00:00:00Z
updated: 2026-06-11T00:00:00Z
---

## Current Test

[awaiting dev-homelab smoke — real Proxmox node + golden template required]

## Tests

These 5 items are the documented "looks done but isn't" acceptance gate for Phase 3.
None are CI failures — CI is hermetic by design (real Proxmox is Out of Scope for CI).
All four roadmap success criteria are verified in code by 25 passing hermetic tests; these
confirm the real-infra half on the homelab.

1. **Real worker boot + ttyd Claude session** — re-run `cc-worker-config/lxc/host-prime/20-create-template.sh`,
   boot a real worker, confirm it fetches bootconfig → clones config+project → copies CLAUDE.md →
   lands in a live persistent LAN-bound ttyd Claude session. A boot failure must surface as a typed
   `boot.error` via the create-saga ttyd-health timeout (no silent hang). — SC-1 real half.
   - Status: ⬜ pending

2. **`resolve_vmid` hostname parse** — confirm the `${host##*-}` hostname-suffix parse (BURROW_HOSTNAME
   default `hostname -s`) yields the correct VMID against the operator-recorded
   `30-network-notes.md` / ADR-0004 static-IP↔VMID mapping. A wrong VMID must 404 safely. — [ASSUMED] T-03-05.
   - Status: ⬜ pending

3. **`x-access-token` GIT_ASKPASS username** — confirm the username convention matches the operator's
   pending `mint_repo_credential` mechanism (GitHub App installation token / fine-grained PAT). If the
   mechanism is a deploy-key / GitLab job token, the askpass Username branch must change. — A2/A3.
   - Status: ⬜ pending

4. **Config-repo (cc-worker-config) auth model** — confirm cc-worker-config is operator-reachable with
   the project-scoped bootconfig credential, or document its separate auth (endpoint is frozen; this is
   an operator contract, not a code change). — A5 / Open-Q-1.
   - Status: ⬜ pending

5. **`enabledPlugins` on-disk shape for claude-code@2.1.170** — confirm `~/.claude/settings.json`
   `enabledPlugins[<name>]=true` is the correct directory-install enablement shape and that the pulled
   claude-plugin actually loads (`claude plugin list` / `claude --debug`). The harness proves the
   clone+settings-write+idempotence shape; the homelab proves the live load. — A1 / Open-Q-2.
   - Status: ⬜ pending

## Notes

- CI-provable contract: PASSED (25 hermetic tests; `reuse lint` 242/242; shellcheck + pytest tiers wired).
- Consistent with the Phase 2 closeout pattern (`human_needed — real-* deferred`).
- When the homelab smoke passes, flip each item to ✅ and re-run `/gsd:verify-work 3` (or update
  03-VERIFICATION.md `status: passed`).
