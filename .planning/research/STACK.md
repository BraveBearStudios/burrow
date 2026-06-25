<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Stack Research — Burrow v1.3 "Go Live"

**Domain:** Self-hosted browser manager for concurrent Claude Code sessions (Proxmox LXC workers). SUBSEQUENT milestone — NEW capabilities only.
**Researched:** 2026-06-24
**Confidence:** HIGH (every external version verified against the upstream release page; integration points read in the live repo files)

> **Scope.** This file covers ONLY the stack deltas the three v1.3 capabilities need (setup wizard, real-boot v2 persistence, first real-infra acceptance). The shipped v1.2 stack — FastAPI / Python 3.12 / uv / proxmoxer / aiosqlite; React 19 / TanStack Query / Zustand / xterm.js / react-mosaic / Vite / biome; the cosign/syft/trivy/release-please supply-chain path — is already validated and is NOT re-litigated here. The full v1.0 pin table lives in git history of this file; this revision is the v1.3 delta.

## Headline Findings (read first)

1. **Terminal persistence → tmux 3.4 (Ubuntu 24.04 apt), NOT zellij.** One-line change in `burrow-boot.sh`'s `exec ttyd` + a small `/etc/tmux.conf` baked in `provision-template.sh`. **No app-code change in `api/` or `ui/`.** ttyd's own wiki documents the exact pattern: `ttyd tmux new -A -s <name>`.
2. **Proxmox persistence is mostly already there.** `stopCt` already halts the CT and **preserves its disk** (it never destroyed anything — only `destroyCt` does). WSX-02's real new work is **snapshot/rollback**: three new `ComputeProvider` methods over the existing proxmoxer call style. **Suspend/resume is OUT** — CRIU is broken/unsupported for unprivileged LXC. Snapshots **require ZFS / LVM-thin / Ceph storage — NOT `dir`** (an operator infra prerequisite, not code).
3. **Setup wizard needs ZERO new dependencies** — frontend or backend. It is plain TanStack Query mutations + a Zustand step slice hitting new FastAPI routes that call **existing** `ProxmoxComputeProvider` methods. Token storage reuses the existing `pydantic-settings` `.env` pattern (`settings.proxmox_token_value`).
4. **First real release: the pins already in the repo are current and correct.** Stay on the pinned action SHAs (they install cosign **v2.x** via `cosign-installer@v3.10.0`). Do NOT chase cosign v3 this milestone (it needs cosign-installer v4). The Trivy SHA-pin is the right mitigation for 2026's two Trivy supply-chain compromises — verify, don't float.

## Recommended Stack (NEW in v1.3)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **tmux** | **3.4** (Ubuntu 24.04 `apt`, baked in `provision-template.sh`) | Durable terminal multiplexer in the worker: holds the live Claude session + full scrollback server-side so a reconnecting browser reattaches to the SAME session (WSX-03). | Already in the worker's distro repo → reproducible + apt-pinnable, no `curl\|bash` of a binary. ttyd's wiki documents `ttyd tmux new -A -s ttyd` exactly. tmux 3.4 has `window-size latest` (the resize fix for a single reconnecting web client). zellij is pre-1.0 (0.41) and has **no apt package** on 24.04. |
| **Proxmox snapshot API** (via existing `proxmoxer==2.3.0`) | PVE 8.x endpoints | `POST/GET /nodes/{node}/lxc/{vmid}/snapshot`, `POST .../snapshot/{name}/rollback`, `DELETE .../snapshot/{name}` for persistent/snapshotted workspaces (WSX-02). | No new Python dep — proxmoxer already reaches arbitrary PVE paths in the exact `self._api.nodes(node).lxc(vmid)...` style used today in `proxmoxProvider.py`. Adds three async methods to the `ComputeProvider` seam. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | — | Setup wizard frontend | A multi-step component using React Query mutations + a Zustand wizard slice (mirror `NewWorkspaceModal.tsx`'s boot-progress states). No form lib, no wizard lib, no new state lib. |
| (none) | — | Setup wizard backend | New `routers/setup.py` validate endpoints calling existing `ProxmoxComputeProvider.healthcheck / getStatus / getNodeMemory` + the existing `/health`. No new pip dep. |
| (none) | — | Token storage | `settings.proxmox_token_value` already exists in `api/config.py` + `.env.example`. The wizard validates a provided token; it is persisted to gitignored `.env`, NEVER returned in any `/api/v1` response or logged. |

### Release-chain tools (already pinned — confirm for first live run, do not bump)

| Tool | Pinned in repo | Current upstream (2026-06) | Notes for the first real run |
|------|----------------|----------------------------|------------------------------|
| `sigstore/cosign-installer` | `@v3.10.0` (installs **cosign v2.x**) | installer v4 (installs cosign v3.0.6); cosign CLI latest **v3.1.1** | **Keep v3.10.0.** cosign v2 keyless sign + the `cosign verify` flags documented in `release.yml` are correct as written. cosign v3 requires installer v4 — a separate deliberate bump, NOT part of "go live". |
| `anchore/sbom-action` (syft) | `@v0.20.7` | syft CLI latest **v1.45.1** | The action bundles its own syft; pin is fine. SPDX + CycloneDX dual-format already wired. No change. |
| Trivy image scan (in `ci.yml`) | SHA-pinned action | trivy CLI latest **v0.71.2** | ⚠️ Trivy's action/registry was compromised twice in 2026 (Mar 19; malicious v0.69.4/.5/.6). The repo's SHA-pin is exactly the right mitigation — **verify the pinned SHA predates/postdates safely and never float to a tag.** |
| `googleapis/release-please-action` | `@v4.4.1` | v4 line current | Config `release-type: simple`, manifest-seeded. First live `push:main` opens the v1.3.0 PR. In v4 read `steps.release.outputs.release_created`, never the old `releases_created`. No change. |
| `actions/attest-build-provenance` + `gh attestation verify` | `@v3.0.0` action; gh built-in | current | Runbook command in `release.yml` is correct: `gh attestation verify oci://ghcr.io/<owner>/burrow-api@sha256:<digest> --owner <owner>`. |
| `cosign verify` (runbook) | documented in `release.yml` | matches cosign v2.x | `--certificate-identity-regexp 'https://github.com/<owner>/burrow/.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com`. Correct for the keyless signature this pipeline emits. |

## Integration Points (named, in the real files)

### 1. Terminal persistence — `cc-worker-config/lxc/worker-template/`

**`--once` is already gone** (`burrow-boot.sh` lines 322-331; ADR-0006 "tab close DETACHES"). The remaining gap is the multiplexer: today ttyd execs `bash -lc "cd … && exec ${CLAUDE_CMD}"`, so the "session" is ttyd's own child pty — a WS reconnect lands on a **fresh shell with no scrollback**. tmux closes that gap with no app change.

**`provision-template.sh` — add `tmux` to the apt line (currently line 37) and bake a config:**
```bash
apt-get install -y git curl build-essential ttyd jq tmux   # add tmux
cat >/etc/tmux.conf <<'EOF'
set -g history-limit 100000   # deep scrollback restored on reattach (WSX-03)
set -g mouse on               # xterm.js wheel -> tmux scroll
set -g status off             # no tmux status bar; the browser is the chrome
set -g window-size latest     # follow the most-recent client size (tmux 3.4);
                              # avoids the "stuck at smallest detached client" resize bug
set -g escape-time 10         # snappy ESC for a TUI agent over the WS
EOF
```

**`burrow-boot.sh` lines 327-331 — the single `exec` change:**
```bash
exec ttyd \
  --port 7681 \
  --writable \
  --interface 0.0.0.0 \
  tmux -f /etc/tmux.conf new -A -s burrow \
    bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"
```
`new -A -s burrow` = "attach if the session exists, else create it." Every browser reconnect (the existing `useTerminal.ts` backoff path) re-runs this `exec`, reattaching to the **same live `burrow` session** with its full server-side scrollback. Destroy stays the only kill path; tab-close still just detaches. **No change to `api/` (WS proxy) or `ui/` (xterm.js)** — both are agnostic to what runs behind ttyd.

### 2. Proxmox persistence — `api/compute/provider.py` + `proxmoxProvider.py` + `fakeProvider.py`

**Reframe WSX-02 correctly:** "workspaces that survive stop/start instead of being destroyed" is **already true at the compute layer.** `stopCt` (`proxmoxProvider.py` line 250) calls `.status.stop.post()`, which halts the CT and **preserves its disk**; only `destroyCt` `delete()`s. The v1.2 gap was UX/state-machine, not compute. So WSX-02 = (a) keep disk on stop (done) + (b) add **snapshot/rollback** for checkpoint-before-risky-op.

Add three methods to the `ComputeProvider` ABC (`provider.py`), implement in both providers, each `_block()`-ed on its UPID exactly like the existing lifecycle mutations:
```python
# proxmoxProvider.py — same self._api.nodes(node).lxc(vmid) style
async def snapshotCt(self, node, vmid, snapname, description="") -> ComputeTask:
    upid = await asyncio.to_thread(
        lambda: self._api.nodes(node).lxc(vmid).snapshot.post(
            snapname=snapname, description=description))
    return await self._block(upid, timeout=self._settings.task_timeout)

async def rollbackCt(self, node, vmid, snapname) -> ComputeTask:
    upid = await asyncio.to_thread(
        lambda: self._api.nodes(node).lxc(vmid).snapshot(snapname).rollback.post())
    return await self._block(upid, timeout=self._settings.task_timeout)

async def listSnapshots(self, node, vmid):
    return await asyncio.to_thread(lambda: self._api.nodes(node).lxc(vmid).snapshot.get())
```
- **No `vmstate`/memory param** — that is QEMU-only. LXC snapshots are **disk-only (filesystem)**, which is exactly the persistence model needed and sidesteps CRIU entirely.
- `FakeComputeProvider` gets an in-memory snapshot dict so the saga/integration tests stay hermetic (same discipline as the existing methods; the Fake is the CI substrate per `docs/ci-cd-and-testing.md` §4.4).
- **Storage prerequisite (operator infra, document in host-prime):** the worker pool's storage must be `zfspool` / `lvmthin` / `ceph` — Proxmox refuses `pct snapshot` on `dir` storage type even on a ZFS/LVM-thin filesystem.
- **ACL prerequisite (operator, document in host-prime):** snapshot/rollback need `VM.Snapshot` (and rollback) on the `burrow@pve` token's pool path — a Proxmox role addition, NOT a code change.

### 3. Setup wizard — `api/routers/` + `ui/src/`

- **Backend:** new `routers/setup.py` with read-only validate endpoints calling **existing** provider methods — `healthcheck()` (`proxmoxProvider.py` line 329, already wraps `version.get()`), `getNodeMemory()`, `getStatus(template_vmid)` to verify the golden template exists — plus confirming `/health` (db + proxmox) goes green. All under `/api/v1`, all using the standard `data`/`meta`/`error` envelope. PVE-side least-priv user/role/token creation stays operator-run; the wizard validates a *provided* token and guides the manual steps.
- **Frontend:** a multi-step component using TanStack Query mutations per validate call + a Zustand slice for step/progress (same pattern as `layoutStore.ts` and `NewWorkspaceModal.tsx`'s boot-progress). No new dependency.
- **Token security (reuse the existing pattern):** the token lives in `settings.proxmox_token_value` (pydantic-settings, read from gitignored `.env`). The wizard accepts + validates it, then guides the operator to persist it to `.env` (v1 no-secrets-manager posture, PROJECT.md Out of Scope). It is **NOT returned in any response, NOT logged** — same redaction discipline as `git_credential_token` in `burrow-boot.sh`. Validate endpoints return only a boolean/health verdict.

## Installation

```bash
# Worker template (in provision-template.sh, inside the CT) — the ONLY new install:
apt-get install -y tmux        # 3.4 from Ubuntu 24.04 noble

# api/ — NO new dependency. Snapshot methods use the already-pinned proxmoxer==2.3.0.
# ui/ — NO new dependency. Wizard uses @tanstack/react-query + zustand already present.
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **tmux 3.4** (apt, baked) | **zellij 0.41** | Only if you wanted built-in session-serialization-to-disk surviving a worker reboot/full clone. But Burrow's persistence is the LXC disk (snapshot/stop), not the multiplexer — and zellij has no apt package on 24.04, is pre-1.0, and would need a pinned binary download (a new supply-chain surface against the "no curl\|bash of a binary" preference). tmux wins on reproducibility + the documented ttyd pattern. |
| **LXC disk snapshot (stop + snapshot/rollback)** | **CT suspend/resume (CRIU)** | Essentially never for unprivileged LXC. CRIU `pct suspend` fails on unprivileged CTs ("Can't dump nested uts namespace" / cgroup limits); upstream treats it as unsupported. Stop preserves disk and is reliable; that IS the persistence story. |
| **ZFS / LVM-thin storage** | **`dir` storage** | Never, if you want snapshots. Proxmox refuses `pct snapshot` on a `dir`-storage CT even on a ZFS/LVM-thin filesystem — the *storage type* must be `zfspool`/`lvmthin`/`ceph`. Operator infra prerequisite, not code. |
| **Keep cosign-installer@v3.10.0 (cosign v2)** | **Bump to installer v4 (cosign v3)** | Defer. cosign v2 keyless sign + verify is fully functional and already wired/documented. v3's new-bundle-format is a deliberate future bump, not first-live-release scope. |
| **release-please** | semantic-release | Already chosen and shipped in v1.2 (RELX-01). Settled. |

## What NOT to Use / NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| zellij in the worker | Pre-1.0, no 24.04 apt pkg, extra binary-download supply-chain surface; its disk-serialization is redundant with LXC-disk persistence | tmux 3.4 from apt |
| `pct suspend` / CT suspend-resume / CRIU | Unsupported/broken for **unprivileged** LXC (the workers are unprivileged) | LXC `stop` (disk preserved) + snapshot/rollback |
| `dir` storage for worker CTs | Proxmox blocks snapshots on `dir` storage type regardless of underlying FS | ZFS or LVM-thin (or Ceph) storage backend — operator prerequisite |
| QEMU `vmstate` / RAM snapshots | Not available for LXC; LXC snapshots are disk-only | Disk-only `lxc/{vmid}/snapshot` (all WSX-02 needs) |
| Any new frontend dep for the wizard (Formik / react-hook-form / wizard libs / a new state lib) | The wizard is a few sequential mutations + a step counter; existing TanStack Query + Zustand cover it; new deps add bundle + supply-chain + audit surface for nothing | `@tanstack/react-query` mutations + a Zustand wizard slice (mirror `NewWorkspaceModal`) |
| Any new backend dep for the wizard | Validation = existing `ProxmoxComputeProvider.healthcheck/getStatus/getNodeMemory` + existing `/health` | The provider methods that already exist |
| Returning/logging the Proxmox token from the wizard | Leaks the operator's PVE credential; breaks the no-secrets posture | Validate-only endpoints; token stays in gitignored `.env` via `settings.proxmox_token_value`; redact like `git_credential_token` |
| A secrets manager for the token | Explicitly hosted-path scope (PROJECT.md Out of Scope); v1 is `.env` | gitignored `.env` + `.env.example` template |
| Bumping cosign to v3 / chasing latest syft/trivy CLI mid-milestone | Churn during a "prove it works on real infra" milestone; the SHA-pinned actions bundle correct tool versions | The pins already in `release.yml` / `ci.yml` |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| tmux 3.4 | ttyd 1.7.7, Ubuntu 24.04, xterm.js 6.0.0 | `ttyd tmux new -A -s` is the wiki-documented pattern; `window-size latest` requires tmux ≥2.9 (3.4 has it). |
| proxmoxer 2.3.0 | PVE 8.x snapshot endpoints | `nodes().lxc().snapshot` path already reachable; no proxmoxer upgrade needed for snapshot/rollback. |
| cosign-installer v3.10.0 | cosign v2.x CLI + the `cosign verify` flags in release.yml | ⚠️ cosign-installer v3 **cannot** install cosign v3 — installer v4 is required for v3. Stay on v2 for first release. |
| `attest-build-provenance@v3.0.0` + `gh attestation verify` | OCI subject by digest, `--owner` | Runbook command in release.yml is current and correct. |

## Open pins to confirm at the dev-homelab smoke (surface, don't silently assume)

1. **Exact proxmoxer snapshot param names** (`snapname`, `description`) on the running PVE version — confirm at the real-infra smoke (the path pattern is solid; param names mirror qemu). 
2. **Worker pool storage type is `zfspool`/`lvmthin`/`ceph`, not `dir`** — verify before relying on rollback (ACC-01).
3. **`burrow@pve` token has `VM.Snapshot`/rollback on the pool path** — add the role grant in host-prime before WSX-02 lands.
4. **First-release tag-by-GITHUB_TOKEN may not re-trigger `release.yml`** (already flagged in `release-please.yml`) — verify on the first live release; re-run on the tag if needed (ACC-02).
5. **harden-runner `egress-policy: audit` → `block` flip** uses the discovered allowlist — an on-runner ACC-02 step, not discoverable on the dev box.

## Sources

- ttyd repo + wiki (`tsl0922/ttyd`) — latest ttyd **1.7.7**; `--writable`/`--interface`/`--once` flags; **`ttyd tmux new -A -s ttyd`** persistent-session pattern. HIGH.
- tmux upstream + Ubuntu Launchpad (noble) — tmux **3.4** is the 24.04 apt version; `history-limit`/`mouse`/`status`/`window-size latest`/`aggressive-resize` knobs; the `window-size`/smallest-client resize behavior (tmux/tmux#1591, #2594). HIGH.
- zellij releases + Snapcraft + 24.04 install guides — zellij **0.41** (pre-1.0), **no apt package on 24.04**, snap/binary only; session-resurrection is opt-in serialization. MEDIUM (confirms the negative: not packaged).
- Proxmox VE wiki "Unprivileged LXC containers" + Proxmox forum (suspend/CRIU threads) + checkpoint-restore/criu#1430 — **CT suspend/CRIU unreliable/unsupported for unprivileged LXC**. HIGH.
- Proxmox forum + 4sysops + storage guides — LXC **snapshots require ZFS/LVM-thin/Ceph, NOT `dir` storage type**; `pct rollback` works the same for unprivileged. HIGH.
- Proxmox API viewer pattern + proxmoxer docs/examples — `nodes/{node}/lxc/{vmid}/snapshot` (POST/GET), `.../snapshot/{name}/rollback` (POST), DELETE; **LXC snapshots are disk-only (no `vmstate`)**. MEDIUM-HIGH (path pattern confirmed across multiple sources; mirrors the qemu pattern proxmoxer documents — verify exact param names at the smoke).
- sigstore/cosign + cosign-installer releases (GitHub) — cosign CLI **v3.1.1** latest; **cosign-installer v3.x installs cosign v2.x; installer v4 required for cosign v3** (default install v3.0.6 on installer v4). HIGH.
- anchore/syft releases — syft CLI **v1.45.1** latest (the action bundles its own). HIGH.
- aquasecurity/trivy releases + StepSecurity/Aqua incident advisories — trivy CLI **v0.71.2** latest; **2026 supply-chain compromises (Mar 19; v0.69.4/.5/.6)** → SHA-pin is the correct mitigation. HIGH.
- googleapis/release-please-action — **v4** current; `release-type: simple` + manifest config (matches the repo); use `release_created` output. HIGH.
- GitHub CLI manual `gh attestation verify` — `oci://…@sha256:<digest> --owner <owner>` syntax confirmed. HIGH.
- Repo files read directly: `api/config.py`, `api/compute/provider.py`, `api/compute/proxmoxProvider.py`, `api/pyproject.toml`, `ui/package.json`, `.env.example`, `.github/workflows/release.yml` + `release-please.yml`, `release-please-config.json`, `cc-worker-config/lxc/worker-template/burrow-boot.sh` + `provision-template.sh`. HIGH (load-bearing integration points).

---
*Stack research for: Burrow v1.3 "Go Live" (setup wizard + real-boot persistence + first real-infra acceptance)*
*Researched: 2026-06-24*
