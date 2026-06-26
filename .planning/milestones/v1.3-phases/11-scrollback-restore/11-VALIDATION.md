---
phase: 11
slug: scrollback-restore
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (hermetic boot harness, `api/tests/boot/`; stub ttyd records argv) |
| **Config file** | `api/pyproject.toml`; stub ttyd at `api/tests/boot/stub_ttyd_bin` + `conftest.py` |
| **Quick run command** | `cd api && uv run pytest tests/boot -q` |
| **Full suite command** | `cd api && uv run pytest -q` |
| **Estimated runtime** | ~10–30 seconds (boot harness) |

---

## Sampling Rate

- **After every task commit:** `cd api && uv run pytest tests/boot -q`
- **After every plan wave:** full `cd api && uv run pytest -q`
- **Before `/gsd:verify-work`:** full suite green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-xx | boot-tmux | 1 | WSX-03 | — | ttyd argv wraps shell in `tmux new-session -A -s burrow` | unit (boot harness) | `cd api && uv run pytest tests/boot -k tmux -q` | ✅ | ⬜ pending |
| 11-02-xx | provision | 1 | WSX-03 | — | tmux installed; `/etc/tmux.conf` sets history-limit 50000 + window-size latest | unit (boot harness) | `cd api && uv run pytest tests/boot -q` | ✅ | ⬜ pending |
| 11-03-xx | reattach-idempotency | 2 | WSX-03 | — | two boots both carry stable `-A -s burrow` invocation (reattach contract) | unit (boot harness) | `cd api && uv run pytest tests/boot -k reattach -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New argv assertion + second-boot reattach test in `api/tests/boot/test_burrow_boot.py`
      (criteria 1 + 3)

*Existing boot-harness infrastructure (stub ttyd, conftest fixtures) covers the rest — no framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real tmux reattach showing prior scrollback after a worker stop/start on real Proxmox | WSX-03 | Real-infra only; CI uses the hermetic stub-ttyd argv harness | Deferred to Phase 14 (ACC-01) dev-homelab smoke |

*All CI-provable behaviors (argv wiring + `-A` idempotency contract) have automated verification; real reattach is the Phase 14 gate by design. Cross-CT-reboot scrollback persistence is out of scope (v1.4, WSX-06).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers the new boot-harness assertions
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
