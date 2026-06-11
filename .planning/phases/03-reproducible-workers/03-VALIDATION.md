---
phase: 3
slug: reproducible-workers
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing `api/tests/`) + a Python `subprocess` boot-script harness |
| **Config file** | `api/pyproject.toml` (existing); manifest JSON-Schema test uses `jsonschema` |
| **Quick run command** | `cd api && uv run pytest tests/unit -q` |
| **Full suite command** | `cd api && uv run pytest -q` |
| **Estimated runtime** | ~30 seconds |

The boot-script harness drives `cc-worker-config/lxc/worker-template/burrow-boot.sh`
against a loopback fake control plane + `file://` bare-repo git remotes + a stub `ttyd`
on PATH (per RESEARCH §Validation Architecture). Real Proxmox boot is the dev-homelab
smoke gate, NOT CI.

---

## Sampling Rate

- **After every task commit:** Run `cd api && uv run pytest tests/unit -q`
- **After every plan wave:** Run `cd api && uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated/confirmed by the planner; each task maps to an automated command or a
> Wave-0 stub. Real-boot acceptance is a manual dev-homelab smoke (see Manual-Only).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 03-01 | 1 | WORK-02 | — | hermetic boot harness scaffold (fake CP + file:// repos + stub ttyd) | unit | `cd api && uv run pytest tests/boot/test_burrow_boot.py::test_fetch_then_clone_happy_path -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 03-01 | 1 | WORK-02 | T-03-01 | no token in worker.env; no cred/URL in any logged line; bounded retry then fail; frozen ttyd tail | unit | `cd api && uv run pytest tests/boot -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 03-01 | 1 | WORK-02 | — | jq + build tools baked into golden template | static | `grep -c 'apt-get install -y git curl build-essential ttyd jq' cc-worker-config/lxc/worker-template/provision-template.sh` | ✅ | ⬜ pending |
| 3-02-01 | 03-02 | 2 | WORK-05 | T-03-02 | manifest JSON-Schema fail-closed; unknown type rejected | unit | `cd api && uv run pytest tests/integration/test_manifest_schema.py -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 03-02 | 2 | WORK-05 | — | two boots → byte-identical plugin tree; only claude-plugin pulled (binary/npm-global baked) | unit | `cd api && uv run pytest tests/boot/test_burrow_boot.py -k "manifest or plugin or two_boots" -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03-03 | 2 | WORK-02, WORK-05 | — | ADR-0009 records boot-time-latest cadence | static | `test -f docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md && grep -c "boot-time-latest" docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` | ✅ | ⬜ pending |
| 3-03-02 | 03-03 | 2 | WORK-02, WORK-05 | — | CI runs shellcheck + the boot pytest tier | static | `grep -c "shellcheck" .github/workflows/ci.yml && grep -c "uv run pytest tests/boot" .github/workflows/ci.yml` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Boot-script test harness scaffold (loopback fake control plane + `file://` bare repos + stub `ttyd`)
- [ ] `manifest.schema.json` + a `jsonschema` validation test for `cc-worker-config/plugins/manifest.json`
- [ ] Credential-scrub assertion harness (sentinel-token no-leak test, mirroring `test_bootconfig.py`)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real worker boots, pulls config + plugins, ttyd serves Claude Code | WORK-02 | Requires real Proxmox + golden template; CI never touches real infra | Dev-homelab smoke: clone template, boot a workspace, confirm CLAUDE.md + plugin set present, ttyd reachable, no token in `/etc/burrow/worker.env` |
| Exact `enabledPlugins` on-disk shape for a directory plugin install | WORK-05 | Claude Code plugin-install internals are version-specific ([ASSUMED] on 2.1.170) | Boot a worker, inspect `~/.claude/plugins/` + settings; confirm pinned-ref plugins enabled |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-11
