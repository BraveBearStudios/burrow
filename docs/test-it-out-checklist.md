<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow — Test It Out (real-infra acceptance)

> **Where things stand:** Tags `v1.0`/`v1.1`/`v1.2` exist on the remote (cut manually at each milestone close) but are NOT fetched locally. There is NO GitHub Release and NO GHCR image published yet (`gh release list` is empty), and it is UNKNOWN whether `ci.yml` has ever executed on a live GitHub runner. So ACC-02 (first release-please PR → tag → publish) and ACC-03 (real GHCR publish + cosign/attestation verify) have NEVER run live. Everything below is the deferred acceptance work that closes ACC-01 (real Proxmox), ACC-02 (first CI + release), and ACC-03 (supply-chain verify).

## 0. What you need (prerequisites)

- **Real Proxmox VE 8.x node/cluster** reachable on the LAN, with `root@pam` on the node that will host the golden template (PRIMING.md P1). For the v1.2 multi-node auto-select check you need **>=2 primed worker nodes** of differing RAM load.
- **CT-rootfs THIN storage** (`lvmthin` or `zfspool`, NOT thick LVM) AND a **dir-type (`vztmpl`) storage** for the downloaded CT image, on that node (PRIMING.md P2; `20-create-template.sh` `ROOTFS_STORAGE` must be thin).
- **LAN bridge** (e.g. `vmbr0` / `WORKER_BRIDGE`) on the same LAN segment the control plane and a browser client share; verify with `ip link show <bridge>` (PRIMING.md P3).
- **A dedicated, NON-ephemeral control-plane box** (separate LXC or small VM, Ubuntu 24.04) on that LAN, with a DNS/host entry, that runs `burrow.service` + nginx, sitting OUTSIDE the worker VMID/IP range (PRIMING.md P4 / STEP 3).
- **Worker IP range excluded from DHCP** on the router/pfSense/dnsmasq. There is NO Proxmox-side enforcement; an overlapping DHCP lease is a live IP collision on worker boot (30-network-notes.md load-bearing obligation).
- **The burrow repo AND the vendored `cc-worker-config/` subdir checked out on the node**; `.env` gitignored in the burrow checkout (the host-prime kit refuses to write the token unless `git check-ignore .env` passes).
- **Filled, gitignored `.env`** on the control plane from `.env.example`: `PROXMOX_HOST`, `PROXMOX_USER=burrow@pve`, `PROXMOX_TOKEN_NAME=burrow`, `PROXMOX_CA_CERT_PATH` (real node CA cert — do NOT use `verify_ssl=False`), `TEMPLATE_VMID`, `WORKER_POOL_START/END`, `DEFAULT_NODE`, `WORKER_SUBNET/GATEWAY/BRIDGE/PREFIX`, `CONFIG_REPO/CONFIG_BRANCH`, `GIT_CREDENTIAL_TOKEN` (short-lived repo-scoped), `CAPACITY_THRESHOLD=0.80`, idle window, TTYD/CLONE/TASK timeouts, `ALLOWED_ORIGIN` (the LAN UI origin, NEVER `*`). `PROXMOX_TOKEN_VALUE` is left blank and pasted at the hidden prompt in STEP 0 / STEP 3.
- **A GitHub repo with Actions + GHCR enabled:** origin `https://github.com/BraveBearStudios/burrow.git`, maintainer push/merge rights, Actions allowed (Settings → Actions → General → Allow all actions), GitHub Advanced Security / code scanning enabled (for the Trivy SARIF upload).
- **`gh` CLI v2.89.0 + `cosign` installed locally** (PowerShell + Git Bash on the Windows 11 dev host). Run `gh` + `git` from Git Bash (PowerShell mangles JSON `-d` payloads and the cosign regexp args). A `docker`/`crane`/`oras` client to resolve a tag to its `@sha256` digest.
- **Note:** `harden-runner` is currently `egress-policy: audit` (NOT block) on all 5 CI/release jobs. The block-flip is deferred and needs live audit telemetry.

## 1. Local sanity over the Fake (dev box, ~15 min)

Quick confidence, no real infra. Pick ONE stand-up path: the one-shot compose OR the three local processes. Running both collides on ports 7681/8000.

- [ ] **Stand up the whole Fake stack in one shot (recommended for browser UAT).** UI via nginx, control plane over the Fake provider, stub ttyd, all from compose.
  ```
  docker compose -f docker-compose.e2e.yml up
  ```
  _Pass: Stack boots and serves UI at http://localhost:4173 (nginx), API (Fake) at :8000, stub ttyd at :7681._ (maps: Lane A / LOCAL-1)

- [ ] **Three-process path, process 1: start the stub ttyd server** (verbatim from `ui/playwright.config.ts`). Leave running in its own shell.
  ```
  cd api && python -m tests.e2e.stub_ttyd_server --host 127.0.0.1 --port 7681
  ```
  _Pass: Stub ttyd listening on 127.0.0.1:7681._ (maps: Lane A / LOCAL-2)

- [ ] **Three-process path, process 2: start the control plane over the Fake provider** with SQLite and the stub-ttyd host. Run via Git Bash (POSIX env-var prefix), or translate to `$env:` for PowerShell.
  ```
  cd api && BURROW_COMPUTE=fake BURROW_DB=sqlite BURROW_E2E_TTYD_HOST=127.0.0.1 uv run uvicorn main:app --host 127.0.0.1 --port 8000
  ```
  _Pass: Uvicorn serving the control plane on 127.0.0.1:8000 against the Fake provider (no real Proxmox touched)._ (maps: Lane A / LOCAL-3)

- [ ] **Three-process path, process 3: start the UI dev server** (or build+preview).
  ```
  cd ui && npm run dev
  ```
  _Pass: UI dev server at http://localhost:5173 (or, via `npm run build && npm run preview`, at :4173). Point Claude Code preview here for visual items, Claude in Chrome here for flow items._ (maps: Lane A / LOCAL-4)

- [ ] **Eyeball the app shell and all four themes** (CC-PREVIEW).
  _Pass: Sidebar workspace list with live status, Navbar per-node capacity chips, StatusBar counts/uptime, the New-Workspace modal, and all four themes render to the 02-UI-SPEC._ (maps: UI-01..04 / V5)

- [ ] **Eyeball the activity drawer rendering** (CC-PREVIEW): open a workspace's activity drawer.
  _Pass: Right-side slide-in; four states render (loading shimmer / empty / list / poll-error strip); newest-first order; color-coded badges keyed to real namespaced event types (workspace.\*, terminal.\*, boot.error, reaper.\*); boot.error rows emphasized (2px --err bar + tint + red mono reason); redacted data rendered as-is._ (maps: UI-06 / V1)

- [ ] **Eyeball drawer responsive width** (CC-PREVIEW) at the three breakpoints. **(v1.1 — currently fails; expected to fail today.)**
  _Pass: At 375px the drawer is a full-width sheet; 640-1023px → min(360px,80vw); >=1024px → 360px. Today ActivityDrawer.tsx hardcodes a single min(360px,100vw) → ~15px scrim sliver at phone width (P4-UI1)._ (maps: UI-06 / V2)

- [ ] **Keyboard-focus the drawer trigger, the close ×, and the scroll region; check the focus ring** (CC-PREVIEW). **(v1.1 — currently fails; expected to fail today.)**
  _Pass: Each shows the 2px Burrow accent focus-visible ring (--accent-line). Today no :focus-visible rule in index.css and the `<aside>` sets outline:none → UA-default focus only (P4-UI2)._ (maps: UI-06 / V3)

- [ ] **Scroll a long event list and inspect the scrollbar** (CC-PREVIEW). **(v1.1 — currently fails; expected to fail today.)**
  _Pass: Thin neutral 3px scrollbar per spec. Today no ::-webkit-scrollbar / scrollbar-\* rules → UA default (P4-UI3)._ (maps: UI-06 / V4)

- [ ] **Automate create-workspace journey over the Fake** (CHROME-AUTO): fill the New-Workspace modal and submit.
  _Pass: Workspace appears in the sidebar and walks creating→running (cosmetic boot progress)._ (maps: WS-01, UI-01/UI-03 / A1)

- [ ] **Automate opening the activity drawer on a workspace** (CHROME-AUTO).
  _Pass: Events render newest-first with the correct badges and boot.error emphasis._ (maps: UI-06 / A2)

- [ ] **Automate terminate** (CHROME-AUTO): click terminate (×) and confirm. Audit-fixed regression guard (REGRESS-WS08, commits 25e54bb / bdd72d8).
  _Pass: A DELETE /api/v1/workspaces/{id} fires AND the workspace is gone server-side on the next list fetch (not just removed from the mosaic). The guard test must FAIL if onTerminate reverts to a client-only closePanel._ (maps: WS-08, UI-05 / A3)

- [ ] **Automate tile/split/persist** (CHROME-AUTO): open multiple panels, split H/V, drag, resize, then refresh the page.
  _Pass: On refresh the Mosaic layout reconciles (gone leaves dropped, active retargeted)._ (maps: UI-02, UI-05 / A4)

- [ ] **Automate detach→reconnect** (CHROME-AUTO): close the tab, reopen, re-open the same workspace's terminal.
  _Pass: Terminal reattaches over the stub ttyd._ (maps: UI-05, TERM-06 / A5)

- [ ] **Automate terminal echo + reconnect overlay** (CHROME-AUTO): type into a panel, then drop the connection.
  _Pass: Input echoes over the stub ttyd frames; on connection drop the reconnecting overlay shows and recovers._ (maps: TERM-05/06/07 / A6)

- [ ] **DECIDE stop/start** (CHROME-AUTO): either (a) record that v1 stop/start is intentionally reaper/backend-only, or (b) add a per-workspace stop/start control and drive it over the Fake. Endpoints and `useStopWorkspace`/`useStartWorkspace` hooks exist but no UI invokes them.
  _Pass: If (b): stop → workspace becomes stopped, start → workspace becomes running. If (a): documented that no UI invokes /stop+/start in v1._ (maps: WS-06, WS-07 / A7)

- [ ] **After V2 lands, add a Playwright/Chrome assertion at a 375px viewport** that the drawer width equals the viewport width (and the tablet band). **(v1.1 — depends on V2 landing first.)**
  _Pass: Assertion proves criterion 10 (drawer width == viewport width at 375px, plus tablet band) and guards against silent regression._ (maps: UI-06 / A8)

## 2. One-time Proxmox priming + golden template

Run the scripts strictly in order `00 → (NET) → 10 → 20 → hand-clone → 40` so each gate localizes failure. First replace the `<...>` placeholders in `00-api-user-role.sh`, `10-template-download.sh`, and `20-create-template.sh` (NODE_NAME, POOL, STORAGE, NODE, TMPL VMID, TMPL_STORAGE, ROOTFS_STORAGE, BRIDGE, pinned Ubuntu build string) — `common.sh require_node` refuses to run on an unfilled `<node>` placeholder or the wrong host.

- [ ] **PRIMING STEP 1 — record the static-IP-from-VMID scheme and exclude the worker range from DHCP off-host.**
  ```
  ip link show <bridge>   # confirm the LAN bridge exists; then edit a private copy of cc-worker-config/lxc/host-prime/30-network-notes.md with VMID->octet map, gw, subnet, range; then on the router/pfSense/dnsmasq exclude <subnet>.<pool-start-octet>-<pool-end-octet> from DHCP
  ```
  _Pass: Bridge exists; VMID→IP formula recorded and matches the control plane's computation; the worker IP range is verified excluded from DHCP; template + control-plane addresses are OUTSIDE the worker range._ (maps: ACC-01 / PREP-NET, H13 readiness, ADR-0004)

- [ ] **STEP 0 — Identity & least privilege.** Run the API-user/role/pool/token script as `root@pam` on the template node; capture the printed token secret into the gitignored `.env` immediately (once, unrecoverable).
  ```
  sudo bash cc-worker-config/lxc/host-prime/00-api-user-role.sh
  ```
  _Pass: `pvesh get /access/permissions --token "burrow@pve!burrow=<uuid>"` shows the BurrowProvisioner role at /pool/burrow-workers, /vms/<template-vmid>, /storage/<rootfs>, /nodes/<node> ONLY and NOTHING on out-of-pool VMIDs. PROXMOX_TOKEN_VALUE landed in .env at 0600, never echoed._ (maps: ACC-01 / H1 + H3)

- [ ] **Re-run STEP 0 to confirm idempotency** — choose `reuse` at the token prompt (NOT `rotate`, which deletes the live token).
  ```
  sudo bash cc-worker-config/lxc/host-prime/00-api-user-role.sh   # choose 'reuse' at the token prompt
  ```
  _Pass: Second run reports role 'modify (re-assert privs)', user 'leave as-is', pool 'present', token 'reuse — secret NOT reprinted', ACLs re-granted idempotently. No second token minted, no churn, exit 0._ (maps: ACC-01 / H1 idempotency)

- [ ] **STEP 2a — Download the pinned Ubuntu 24.04 CT template.** Discover the exact build string and pin it in the script first.
  ```
  pveam available --section system | grep ubuntu-24.04-standard   # paste the full filename into TMPL in 10-template-download.sh, then:
  sudo bash cc-worker-config/lxc/host-prime/10-template-download.sh
  ```
  _Pass: Script prints 'STEP 2a complete. Template available on <tmpl-storage>: ubuntu-24.04-standard_<ver>_amd64.tar.zst'. Re-running skips the download. It refuses to run while TMPL still contains the <ver> placeholder._ (maps: ACC-01 / H2)

- [ ] **STEP 2b — Build the golden worker template** (unprivileged + nesting CT on THIN rootfs, push the worker-template payload, run the provisioner inside, convert with `pct template`).
  ```
  sudo bash cc-worker-config/lxc/host-prime/20-create-template.sh
  ```
  _Pass: Script ends 'Golden template ready at VMID <template-vmid>.' Inside, provision-template.sh installed Ubuntu 24.04 + Node 22 (NodeSource setup_22.x) + pinned @anthropic-ai/claude-code@2.1.170 + ttyd + jq, baked rtk/gsd, installed /opt/burrow-boot.sh, and ran `systemctl enable burrow-worker.service`. CT is now a template._ (maps: ACC-01 / H2 + H16 substrate)

- [ ] **PRIMING STEP 2 manual gate — hand-clone the template once, start it, confirm ttyd answers on the LAN and `claude` launches, then destroy the test clone.**
  ```
  pct clone <template-vmid> <test-vmid> --full
  pct set <test-vmid> -net0 name=eth0,bridge=<bridge>,ip=<subnet>.<oct>/<prefix>,gw=<gw>
  pct set <test-vmid> -hostname burrow-<test-vmid>
  pct start <test-vmid>
  curl http://<subnet>.<oct>:7681/
  pct destroy <test-vmid> --force
  ```
  _Pass: `curl http://<worker-ip>:7681/` returns ttyd's HTML (bound to 0.0.0.0, reachable over the LAN — not lo); a `claude` session is launchable in that ttyd; test clone destroys cleanly and the VMID is freed._ (maps: ACC-01 / H4 + H5 substrate)

- [ ] **STEP 3 — Provision the control-plane box** (burrow service account, /opt/burrow + /data, the uv venv from the frozen lockfile, the nginx site validated with `nginx -t`, burrow.service, assembled .env). Paste the STEP-0 token at the hidden prompt.
  ```
  sudo bash cc-worker-config/lxc/host-prime/40-control-plane.sh   # at the hidden prompt, paste PROXMOX_TOKEN_VALUE from STEP 0
  ```
  _Pass: `curl http://127.0.0.1:8000/api/v1/health` returns db: ok AND compute: ok. /opt/burrow/.env is 0600 burrow:burrow with the token never echoed. `nginx -t` passed before reload; burrow.service is enabled and running._ (maps: ACC-01 / H1 control-plane half + SETUP-04 health gate)

## 3. Dev-homelab smoke (real Proxmox) — ACC-01

Lead with the H9 five-step gate, then reaper/idle/capacity, then boot/credential/plugin, then the v1.2 real multi-node auto-select.

### The H9 five-step gate ("the looks-done-but-isn't gate")

- [ ] **H9 step 1 of 5 — CREATE.** From a LAN browser pointed at the control plane (nginx), open the New-Workspace modal, pick a small repo + branch, submit.
  ```
  Browser: http://<control-plane-host>/  -> 'New Workspace' -> select repo + branch -> Create.   API equivalent: POST /api/v1/workspaces {"repo":"...","branch":"..."}
  ```
  _Pass: A worker CT is --full cloned from the template; the clone + start UPIDs block to OK; net0 carries the VMID-derived static IP; the workspace row transitions creating → running. The activity drawer shows workspace.\* events with no boot.error._ (maps: ACC-03 / H6)

- [ ] **H9 step 2 of 5 — LIVE TERMINAL.** Open the workspace's terminal panel and confirm an interactive, resizable Claude Code session.
  ```
  Browser: click the workspace tile -> terminal panel. Type a command; resize/split the panel.
  ```
  _Pass: The panel shows a live interactive `claude` session over the real ttyd `tty` subprotocol; input echoes; the TUI REFLOWS to the panel size (not stuck 80x24). Saga step 6 (_wait_ttyd) succeeded against :7681 and the workspace is `running`._ (maps: ACC-03 / H7 + H10 + H12)

- [ ] **H9 step 3 of 5 — STOP.** Stop the workspace; the LXC stops but its disk is preserved.
  ```
  Browser: workspace stop control.   API equivalent: POST /api/v1/workspaces/{id}/stop
  ```
  _Pass: Status → `stopped`; the LXC is stopped (pct status shows stopped); the rootfs/disk is preserved (not destroyed)._ (maps: ACC-03 / WS-06; confirm whether a UI control exists or drive via API — Lane-A A7 note)

- [ ] **H9 step 4 of 5 — START.** Start the stopped workspace; the terminal reconnects to the SAME session.
  ```
  Browser: workspace start control, then re-open the terminal.   API equivalent: POST /api/v1/workspaces/{id}/start
  ```
  _Pass: Status → `running`; the terminal reconnects to the SAME PTY/Claude session (no fresh process); the start UPID blocked to OK._ (maps: ACC-03 / WS-07 + H11 + H5)

- [ ] **H9 step 5 of 5 — DESTROY.** Destroy the workspace; the LXC is gone, the VMID freed, the row soft-deleted.
  ```
  Browser: terminate (x) -> confirm.   API equivalent: DELETE /api/v1/workspaces/{id}
  ```
  _Pass: The LXC no longer exists on the node; the VMID is freed (re-allocatable); the workspace row is soft-deleted (deletedAt set). After all five: no orphan CTs remain and the VMID pool is clean._ (maps: ACC-03 / H9 headline acceptance)

### Saga compensation, reaper, idle, capacity

- [ ] **H8 — Compensation: force a mid-saga failure on a create and confirm the partial clone is torn down.**
  ```
  Trigger a create, then induce a saga failure (e.g. make ttyd health unreachable for that worker, or temporarily point net0 off-LAN) so _wait_ttyd / a saga step fails.
  ```
  _Pass: The partial CT is destroyed, its VMID freed, the workspace row lands `error`, and NO orphan CT remains on the node._ (maps: ACC-03 / H8, WS-03)

- [ ] **H17 — Reaper destroys an OFF-NODE orphan.** Inject an orphan CT into the burrow-workers pool on a NON-default node, then let one reconcile pass run.
  ```
  On a non-default node: pct clone <template-vmid> <orphan-vmid> --full ; pvesh set /pools/burrow-workers -vms <orphan-vmid> ; pct start <orphan-vmid>   (no matching workspace row). Also create one OUT-of-pool CT as a control. Wait for the reaper reconcile interval.
  ```
  _Pass: One reconcile pass destroys the orphan ON ITS REAL NODE and frees the VMID; the out-of-pool CT is UNTOUCHED; `reaper.destroyed` is logged only on a real destroy._ (maps: ACC-03 / H17, CR-01 fix)

- [ ] **H18 — Idle auto-stop over the real window.** Boot a workspace, disconnect the terminal, let wall-clock exceed `idle_window_s`.
  ```
  Create + open a workspace, close the terminal tab, wait > idle_window_s (per .env). Separately: reconnect within the window on another workspace to prove the negative.
  ```
  _Pass: After the window elapses the workspace is STOPPED (not destroyed) and emits workspace.stopped with reason: idle. A reconnect INSIDE the window does NOT trip the auto-stop._ (maps: ACC-03 / H18, CAP-02)

- [ ] **H19 — Capacity refusal under real concurrency.** Fire concurrent creates near the node-RAM threshold against real Proxmox metrics.
  ```
  Fire N concurrent POST /api/v1/workspaces near CAPACITY_THRESHOLD=0.80 of node RAM (e.g. a loop / parallel curl) so the sum would overcommit.
  ```
  _Pass: No overcommit: creates beyond the threshold are REFUSED; the atomic check+reserve lock holds under concurrency (real node-RAM metrics, not the Fake)._ (maps: ACC-03 / H19, CAP-01/CAP-02)

### Boot, credential, plugin internals

- [ ] **H13 — Confirm resolve_vmid hostname parse against the recorded VMID↔static-IP map; a wrong VMID must 404 safely.**
  ```
  On a live worker: hostname -s   (expect burrow-<vmid>; ${host##*-} must yield <vmid>). Negative: curl -fsS http://<control-plane>/api/v1/internal/bootconfig/<bad-vmid>  (expect HTTP 404).
  ```
  _Pass: `${host##*-}` yields the VMID matching the 30-network-notes.md / ADR-0004 map; a non-existent/out-of-pool VMID returns 404 (fails closed, no orphan boot)._ (maps: ACC-03 / H13, WORK-02)

- [ ] **H14/H15 — Confirm the boot-time git credential convention and config-repo reachability.**
  ```
  Inspect a real worker boot log (journalctl -u burrow-worker.service) and confirm both the config repo (cc-worker-config) and the project repo cloned; verify the credential the bootconfig returned (.data.gitCredential) is accepted by your provider.
  ```
  _Pass: Both clones succeed with the project-scoped bootconfig credential; the credential never appears on disk, on a command line, in /etc/burrow/worker.env, or in any log; CLAUDE.md was copied to the worker home. If your mechanism is a deploy-key / GitLab job token rather than a GitHub App token / fine-grained PAT, the GIT_ASKPASS Username branch must be adjusted from `x-access-token`._ (maps: ACC-03 / H14 + H15, WORK-02)

- [ ] **H16 — Confirm the enabledPlugins on-disk shape and that the pulled claude-plugin loads on claude-code@2.1.170.**
  ```
  On a live worker after boot: jq '.enabledPlugins' ~/.claude/settings.json   then  claude plugin list   (or claude --debug).
  ```
  _Pass: ~/.claude/settings.json has enabledPlugins[<name>]=true for each pulled claude-plugin and `claude plugin list` shows the plugin loaded; the manifest passed the fail-closed jq structural gate at boot._ (maps: ACC-03 / H16, WORK-05)

### v1.2 real multi-node + real stop/start

- [ ] **ACC1-1 — Real multi-node auto node-selection smoke.** With the control plane pointed at a real cluster (>=2 primed nodes of differing RAM load) and `settings.worker_nodes` listing them, create a workspace with NO node chosen (modal on 'Auto (least-loaded)').
  ```
  # Git Bash, against the live LAN control plane (BURROW_COMPUTE=proxmox):
  curl -s -X POST http://<control-plane-lan-ip>:8000/api/v1/workspaces -H 'content-type: application/json' -d '{"name":"acc01-auto","projectRepo":"<git-url>","branch":"main"}' | tee /tmp/acc01.json
  # then read back which node it actually booted on:
  curl -s http://<control-plane-lan-ip>:8000/api/v1/nodes
  curl -s http://<control-plane-lan-ip>:8000/api/v1/workspaces | grep -i node
  ```
  _Pass: POST returns 201/200 with node:null in request yet the created workspace's resolved node == the least-loaded node from GET /api/v1/nodes whose memoryUsedFraction <= capacityThreshold (tie broken by node name asc). A second create when only one node fits still picks that node; when NO node fits, the create is refused with the capacity_exceeded envelope (HTTP 409) and NO orphan row/CT is left. Worker boots to a live Claude Code ttyd terminal in the browser._ (maps: ACC-01 / WSX-01 — the one piece CI cannot prove over the Fake)

- [ ] **ACC1-2 — Real stop/start UI controls against real infra.** In the browser UI, click the Stop header icon on a running real workspace, then Start.
  ```
  # Browser UI served from the LAN control plane; no shell. Watch the event drawer + state badge.
  # Optional truth-check from Git Bash:
  curl -s http://<control-plane-lan-ip>:8000/api/v1/workspaces/<id>/events | tail
  ```
  _Pass: Stop fires immediately (no confirm), button shows aria-busy spinner then the panel swaps to the stopped placeholder; the live ttyd terminal disconnects on running→stopped. Start re-runs the boot and the real Claude terminal reconnects on stopped→running. The drawer logs workspace.stopped with NO reason (explicit-stop, distinct from reason: idle). State machine rejects any illegal action._ (maps: ACC-01 / WS-06 / WS-07 — new in v1.1)

### v1.1/v1.2 visual eyeball on a real device (no Proxmox)

These are mostly CI-proven (live Playwright + vitest CSS-source asserts); the only human delta is an eyeball on a real device. Serve the built UI: `npm --prefix ui run build && npm --prefix ui run preview -- --host`, then open `http://<dev-box-lan-ip>:4173` on a handset <=375px CSS width.

- [ ] **VIS-1 — On a real phone (<=375px), open the per-workspace activity drawer.**
  _Pass: At <=375px the drawer fills the full viewport width (100vw via the --w-drawer override under @media (max-width:375px)); at ~360px still full-bleed; above 375px it is the min(360px,100vw) panel. No horizontal scroll, content legible._ (maps: UI-09)

- [ ] **VIS-2 — On a real device, tab/keyboard-focus through controls across all four themes.**
  _Pass: Every :focus-visible control shows a 2px solid --accent-line outline with 2px offset, visible and consistent across all four themes; no control is left without a visible focus indicator._ (maps: UI-10)

- [ ] **VIS-3 — On a real device (Chromium + Firefox), scroll a long list and confirm the custom Burrow scrollbar.**
  _Pass: Webkit browsers show the 8px custom thumb (Burrow token colors, hover lightens to --text-muted) on a transparent track; Firefox shows scrollbar-width:thin with matching scrollbar-color. No default OS scrollbar leaks through._ (maps: UI-11)

- [ ] **Flip the deferred v1.0 UAT homelab items to passed.**
  ```
  Edit .planning/milestones/v1.0-phases/03-reproducible-workers/03-HUMAN-UAT.md and 04-hardening-release/04-HUMAN-UAT.md: mark items done and set status: passed; tick H1-H19 in docs/v1.0-uat-checklist.md Lane D.
  ```
  _Pass: 03-HUMAN-UAT.md items 1-5 done, 04-HUMAN-UAT.md items 1-3 done (items 4-5 are CI/CD lanes B/C, not this homelab lane), Lane D H1-H19 checked, and 03/04-VERIFICATION.md status flipped to passed._ (maps: ACC-03 / CLOSE bookkeeping)

## 4. First live CI run — ACC-02 (CI half)

Open a PR (not a direct push) so every job runs: `ci.yml` triggers on `pull_request` AND `push: branches:[main]`, but `pr-title` only runs on `pull_request`. The real `ci.yml` has exactly three jobs: `static-gates`, `pr-title`, `build-scan`. The Windows dev host CANNOT run these gates (no Docker/Buildx/Trivy/shellcheck) — the ubuntu-latest runner is the sole authority for C1/C3.

- [ ] **Create a throwaway PR branch off main** so `ci.yml` fires on `pull_request`.
  ```
  git checkout -b chore/first-ci-run && git commit --allow-empty -m "chore: trigger first live CI run" && git push -u origin chore/first-ci-run
  ```
  _Pass: Branch pushed; `gh pr create` succeeds and returns a PR URL._ (maps: ACC-02 / CI-1)

- [ ] **Open the PR with a Conventional-Commit-valid title** (validated by the `pr-title` job via amannn/action-semantic-pull-request).
  ```
  gh pr create --base main --head chore/first-ci-run --title "chore: first live CI run" --body "Exercise ci.yml on a live runner (ACC-02)."
  ```
  _Pass: PR is created; the `pr-title` check appears and goes green because the title 'chore: ...' is a valid Conventional Commit. An invalid title fails the job by design._ (maps: ACC-02 / CI-2)

- [ ] **Watch the run and confirm `static-gates` goes green** (this single job runs all Tier-0 gates + boot/manifest/reconciler pytest tiers + shellcheck — C3 + C4 + C5 combined).
  ```
  gh pr checks --watch
  ```
  _Pass: static-gates = success. Internally every step green: api ruff check, api ruff format --check, api mypy . --strict, api uv lock --check, ui npx tsc --noEmit, ui npx biome ci, the two pytest steps, shellcheck, and reuse lint. A red step fails the whole job (fail-closed DAG)._ (maps: C3,C4,C5 / CI-3)

- [ ] **Within static-gates, confirm the shellcheck step lints both worker boot scripts** (first real shellcheck run; unavailable on the Windows host).
  ```
  # step: `shellcheck cc-worker-config/lxc/worker-template/burrow-boot.sh cc-worker-config/lxc/worker-template/provision-template.sh`
  ```
  _Pass: shellcheck step exits 0 (no warnings escalated to errors) on both burrow-boot.sh and provision-template.sh._ (maps: C3 / CI-4)

- [ ] **Within static-gates, confirm the boot + manifest pytest tier goes green** (hermetic: fake control plane + file:// bare repos + stub ttyd on PATH; no real Proxmox).
  ```
  # step: `uv run pytest tests/boot tests/integration/test_manifest_schema.py -q` (working-directory: api)
  ```
  _Pass: pytest step for tests/boot + test_manifest_schema.py exits 0._ (maps: C3 / CI-5)

- [ ] **Within static-gates, confirm the Phase-4 hermetic runtime tier (reconciler + capacity-race + lifespan) goes green** over the Fake provider with injected clock.
  ```
  # step: `uv run pytest tests/unit/test_reconciler.py tests/integration/test_capacity_race.py tests/integration/test_lifespan.py -q` (working-directory: api)
  ```
  _Pass: This pytest step exits 0 — reaper, idle auto-stop, capacity-race and lifespan logic green with no real Proxmox/real time._ (maps: C3 / CI-6)

- [ ] **Within static-gates, confirm the reuse (SPDX) gate runs WITH the charset-normalizer encoding module and reports the full pass.**
  ```
  # step: `uvx --with charset-normalizer reuse lint`
  ```
  _Pass: reuse lint step exits 0 with the summary reporting all files SPDX-compliant (the live count is whatever the current tree holds — the gate is exit 0, not a fixed number). No NoEncodingModuleError._ (maps: C4 / CI-7)

- [ ] **LANE-E reconcile — confirm the SPDX-comment-before-frontmatter convention no longer breaks gsd-sdk phase-plan-index reading waves/deps as defaults** (tooling fix, not a ci.yml job).
  ```
  # Inspect a plan file with SPDX-before-frontmatter and run the gsd-sdk phase-plan-index parser; confirm waves/deps parse correctly (not silently defaulted).
  ```
  _Pass: phase-plan-index reads the real waves/deps from the YAML frontmatter even though an SPDX comment precedes it (currently worked around per PROJECT Active #3 / CI-SPDX-PARSER)._ (maps: C5 / CI-8)

- [ ] **Confirm the build-scan matrix job runs for BOTH images and the Trivy GATE behaves correctly** (C1 — first real Docker/Buildx + Trivy run, impossible on the Windows host).
  ```
  # job build-scan, matrix: burrow-api (Dockerfile.api) + burrow-ui (Dockerfile.ui); needs: [static-gates]
  ```
  _Pass: Both matrix legs build the image with Buildx push:false load:true (tag <image>:scan), then Trivy run 1 (gate) with severity HIGH,CRITICAL exit-code 1 ignore-unfixed false. Green == build succeeds AND zero HIGH/CRITICAL findings. A HIGH/CRITICAL fails that leg by design (fail-closed). fail-fast:false so api and ui report independently._ (maps: C1 / CI-9)

- [ ] **Confirm the Trivy SARIF (run 2, full report) uploads to GitHub code scanning for each image regardless of the gate result.**
  ```
  # steps: Trivy scan (SARIF, if: always()) -> github/codeql-action/upload-sarif (if: always(), category trivy-<image>)
  ```
  _Pass: trivy-burrow-api.sarif and trivy-burrow-ui.sarif appear under Security → Code scanning with categories trivy-burrow-api / trivy-burrow-ui. Upload requires security-events: write (set on the job)._ (maps: C1 / CI-10)

- [ ] **NOTE THE GAP — decide on the missing e2e/Playwright job.** Lane B C2 and ci-cd-and-testing.md §3.2 describe an e2e job in the DAG, but `ci.yml` has NO e2e job (only a doc-comment reference to docker-compose.e2e.yml).
  ```
  # Verified: ci.yml jobs are static-gates, pr-title, build-scan only. grep "playwright|e2e" .github/workflows/ci.yml -> only line 5 comment.
  ```
  _Pass (decision, not a check): C2 is explicitly recorded as deferred, OR an e2e job (compose stack from docker-compose.e2e.yml + `npx playwright install chromium` + the create→echo→split→detach→reconnect→terminate journey) is added and goes green._ (maps: C2 / CI-11)

- [ ] **Accept the first-CI run and squash-merge (or close) the PR** once all required checks are green.
  ```
  gh pr checks chore/first-ci-run
  ```
  _Pass: All required checks (static-gates, pr-title, build-scan x2 [+ any code-scanning required check]) report success. NOTE: codeql.yml/dependency-review.yml/scorecard.yml are spec'd in §8 but NOT committed; if branch protection lists them as required, they must be added or the rule relaxed._ (maps: ACC-02 / CI-12)

- [ ] **Capture the harden-runner egress audit output from this first run, for every job,** to seed the future allowlist (audit mode now; flip to block later).
  ```
  # In each job's log, expand the 'Harden the runner (audit egress)' / harden-runner step, or open the run's harden-runner insights link to read the observed outbound endpoints.
  ```
  _Pass: You have a concrete list of egress endpoints (e.g. ghcr.io, registry hosts, pypi/npm, GitHub API, action download hosts) observed in audit mode, recorded for a later egress-policy: block allowlist. No egress is blocked on this run._ (maps: ACC-02 / CI-13)

- [ ] **harden-runner egress block-flip (deferred ACC-02).** After the first live runs of `ci.yml`, `release-please.yml`, and `release.yml`, collect the observed egress endpoints PER JOB and turn them into an allowed-endpoints allowlist, then flip `egress-policy: audit → block` on all 5 jobs and re-run. Depends on ACC2-1/ACC2-2 (section 5) having run first.
  ```
  gh run view <run-id> --repo BraveBearStudios/burrow --web   # open StepSecurity 'Insights' for the harden-runner step, copy discovered endpoints
  # edit ci.yml (3 jobs) + release-please.yml (1) + release.yml (1): egress-policy: block + allowed-endpoints
  gh pr create --base main --head harden/egress-block --title 'ci: flip harden-runner egress to block'
  gh run watch --exit-status
  ```
  _Pass: Each harden-runner step has an explicit allowed-endpoints list and egress-policy: block; a re-run of every workflow stays green (publish still signs + attests, build-scan still pulls/scans). build-scan (ci.yml) and publish (release.yml) need the widest allowlist (Docker, Trivy DB, GHCR, plus Fulcio/Rekor/TUF for cosign keyless)._ (maps: ACC-02 / RELX-02 / CD-9, ACC2-3)

## 5. Real release + supply-chain verify — ACC-02 (release) + ACC-03

Run `git fetch --tags origin` first. The release-please manifest is seeded `1.1.0` (bootstrap-sha = v1.1 commit `9bccec85`), so the first release PR proposes **v1.2.0**. The two workflows chain ONLY via the git tag. ALWAYS verify by immutable digest (`@sha256:...`), never a floating tag. GHCR lowercases the owner: images are `ghcr.io/bravebearstudios/burrow-api` and `...burrow-ui`.

- [ ] **CD-1 — Land Conventional-Commit work on main and confirm release-please opened/updated the release PR proposing v1.2.0.**
  ```
  gh pr list --repo BraveBearStudios/burrow --label 'autorelease: pending' --state open
  ```
  _Pass: A release-please PR exists, bumps .release-please-manifest.json to 1.2.0, regenerates CHANGELOG.md, and (release-type: simple) adds version.txt=1.2.0. The release-please workflow run is green._ (maps: ACC-02 / CD-1)

- [ ] **CD-2 — Review and squash-merge the release-please PR** (the PR title must be a valid Conventional Commit). Merging creates the v1.2.0 tag and the GitHub Release.
  ```
  gh pr merge <release-pr-number> --repo BraveBearStudios/burrow --squash
  ```
  _Pass: Tag v1.2.0 is created on the merge commit and a GitHub Release v1.2.0 is published (gh release view v1.2.0 resolves)._ (maps: ACC-02 / CD-2)

- [ ] **CD-3 — Confirm release.yml actually fired on the new tag** (GITHUB_TOKEN retrigger trap: a tag pushed by GITHUB_TOKEN may not auto-trigger release.yml).
  ```
  gh run list --repo BraveBearStudios/burrow --workflow release.yml --branch v1.2.0
  ```
  _Pass: A 'release' workflow run exists for tag v1.2.0 with both matrix legs (publish burrow-api, publish burrow-ui) green. If absent: re-run via `gh workflow run release.yml --ref v1.2.0` or push a fresh tag under a GitHub App token._ (maps: ACC-03 / CD-3)

- [ ] **CD-4 — Confirm both images were pushed to GHCR by digest with the §2.4 tag set** (X.Y.Z, X.Y, latest, sha-<short>). Capture each immutable digest.
  ```
  docker buildx imagetools inspect ghcr.io/bravebearstudios/burrow-api:1.2.0 --format '{{.Manifest.Digest}}'   # repeat for burrow-ui
  ```
  _Pass: ghcr.io/bravebearstudios/burrow-api and ghcr.io/bravebearstudios/burrow-ui each resolve to a sha256 digest and carry tags 1.2.0, 1.2, latest, sha-<short>._ (maps: ACC-03 / CD-4)

- [ ] **CD-5 — VERIFY the keyless cosign signature on burrow-api by DIGEST** (Sigstore + GitHub OIDC).
  ```
  cosign verify --certificate-identity-regexp 'https://github.com/BraveBearStudios/burrow/.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com ghcr.io/bravebearstudios/burrow-api@sha256:<api-digest>
  ```
  _Pass: cosign reports a verified signature whose Fulcio cert identity matches the regexp and issuer; exit 0. (Signature recorded in Rekor; no long-lived key.)_ (maps: ACC-03 / CD-5)

- [ ] **CD-6 — VERIFY the SLSA build-provenance attestation on burrow-api by DIGEST.**
  ```
  gh attestation verify oci://ghcr.io/bravebearstudios/burrow-api@sha256:<api-digest> --owner BraveBearStudios
  ```
  _Pass: gh attestation verify reports the SLSA provenance attestation as verified for the digest under owner BraveBearStudios; exit 0._ (maps: ACC-03 / CD-6)

- [ ] **CD-7 — Confirm BOTH SBOMs (SPDX-json AND CycloneDX-json) were generated for burrow-api.**
  ```
  gh run view <release-run-id> --repo BraveBearStudios/burrow --log | grep -E 'sbom-burrow-api\.(spdx|cyclonedx)\.json'
  ```
  _Pass: Both sbom-burrow-api.spdx.json and sbom-burrow-api.cyclonedx.json were produced against the pushed digest. D1 is unmet if either is missing._ (maps: ACC-03 / CD-7)

- [ ] **CD-8 — Repeat the digest capture + cosign verify + attestation verify + dual-SBOM check for burrow-ui** (the matrix is independent; a green run can still leave one image unverified).
  ```
  cosign verify --certificate-identity-regexp 'https://github.com/BraveBearStudios/burrow/.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com ghcr.io/bravebearstudios/burrow-ui@sha256:<ui-digest> && gh attestation verify oci://ghcr.io/bravebearstudios/burrow-ui@sha256:<ui-digest> --owner BraveBearStudios
  ```
  _Pass: burrow-ui signature verifies (exit 0), provenance verifies (exit 0), and both sbom-burrow-ui.spdx.json + sbom-burrow-ui.cyclonedx.json exist. Closes D1: both images published by digest, each keyless-signed, each with SLSA provenance and both SBOM formats._ (maps: ACC-03 / CD-8)

- [ ] **CD-10 — Confirm SHA-pin posture is intact across all release workflows** (every third-party action reference is a full 40-hex commit SHA; the trailing `# vX.Y.Z` is only a label).
  ```
  rg -n 'uses:.*@(?![0-9a-f]{40})' .github/workflows/release.yml .github/workflows/release-please.yml .github/workflows/ci.yml
  ```
  _Pass: Zero matches (no unpinned / tag-pinned references). Spot-confirm harden-runner@9af89fc7..., checkout@34e11487..., build-push-action@f9f3042f..., cosign-installer@d7543c93..., attest-build-provenance@977bb373..., release-please-action@5c625bfb... all carry 40-hex SHAs._ (maps: ACC-03 / CD-10)

- [ ] **DEBT-1 — Close-out: flip the carried acceptance-debt line + the ★ on-runner/homelab markers in PROJECT.md to passed.**
  ```
  # edit .planning/PROJECT.md: tick the Active line and mark the ★ markers accepted; commit per approval gate.
  ```
  _Pass: PROJECT.md Active line 'Run and record the dev-homelab smoke + first CI release' is checked, and the ★ markers on the v1.2 Phase 8/9 + v1.0 CI/CD Validated lines are recorded as accepted with run links (ci.yml/release-please.yml/release.yml run URLs + the v1.2.0 Release URL). NOTE: v1.1/v1.2 shipped NO per-phase HUMAN-UAT files — there is nothing else to flip for these milestones._ (maps: ACC-01/02/03 / DEBT-1)

## Gotchas

- **Windows orphaned processes:** The taskkill / kill-port-8000 / delete-burrow-e2e.db cleanup is NOT in the v1.0 UAT checklist; the only "port 8000" reference there is the LOCAL-3 uvicorn command itself. The `.continue-here.md` anti-pattern table is the source: before any local `playwright test`, `taskkill //F //IM python.exe` + `rm -f api/burrow-e2e.db*`, then verify `netstat -ano | grep :8000` is empty.
- **POSIX vs PowerShell env-vars:** The `VAR=val ... command` prefix in section 1 (and the LOCAL-3 control-plane command) is POSIX/bash, not PowerShell. On the Windows dev box run it via Git Bash, or translate to `$env:` assignments. Run all `gh` + `git` from Git Bash (PowerShell quoting mangles JSON `-d` payloads and the cosign `--certificate-identity-regexp` args).
- **STATIC-IP-FROM-VMID:** Unprivileged LXC has no guest agent, so Burrow COMPUTES each worker's IP from its VMID (deterministic VMID→octet map in 30-network-notes.md / ADR-0004). The worker hostname MUST be `burrow-<vmid>` because `resolve_vmid` in burrow-boot.sh parses `${host##*-}`; a non-integer suffix ERR-traps the boot. A VMID collision IS an IP collision.
- **DHCP exclusion is load-bearing and off-host:** The worker IP range must be reserved OUT of the LAN DHCP pool on the router/pfSense/dnsmasq. There is NO Proxmox-side enforcement. Keep the golden template AND the control plane OUTSIDE the worker range so destroying a worker can never collide with persistent infra.
- **PULL-AT-BOOT, never injected:** Boot config is fetched at boot from `GET /api/v1/internal/bootconfig/<vmid>` (ADR-0002), not via cloud-init/pct push. No secret is ever written to `/etc/burrow/worker.env`. burrow-boot.sh bounded-retries (~5 attempts, capped backoff) then fails non-zero; a 404 (out-of-pool / no workspace) fails closed via `curl -f`. Only `type==claude-plugin` manifest entries are pulled fresh; binary/npm-global are baked into the template.
- **TTYD LAN bind + persistence:** burrow-boot.sh execs `ttyd --port 7681 --writable --interface 0.0.0.0 ...` (NOT lo, SC-9/ADR-0007) and PERSISTENT with NO `--once` (SC-8/ADR-0006). Closing a tab or a stop/start cycle DETACHES, never terminates the live session. Destroy is the only kill path. The TUI must reflow to the panel size (not stuck 80x24).
- **Credential hygiene (three places):** (1) The Proxmox privsep token secret prints ONCE in 00-api-user-role.sh and is unrecoverable; a second `token add` mints a SECOND token and never reprints the first, hence the reuse/rotate prompt; the .env write is REFUSED unless `git check-ignore .env` passes (00) / unless the file is outside any git work-tree, 0600, root-owned (40). (2) Both scripts read the token via `read -rsp` (silent), wrap with `set +x`, use printf (never echo), unset after. (3) The boot-time git credential lives ONLY in a subshell-local `GIT_ASKPASS_TOKEN` via an in-memory helper, never in the clone URL / on a command line / on disk / in worker.env; `GIT_TERMINAL_PROMPT=0` + empty `credential.helper=` make a bad credential fail fast under systemd; unset the instant clones finish; there is NO `set -x` anywhere and the ERR trap redacts `$BASH_COMMAND` as a backstop.
- **Privsep token scope:** Under privsep the token's effective rights are the INTERSECTION of user and token ACLs, so 00-api-user-role.sh grants the BurrowProvisioner role to BOTH the user and the token. The authoritative check is `pvesh get /access/permissions --token "burrow@pve!burrow=<uuid>"` (the `--token` form), which catches the "granted user but not token" mistake. Role is EXACTLY 9 privileges. A 403 on 'set network' means SDN enforcement is on — additionally grant `SDN.Use` on the bridge/vNet (commented block in the script).
- **Thin storage + unprivileged/nesting baked once:** The golden template MUST live on thin storage because template-marked CTs default clones to LINKED while Burrow clones `--full` at runtime; thin keeps `--full` cheap. `unprivileged=1` + `nesting=1` are set once at template-create and inherited by every clone. The pinned chain (Ubuntu 24.04 build string, NodeSource setup_22.x, `@anthropic-ai/claude-code@2.1.170`) is reproducibility-critical.
- **Each gate localizes failure:** Run 00 → (NET) → 10 → 20 → hand-clone → 40 strictly in order. `/api/v1/health` returning `compute: ok` proves token+ACL auth end-to-end BEFORE the H9 smoke; the hand-clone proves ttyd LAN bind + claude launch BEFORE wiring the control plane. STEP-0 re-run must use `reuse` (not `rotate`) to preserve idempotency.
- **ci.yml has NO e2e/Playwright job** despite Lane B C2 and ci-cd §3.2 describing one (only the line-5 doc comment). The real `ci.yml` has exactly three jobs: `static-gates`, `pr-title` (PR-only), `build-scan`. `codeql.yml`/`dependency-review.yml`/`scorecard.yml`/`dependabot.yml`/`CODEOWNERS` are listed in §8 but NOT committed; if branch protection marks them required, the first PR is blocked until they are added or the rule relaxed.
- **build-scan Trivy gate uses `ignore-unfixed:false`,** so an unfixable HIGH/CRITICAL in a base image (`python:3.12-slim` / `nginx:1.27-alpine`) fails the build with no waiver path in the workflow even if Burrow code is clean. The build-scan SARIF upload needs code scanning enabled (and `actions: read` on a private repo).
- **GITHUB_TOKEN tag-retrigger trap (Open Q1):** release-please tags the release using the run's GITHUB_TOKEN; GitHub suppresses workflow events raised by GITHUB_TOKEN, so the new `v*` tag MAY NOT auto-fire release.yml. Confirm release.yml ran (CD-3); if not, re-run it on the tag or push a fresh tag under a scoped GitHub App token.
- **Cosign keyless OIDC + always verify by digest:** The `--certificate-identity-regexp` uses the case-sensitive GitHub URL `https://github.com/BraveBearStudios/burrow/.*` while the image ref path is lowercase (`ghcr.io/bravebearstudios/...`). Use the immutable `@sha256:` digest, not a floating tag, in every verify command — a tag verify can pass against a different artifact. Signing on the runner used `cosign sign --yes` (COSIGN_YES=true), no `--key`.
- **Two SBOMs per image are REQUIRED** (SPDX-json AND CycloneDX-json), generated by `anchore/sbom-action` in two separate steps. The publish job declares EXACTLY four permissions: `contents:read`, `packages:write`, `id-token:write`, `attestations:write` — a missing scope fails keyless signing with an opaque OIDC error; check this set first rather than widening others. The matrix is `fail-fast: false`, so verify BOTH digests independently.
- **harden-runner block-flip cannot be done blind:** the allowlist must be derived from the real audit insights produced by the FIRST live runs (CI section 4 + this release). All 5 jobs are confirmed `egress-policy: audit` this session. build-scan and publish need the widest allowlist (Docker layer pulls, Trivy DB, GHCR, Fulcio/Rekor/TUF). Cannot be discovered on the Windows dev box.
- **No prior live run despite tags:** Tags v1.0/v1.1/v1.2 exist on origin (manual milestone cuts) but are NOT fetched locally; `gh release list` is empty and no GHCR image exists. Do not assume a prior live CI/CD run happened just because tags exist. Any doc claiming the release/publish path is "proven" means YAML/JSON parse + SHA-pin regex only.

**Order of operations:** 1 → 2 → 3 (ACC-01) → 4 (ACC-02) → 5 (ACC-03).
</content>
