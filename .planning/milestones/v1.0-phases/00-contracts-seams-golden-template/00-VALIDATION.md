---
phase: 0
slug: contracts-seams-golden-template
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-09
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Splits cleanly into **CI-provable** (contracts, envelope, Fake provider, static gates, models) and **NOT CI-provable** (real Proxmox/ttyd → dev-homelab smoke, deferred).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (api); biome/tsc are gate-only (ui) |
| **Config file** | `api/pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) — authored in Wave 0 |
| **Quick run command** | `cd api && uv run pytest tests/unit -x -q` |
| **Full suite command** | `cd api && uv run pytest` (Phase 0 = unit only; integration is Phase 1) |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** `cd api && uv run pytest tests/unit -x -q` + `uv run ruff check . && uv run mypy . --strict`
- **After every plan wave:** the full `static-gates` set (`ruff`, `ruff format --check`, `mypy --strict`, `tsc --noEmit`, `biome ci`, `uv lock --check`, `npm ci`, `reuse lint`)
- **Before `/gsd:verify-work`:** full suite + static gates green; dev-homelab items recorded as deferred
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| PLAT-02 | Envelope wraps `{data,meta:{requestId,timestamp},error}` | unit | `uv run pytest tests/unit/test_envelope.py -x` | ❌ W0 | ⬜ pending |
| PLAT-09 | snake↔camel alias round-trip on models | unit | `uv run pytest tests/unit/test_models.py -x` | ❌ W0 | ⬜ pending |
| PLAT-07, PLAT-08 | `FakeComputeProvider` honors the ABC (lifecycle, determinism) | unit | `uv run pytest tests/unit/test_fake_compute.py -x` | ❌ W0 | ⬜ pending |
| PLAT-06 | `DbProvider` ABC importable; `SqliteProvider` migrations run on temp DB | unit | `uv run pytest tests/unit/test_db_provider.py -x` | ❌ W0 | ⬜ pending |
| PLAT-06, PLAT-07 | Seam leakage: no Proxmox/SQLite symbols in services/routers/models | static | `uv run pytest tests/unit/test_seam_leakage.py -x` | ❌ W0 | ⬜ pending |
| CICD-01 | ruff/format/mypy/tsc/biome/lockfile gates pass | static (CI) | `static-gates` job | ❌ W0 | ⬜ pending |
| CICD-06 | every source file carries the SPDX header | static (CI) | `uvx reuse lint` | ❌ W0 | ⬜ pending |
| SETUP-01..05, WORK-01, WORK-04 | host-prime + template + boot-script correctness | manual / dev-homelab | not CI-automatable | n/a | ⬜ deferred |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. Task IDs assigned by the planner; rows are req-anchored.*

---

## Wave 0 Requirements

- [ ] `api/pyproject.toml` with `[tool.pytest.ini_options]` `asyncio_mode = "auto"` + ruff/mypy config
- [ ] `api/tests/conftest.py` — Fake providers + `httpx.ASGITransport` client fixtures
- [ ] `api/tests/unit/test_envelope.py`, `test_models.py`, `test_fake_compute.py`, `test_db_provider.py`, `test_seam_leakage.py`
- [ ] `.github/workflows/ci.yml` `static-gates` job
- [ ] `.reuse/dep5` (or `REUSE.toml`) for non-headerable files
- [ ] Framework install: `uv add --dev pytest pytest-asyncio`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `provision-template.sh` builds a working template; `pct template` succeeds | WORK-01 | Needs a real Proxmox node | Run on the Proxmox host; confirm template VMID exists and is a template |
| A `--full` clone boots; ttyd comes up on the LAN interface and is reachable | WORK-04 | Real CT + LAN | Clone by hand; `curl http://<worker-ip>:7681/` returns < 500 from the control plane |
| `claude` launches in ttyd; persistent ttyd survives a tab close | WORK-01 (SC-8) | Real terminal session | Open ttyd, close tab, reconnect — session still alive |
| `00-api-user-role.sh` token + scoped ACL authenticates and clones | SETUP-02, SETUP-03 | Real Proxmox auth | `pvesh get /cluster/nextid` with the token; attempt a scoped clone |
| Five-step `create→live→stop→start→destroy` acceptance gate | SETUP-04 | Full real-infra path | PROXMOX-PRIMING §8 STEP 4 runbook |

> All deferred per the operator's full-autonomous choice (no Proxmox reachable from the dev box). The planner marks these `human_needed`, not phase-blocking.

---

## Validation Sign-Off

- [ ] All CI-provable tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner maps task IDs)

**Approval:** pending
