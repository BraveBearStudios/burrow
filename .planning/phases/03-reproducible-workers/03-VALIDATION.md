---
phase: 3
slug: reproducible-workers
status: draft
nyquist_compliant: false
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
| TBD | — | — | WORK-02 / WORK-05 | T-03-* | no token in worker.env; no cred/URL in logs | unit/integration | `cd api && uv run pytest -q` | ❌ W0 | ⬜ pending |

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
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
