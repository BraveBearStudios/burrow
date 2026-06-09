<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Pitfalls Research

**Domain:** Proxmox LXC orchestration + browser terminal multiplexing (ttyd/xterm.js) + ephemeral Claude Code worker lifecycle
**Researched:** 2026-06-09
**Confidence:** HIGH on Proxmox task/VMID semantics, ttyd protocol, WebSocket proxy bridge, and xterm.js lifecycle (verified against official docs, proxmoxer docs, ttyd source/issues, FastAPI discussions). MEDIUM on a few cloud-init/cleanup specifics that depend on your Proxmox version and storage backend.

> Domain note: several pitfalls below contradict code in `docs/tech-spec.md`. The spec is explicitly a working draft; these are the places where implementing it literally produces a broken or racy system. Each is tied to the exact spec section and the phase that should own the fix.

---

## Critical Pitfalls

### Pitfall 1: Treating Proxmox clone/start/destroy as synchronous instead of polling the returned task (UPID)

**What goes wrong:**
Every mutating Proxmox API call (clone, start, stop, destroy, config set) returns immediately with a **UPID** (a task id) while the work continues asynchronously on the node. The spec's `createWorkspace` (tech-spec §6.2) calls `cloneLxc(...)` then immediately `setCloudInitUserdata(...)` then `startLxc(...)`. On real hardware the clone is still copying the disk when `startLxc` fires, so you get `CT is locked (disk-move/create)`, or you start a half-cloned container, or the config write lands on a container that does not fully exist yet. This is the single most common failure for first-time Proxmox automation.

**Why it happens:**
The synchronous-looking method signatures (`cloneLxc -> dict`) invite you to assume completion on return. The HTTP 200 means "task accepted," not "task done." Clones of a 30 GB disk (template is 30 GB per §9.1) take seconds to minutes depending on storage (much worse on non-thin LVM where there is no fast copy-on-write clone).

**How to avoid:**
- After every mutating call, capture the UPID and poll `GET /nodes/{node}/tasks/{upid}/status` until `status == "stopped"`, then assert `exitstatus == "OK"`. proxmoxer ships a `tasks.blocking_status()` / wait helper; use it rather than hand-rolling. Treat any non-`OK` exitstatus as a hard failure that triggers cleanup (Pitfall 7).
- Make `ProxmoxService` methods that wrap async tasks `await`-able and have them block on the UPID internally, so `WorkspaceService` cannot accidentally race them.
- The template must be a **linked-clone-capable** setup or you must accept full-clone latency; either way the health-poll timeout (`TTYD_HEALTH_TIMEOUT = 60`) needs to budget clone time too, or move clone-wait out of the health budget.

**Warning signs:**
"CT is locked," "volume already exists," intermittent boot failures that vanish when you add a manual sleep, create succeeding on an idle node but failing under load.

**Phase to address:** Phase 1 (Control Plane API) — `ProxmoxService` task-wait is foundational; do not build `WorkspaceService` on top of fire-and-forget calls.

---

### Pitfall 2: VMID allocation race — two concurrent creates grab the same VMID

**What goes wrong:**
`getNextVmId()` (tech-spec §6.2 step 2) "finds the next unused VMID in the pool." If two `POST /api/workspaces` requests run concurrently (two browser tabs, a retry, or the create flow being slow enough to overlap), both read the same "next free" id before either has created a container, and the second clone fails with `CT <id> already exists` — or worse, races into a partially created container. The control plane runs `--workers 2` (uvicorn, §10.2), so two OS processes can genuinely run this concurrently; an in-process lock will not save you.

**Why it happens:**
"Next free id" is a classic check-then-act TOCTOU. SQLite is the source of truth for workspaces, but the VMID lives in Proxmox; the gap between "I picked 207" and "Proxmox now owns 207" is unguarded. Two uvicorn workers means even a Python `asyncio.Lock` is insufficient.

**How to avoid:**
- Make Proxmox itself the allocation arbiter where possible: Proxmox `/cluster/nextid` returns a cluster-wide free id, but it still has a TOCTOU window, so combine it with a reservation row.
- Reserve the VMID in SQLite **before** calling Proxmox: a `UNIQUE` constraint on `workspaces.vmid` plus an INSERT-then-clone ordering turns the race into a constraint violation you can retry, instead of a Proxmox error. (The spec writes the DB row at step 5, *after* clone at step 3 — invert this: reserve id in DB first, then clone.)
- Because there are two uvicorn workers, the lock must be cross-process: rely on the DB unique constraint (works across workers) or run the create saga single-flighted (e.g. one worker owns creates, or serialize via a DB advisory lock pattern).
- Align with the **static-IP-per-VMID** decision (open question B1, recommendation = static): if VMID 207 deterministically maps to `10.x.y.207`, a VMID collision is also an IP collision, which makes the unique-constraint guard doubly important.

**Warning signs:**
`CT already exists` under rapid creates, two workspaces showing the same `vmid`, IP conflicts on the LAN, a create that "sometimes" fails when you click New twice quickly.

**Phase to address:** Phase 1 (allocation + unique constraint). Re-verify under Phase 4 capacity/auto-stop work where concurrent lifecycle events multiply.

---

### Pitfall 3: The ttyd WebSocket proxy passes raw bytes — but ttyd speaks a framed sub-protocol, so the naive proxy never works

**What goes wrong:**
The spec's proxy (tech-spec §6.4) bridges raw binary frames both directions with `iter_bytes()` / `ttyd.send(msg)`. ttyd does **not** accept raw terminal bytes. Its WebSocket protocol requires:
1. The connection to negotiate the `tty` **sub-protocol** (`Sec-WebSocket-Protocol: tty`) on the upstream connect.
2. A **JSON init message** as the first client message (`{"AuthToken":"","columns":C,"rows":R}`); ttyd will not start the PTY until it receives this.
3. **Command-prefixed frames** thereafter: client→server input is byte `'0'` + data, resize is byte `'1'` + JSON `{"columns":C,"rows":R}`, pause/resume are `'2'`/`'3'`. Server→client output is byte `'0'` + data, with `'1'`=SET_WINDOW_TITLE and `'2'`=SET_PREFERENCES.

A pure passthrough proxy that forwards xterm.js bytes straight to ttyd sends unprefixed data; ttyd interprets the first byte as a command and discards/mis-routes the rest. The terminal appears connected but is dead, or echoes garbage, or never resizes.

**Why it happens:**
"WebSocket proxy = copy bytes both ways" is the obvious mental model, and the spec reinforces it. The framing and init handshake are invisible until you wire a real ttyd and watch nothing happen.

**How to avoid:**
- Decide the proxy's role explicitly. Two viable designs:
  - **(Recommended) Thin pass-through, client-aware:** the *browser* terminal client speaks ttyd's protocol directly (use ttyd's own client bundle or a small client that emits `'0'`/`'1'` frames and the JSON init), and the proxy is a dumb byte relay that also forwards the sub-protocol header. xterm.js then needs an adapter that prefixes input with `'0'` and sends `'1'`+JSON on FitAddon resize.
  - **Translating proxy:** the proxy terminates ttyd's protocol and re-frames for a plain xterm.js client. More code, but decouples the browser from ttyd specifics.
- Whichever you choose, the upstream connect MUST request `subprotocols=["tty"]`, and the init JSON MUST be sent before expecting output.
- **Resize is a control message, not terminal data.** xterm.js FitAddon computing new cols/rows must turn into a `'1'`+`{"columns","rows"}` frame to ttyd; otherwise the PTY stays at its default 80x24 and full-screen TUIs (which `claude` is) render wrapped/garbled.

**Warning signs:**
Terminal connects (status flips to connected, events logged) but shows nothing or mojibake; input does nothing; `claude`'s TUI is stuck at 80x24 regardless of panel size; works against your stub echo server (which ignores framing) but breaks against real ttyd.

**Phase to address:** Phase 1 owns the proxy framing decision and the upstream sub-protocol; Phase 2 owns the xterm.js-side adapter (input prefixing + resize control frames). **The Tier-2 "stub ttyd echo server" (ci-cd §4.3) will hide this bug** unless the stub also enforces the `tty` sub-protocol and command-prefix framing — make the stub protocol-accurate, not a bare echo.

---

### Pitfall 4: `--once` + closing the tab silently kills the Claude session (detach vs terminate)

**What goes wrong:**
`burrow-boot.sh` (§9.3) runs `ttyd --once`. `--once` means ttyd accepts exactly one client and **exits the moment that client disconnects** — and since ttyd is PID 1 of the worker's foreground service (`exec ttyd`), ttyd exiting tears down the `claude` process. Result: the operator closes a browser tab, switches networks, or the laptop sleeps, and their running Claude session (and any in-flight agent work) is destroyed. This directly contradicts the core value prop ("watch and switch between many sessions") and the stated requirement "restore/reconnect terminal after browser refresh while workspace still running."

**Why it happens:**
`--once` is convenient for the "workspace done = container gone" model, and the spec even rationalizes it ("exit when client disconnects (workspace done)"). But the WS proxy sits between browser and ttyd: a browser refresh closes the proxy→ttyd connection, which trips `--once`, which kills Claude — even though the LXC is still running and the user wanted to reconnect. This is open question B2, and getting it wrong is a data-loss-class UX failure.

**How to avoid:**
- **Do not use `--once` for interactive worker sessions.** Run ttyd persistently (drop `--once`), so a disconnect is just a disconnect and the next WS connect re-attaches to the same PTY/`claude` process.
- For "reconnect to a live session," ttyd alone re-attaches to *its* PTY, but if ttyd restarts you lose scrollback; if true detach/reattach across ttyd restarts matters, run `claude` inside `tmux`/`abduco` and have ttyd attach to that — then ttyd can die and the session survives.
- Make terminate **explicit**: closing a panel = detach (WS closes, container keeps running); destroy = the only path that kills the container. Surface this in the UI so "close tab" never means "lose work."
- Auto-stop (Phase 4) then becomes the *intentional* lifecycle end (idle N minutes), not an accidental side effect of a dropped socket.

**Warning signs:**
"My Claude session vanished when I refreshed," workspace flips to `stopped`/`error` right after a panel close, agents losing mid-task context on network blips, reconnect overlay never finding a live session.

**Phase to address:** Phase 0/3 (boot script: drop `--once`, optionally add tmux). Phase 2 (UI detach-vs-terminate semantics). Phase 4 (auto-stop as the deliberate end-of-life). This is open question B2 — resolve it *before* Phase 0 finalizes the template, because it changes `burrow-boot.sh`.

---

### Pitfall 5: ttyd bound to `lo`/localhost but the proxy connects over the LAN IP — connection refused

**What goes wrong:**
`burrow-boot.sh` runs `ttyd --interface lo` (binds to 127.0.0.1 inside the worker), and the architecture diagram (§3.1) also says "ttyd (:7681, bound localhost)." But the control-plane proxy connects to `ws://{workspace.lxcIp}:7681/ws` (§6.4) — the worker's **LAN** IP. ttyd bound to `lo` will refuse every connection from the control plane. The two halves of the spec contradict each other.

**Why it happens:**
"Bind ttyd to localhost so it's not exposed" is a sound instinct (v1 is LAN-only, no auth — Pitfall 12), but it's incompatible with a *remote* proxy on a different host reaching it. The contradiction is easy to miss because the proxy code and the boot script live in different repos (`burrow` vs `cc-worker-config`).

**How to avoid:**
- ttyd must listen on an interface the control plane can reach: bind to the worker's LAN interface (or `0.0.0.0`) on `:7681`, OR keep ttyd on `lo` and reach it via an SSH tunnel / Proxmox `pct exec` bridge from the control plane. The simplest LAN-only choice: bind to the worker IP and rely on the worker firewall + the no-auth-LAN-only posture.
- If you keep it on `lo` for safety, the proxy can't use `ws://lxcIp:7681`; you'd need a per-worker tunnel, which is more moving parts than v1 needs.
- The `_waitForTtyd` health poll (§6.2) hits `http://{lxcIp}:7681/` — same reachability requirement; it will time out 100% of the time if ttyd is on `lo`, manifesting as every create ending in `error`.

**Warning signs:**
Every workspace times out at the ttyd health check and lands in `error`; `curl http://<workerIp>:7681` from the control plane gives connection refused while `curl` from *inside* the CT works; health endpoint reports proxmox ok but no workspace ever reaches `running`.

**Phase to address:** Phase 0 (template/boot script binding) and Phase 1 (health poll + proxy target) must agree. Pin the binding decision in an ADR since it has a security dimension.

---

### Pitfall 6: IP not ready when you read it — DHCP-poll latency/races; static pool is the safer default

**What goes wrong:**
`getLxcIp()` "polls until available" and `_waitForIp` is called right after `startLxc`. With DHCP, the IP is unknown until: the CT boots, brings up the NIC, completes a DHCP handshake, and the lease becomes visible to the Proxmox agent/ARP. Polling the Proxmox API for the interface IP can return nothing for many seconds, return a stale/old lease, or return a link-local address first. If you proceed with `None` or a wrong IP, the ttyd health poll connects to the wrong host or never.

**Why it happens:**
DHCP introduces a discovery delay and a visibility gap (the control plane learns the IP via the Proxmox guest-agent or the DHCP server, both lagging). LXCs don't run qemu-guest-agent (that's for VMs); IP discovery for containers goes through the host's view of the veth/lxc-net, which has its own timing.

**How to avoid:**
- Adopt the spec's own recommendation (open question B1): **static IP per VMID** — VMID 207 → `10.x.y.207`, injected via the LXC `net0` config (`ip=10.x.y.207/24,gw=...`) at clone time. Then the IP is known the instant you allocate the VMID; no polling, no race, and it composes with the VMID-uniqueness guard (Pitfall 2).
- If DHCP is unavoidable, treat IP discovery as its own bounded, retried step with a clear timeout distinct from the ttyd timeout, and validate the address (reject link-local/empty) before health-checking.
- Static IPs also remove a whole class of "workspace reconnect points at an IP that changed after restart" bugs (Phase 4 restore).

**Warning signs:**
`lxcIp` null in the DB after create, health poll hitting an unreachable/old IP, IPs changing across stop/start so reconnect breaks, intermittent create failures that correlate with DHCP server load.

**Phase to address:** Phase 1 (IP strategy plumbed into create saga). Open question B1 — decide before Phase 1 completes; static is recommended and simplifies everything downstream.

---

### Pitfall 7: Failed creates leave orphaned clones — no compensation/cleanup (saga rollback)

**What goes wrong:**
The create flow is a multi-step saga: allocate VMID → clone → set userdata → write DB row → start → wait IP → wait ttyd → mark running. If it fails at step 7 or 8 (ttyd never healthy, boot script errored), the spec raises `WorkspaceBootError` and stops — but the **cloned, started LXC still exists on the node**, the VMID is consumed, the static IP is consumed, and (depending on ordering) a `creating` row lingers. Over time the pool (200–299, only 100 ids) fills with orphans and creates start failing with "no free VMID" even though nothing is "running."

**Why it happens:**
The happy path is written; the compensation path isn't. Partial failure in distributed create flows is the norm under real infra (slow clone, bad repo URL in cloud-init, plugin install failure in `burrow-boot.sh`), and "raise and bail" feels done in unit tests where Proxmox is mocked to always succeed.

**How to avoid:**
- Wrap the saga in try/except with **compensating actions**: on any failure after clone, stop+destroy the LXC (poll its UPID), free the IP, and set the DB row to `error` (don't leave it `creating`). The integration tier (ci-cd §4.3) explicitly calls for testing "compensation/cleanup on failure" — make that test real, not aspirational.
- Make destroy idempotent (Pitfall 8) so cleanup is safe even if the container half-exists.
- Add a **reconciler/janitor**: on startup and periodically, list pool VMIDs on the node, diff against DB `running`/`stopped` rows, and destroy clones with no owning row (and mark `creating` rows older than the boot timeout as `error`, destroying their CTs). This is the safety net for crashes mid-saga that no try/except can cover (control plane killed at step 6).
- Distinguish "boot failed, container exists" from "clone failed, nothing exists" so cleanup targets the right thing.

**Warning signs:**
`pct list` on the node shows VMIDs with no matching workspace; "no free VMID in pool" with few visible workspaces; rows stuck in `creating` forever; node memory creeping up from dead-but-running clones.

**Phase to address:** Phase 1 (saga compensation in `WorkspaceService`). Phase 4 (the periodic reconciler/janitor, alongside auto-stop, which is the same "compare desired vs actual" muscle).

---

### Pitfall 8: State-machine edge cases — stop during create, double-destroy, `creating→error` with no exit

**What goes wrong:**
The state machine (§5.3) only draws the happy edges. The dangerous transitions are the ones not drawn:
- **stop/destroy while `creating`:** user clicks Stop on a workspace mid-clone. The container is locked by the clone task; `stopLxc` fails or races. The DB says `creating`, Proxmox says locked, the UI offers Stop anyway.
- **`creating → error` with a live container:** boot fails, row goes `error`, but the LXC is up consuming RAM (Pitfall 7).
- **double-destroy / destroy-then-start:** `DELETE` soft-deletes the row but a stale UI still shows it and lets the user click Start on a destroyed workspace.
- **start on `error`:** is `error` recoverable (retry boot) or terminal (must destroy)? Undefined.

**Why it happens:**
State machines get drawn for the demo path. Real users click buttons at the wrong time, and TanStack Query polling (Phase 2) shows slightly stale state, so the UI offers actions the backend must reject.

**How to avoid:**
- Define and **enforce allowed transitions server-side** as an explicit table (from-state → action → to-state), rejecting illegal ones with a clear error code in the envelope — never trust the UI to gate. e.g. Stop is only legal from `running`; while `creating`, Stop means "cancel the saga" (a distinct, deliberate path), not "stop the container."
- Make `error` a defined state with a defined exit: either "retry → re-enter create saga" or "destroy only." Don't leave it ambiguous.
- Guard the WS proxy: it already checks `status == "running"` before accepting (§6.4) — keep that, and ensure status is authoritative.
- Persist a `lock`/in-flight marker so a second mutating request on the same workspace is rejected while one is in progress (prevents double-destroy, stop-during-create).

**Warning signs:**
Buttons that error when clicked at the wrong moment; workspaces that won't leave `creating`; "destroyed" workspaces reappearing or accepting Start; Proxmox "CT is locked" on user-initiated stop.

**Phase to address:** Phase 1 (transition table + server-side enforcement + per-workspace in-flight lock). Phase 2 (UI disables actions per state, but treats backend as the gate).

---

### Pitfall 9: Soft-delete vs unique constraints — VMID/name reuse collides with tombstoned rows

**What goes wrong:**
`DELETE` soft-deletes (`deletedAt`, §6.3 / §7.1) but the row, including its `vmid`, stays in the table. If you add a `UNIQUE(vmid)` constraint (which you should, per Pitfall 2) and later reuse VMID 207 for a new workspace, the INSERT collides with the tombstoned row. Same for any `UNIQUE(name)`. Conversely, if you *don't* constrain, you get duplicate active VMIDs.

**Why it happens:**
Soft-delete and uniqueness are in tension: "keep the history" vs "the id is free again." The VMID pool is small (100 ids) and meant to be recycled, so reuse is guaranteed, not hypothetical.

**How to avoid:**
- Use a **partial unique index**: `UNIQUE(vmid) WHERE deletedAt IS NULL` (and `WHERE status != 'destroyed'`). SQLite supports partial indexes. This lets a tombstoned VMID 207 coexist with a freshly recycled active 207.
- Treat `destroyed`/soft-deleted rows as out of the allocatable set in `getNextVmId` (scan only live rows + actual Proxmox state, not tombstones).
- Decide what `vmid` means on a destroyed row: keep it for audit, but it must not block reuse.

**Warning signs:**
`UNIQUE constraint failed: workspaces.vmid` on create after some destroys; `getNextVmId` skipping ids that are actually free because tombstones still claim them; pool "full" with mostly-destroyed history.

**Phase to address:** Phase 1 (schema: partial unique index; allocation reads live rows only). Surfaces immediately once you destroy + recreate.

---

### Pitfall 10: Long-lived WS killed by proxy/idle timeouts; reconnect storms; bridge-task ordering

**What goes wrong:**
Several related WS failures:
- **nginx timeout:** the spec sets `proxy_read_timeout 3600s` (§10.1) — good — but a Claude session can sit idle (thinking, waiting on the user) longer than an hour, and any *intermediate* proxy/load balancer or the FastAPI/uvicorn side without its own keepalive will still drop it. ttyd sends periodic data, but idle is idle.
- **No heartbeat:** without WS ping/pong, half-open TCP (laptop sleeps, Wi-Fi drops) isn't detected for minutes; the proxy keeps a dead upstream and the UI thinks it's connected.
- **Bridge-task half-open:** the proxy does `asyncio.gather(clientToTtyd(), ttydToClient())`. When the *client* disconnects, `iter_bytes()` may not raise promptly, so `clientToTtyd` hangs while `ttydToClient` keeps reading ttyd — the gather never returns, the upstream ttyd connection leaks, and (with `--once`) ttyd may never see the close. This is a known FastAPI/Starlette footgun: one side closing does not reliably cancel the other.
- **Reconnect storms:** the frontend reconnects with backoff (5 retries, max 30s, §8.3). If the *backend* is down or the workspace is in `error`, N panels each reconnecting hammer the API; without jitter they synchronize into thundering-herd bursts.

**Why it happens:**
WS bridges look trivial (two loops) but correct teardown requires explicit cancellation, and idle terminal sessions are genuinely long. Reconnect logic written per-panel doesn't account for many panels reconnecting at once.

**How to avoid:**
- In the proxy, don't bare-`gather`: run both directions as tasks and on *either* completing, **cancel the other** and close both sockets (`FIRST_COMPLETED` + explicit `.cancel()`), then `await` cleanup. This is the documented fix for the half-open hang.
- Enable WS **ping/pong keepalive** on both the client→proxy and proxy→ttyd legs (the `websockets` client supports `ping_interval`) so half-open is detected in seconds, not minutes.
- Add **jitter** to the frontend backoff and a per-error policy: stop retrying (show a terminal error, not "reconnecting…") when the workspace is `error`/`destroyed` vs transient network. Distinguish "workspace gone" (don't retry) from "blip" (retry).
- Budget for sessions longer than any single timeout: prefer detach/reattach (Pitfall 4) over relying on one socket living forever.

**Warning signs:**
Terminals freezing after ~1h idle; "reconnecting" overlay flapping; control plane file-descriptor/connection count climbing with stale ttyd connections; CPU spike when many panels reconnect; ttyd processes lingering after the browser closed.

**Phase to address:** Phase 1 (proxy task-cancellation + keepalive — this is core correctness, not polish). Phase 2 (frontend backoff jitter + error-vs-blip distinction + overlay states).

---

### Pitfall 11: TanStack Query polling vs WebSocket state drift — the list and the terminal disagree

**What goes wrong:**
The sidebar derives status from TanStack Query polling `/api/workspaces` (Phase 2), while the terminal panel's reality comes from the live WS. These drift: the list shows `running` (last poll) while the WS just died and the terminal shows a reconnect overlay; or the list still shows a destroyed workspace for one poll interval and lets the user open a panel against a gone container; or `creating` lingers in the list after the WS is already live. Two sources of truth, no reconciliation.

**Why it happens:**
Polling and streaming are independent clocks. The spec uses polling for the list (simple) and WS for terminals (necessary), but never says which wins when they conflict.

**How to avoid:**
- Pick a precedence rule: **WS/terminal events are the fresher truth for a given workspace's liveness**; when a terminal transitions (connected/errored/closed), optimistically update or invalidate that workspace's query so the list converges fast (`queryClient.invalidateQueries`/`setQueryData`), rather than waiting for the next poll.
- Keep poll interval tight enough for status feel (a few seconds) but don't rely on it for correctness of destructive actions — gate Start/Stop/Destroy on a fresh server check (the backend already rejects illegal transitions per Pitfall 8, so a stale UI click fails safely).
- On destroy, remove the row from the cache immediately and close any open panel for it, rather than waiting for the poll to drop it.

**Warning signs:**
Sidebar status lagging the terminal by a poll cycle; opening a panel on a workspace that's actually gone; flicker between states; users confused why the list says running but the terminal is dead.

**Phase to address:** Phase 2 (define the precedence + cache invalidation on WS events). Phase 4 (event log + restore must use the same reconciliation).

---

### Pitfall 12: LAN-only "no auth" assumptions leaking into reachable surfaces

**What goes wrong:**
v1 is LAN-only, no auth, *by design* (PROJECT.md, CLAUDE.md). The risk isn't building auth — it's the **unauthenticated, unencrypted surfaces** this exposes if the network boundary is weaker than assumed: the WS terminal proxy gives a raw, writable `claude` shell with no credential check (`--writable`, no AuthToken), ttyd reachable on the LAN (Pitfall 5), the Proxmox token in `.env`, and CORS/`ALLOWED_ORIGINS` left permissive. Anyone who reaches `burrow.lan` gets root-equivalent shells in every worker. If the "LAN" is a flat home network with IoT devices, a guest VLAN, or a VPN that's broader than expected, "LAN-only" is doing a lot of unspoken work.

**Why it happens:**
"No auth in v1" gets read as "security is out of scope for v1," which is different. The spec correctly defers *multi-tenant auth* to the hosted path, but v1 still needs the network boundary to actually be the boundary, and still needs the non-auth security controls (headers, CORS, secret hygiene) the spec explicitly requires.

**How to avoid:**
- Treat the LAN boundary as a hard precondition and document it loudly: bind the control plane to the LAN interface only, never a public IP; assume anyone on the LAN can drive any workspace.
- Don't let "no auth" suppress the controls that *are* in scope: security headers on every API response, a **non-permissive CORS origin** (`ALLOWED_ORIGINS`, not `*` — `*` is incompatible with WS credentials anyway), and the standard envelope not leaking internals in `error.message`.
- Keep auth seams clean but *absent* from v1 code paths (per CLAUDE.md) so the hosted path is additive — don't stub half-auth that gives false confidence.
- Be explicit that workers run arbitrary agent code with network egress; the boundary is the only thing between a LAN peer and a root shell.

**Warning signs:**
Control plane reachable from outside the intended subnet; `ALLOWED_ORIGINS=*`; ttyd reachable from devices that shouldn't reach it; security-headers middleware missing; `.env` readable by other LAN services.

**Phase to address:** Phase 1 (headers + CORS + bind interface). Phase 4 (hardening pass confirms no public exposure). Documented as a deployment precondition, not a code feature.

---

### Pitfall 13: Secrets in cloud-init userdata and `.env` — Proxmox token and git creds leak

**What goes wrong:**
`_buildUserdata` (§6.2) injects env into the worker via cloud-init. Two leaks lurk: (1) anything you put in cloud-init userdata is **readable inside the guest** (and often via the Proxmox config / snippets file on the host) — a git deploy token or PAT for private `projectRepo`/`CONFIG_REPO` ends up persisted where any process in the worker (i.e. the agent, or a malicious repo's build step) can read it; (2) the Proxmox API token in `.env` (§10.3) is a powerful credential — if it's `root@pam` or over-privileged (Pitfall 14), a leaked token is cluster compromise.

**Why it happens:**
cloud-init is the natural injection point and feels private. But `git clone` of a private repo needs a credential somewhere, and the obvious move (bake a token into userdata) makes it readable by the very agent code you don't fully trust. The spec uses SSH-style `git@github.com:...` repos but doesn't say where the deploy key lives.

**How to avoid:**
- Never put long-lived git tokens in cloud-init. Prefer a **short-lived, narrowly-scoped** credential (a per-clone deploy token, GitHub App installation token, or read-only deploy key for that one repo), and remove it from the environment after `git clone` in `burrow-boot.sh` (don't leave it in `/etc/burrow/worker.env`).
- Keep the Proxmox token least-privilege (Pitfall 14) and out of any worker-visible surface — it belongs only to the control plane's `.env`, never injected into workers.
- Enforce the repo's secret hygiene (ci-cd §5.3): gitleaks (CI + pre-commit), `.env` gitignored, `.env.example` only, `.dockerignore` excludes `.env*`. Ensure cloud-init userdata is never logged in events or structured logs (it'll contain repo URLs and possibly creds).
- Remember the worker runs an **untrusted-by-default agent** plus arbitrary cloned project code; assume anything in the worker env is exposed to it.

**Warning signs:**
Tokens visible in `/etc/burrow/worker.env` after boot, in Proxmox snippet files, or in event-log `data` blobs; `git@github` clones failing because no key is provisioned (driving someone to paste a token into userdata as a "quick fix"); gitleaks hits.

**Phase to address:** Phase 3 (boot script git-auth strategy + scrub-after-use — the spec's Phase 3 already lists "git auth fallback," make it credential-safe). Phase 1 (ensure userdata/secrets never hit logs). Phase 4 (verify no secret-bearing surfaces).

---

### Pitfall 14: Over-privileged Proxmox token + unpinned/over-permissioned CI tokens

**What goes wrong:**
Two supply-chain/least-privilege failures:
- **Proxmox token too broad:** the easy path is `root@pam` or a token with `PVEAdmin`. Burrow only needs clone/start/stop/destroy/config on the worker pool + read node status. A broad token turns any control-plane compromise (Pitfall 12) into full-cluster compromise, and lets a bug destroy unrelated VMs.
- **CI token/action mistakes:** missing per-job `permissions:`, using mutable action tags instead of SHA pins, or granting the publish job's `id-token: write`/`packages: write` to jobs that don't need them — undermining the cosign-keyless/SLSA chain (ci-cd §5.5).

**Why it happens:**
Least privilege is fiddly to scope correctly, and the broad credential "just works" in dev. CI permission blocks default to convenient-but-wide if you don't set them explicitly.

**How to avoid:**
- Create a dedicated `burrow@pve` user (the spec's `.env.example` already says "NOT root@pam") with a **custom role** limited to the exact privileges (`VM.Clone`, `VM.Allocate`, `VM.Config.*`, `VM.PowerMgmt`, `VM.Audit`, `Datastore.AllocateSpace`) scoped to the worker pool/storage, and verify it can't touch non-pool VMIDs.
- In CI: default `contents: read`; each job widens only what it needs; the publish job alone gets `packages: write` + `id-token: write` + `attestations: write`; **pin every third-party action to a full commit SHA** (ci-cd §5.5); gate publish to default branch / release tags + protected environment so fork PRs can't read publish creds.
- Verify the cosign-keyless + SBOM + SLSA chain end to end (sign by digest, attest provenance) rather than assuming the actions "did it."

**Warning signs:**
`.env` with `root@pam`; the token able to clone/destroy VMIDs outside 200–299; CI workflows without `permissions:` blocks; actions referenced by `@v4` instead of `@<sha>`; `id-token: write` at workflow scope.

**Phase to address:** Phase 0/1 (Proxmox role scoping — define the role when you build the template/control plane). CI phase (token scoping, SHA pinning, signing chain — ci-cd §5).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fire-and-forget Proxmox calls (skip UPID polling) | Less code, "works" against mocks | Races, locked-CT errors, flaky creates under load (Pitfall 1) | Never — it's the core failure mode |
| `getNextVmId` scans without a reservation/unique constraint | Trivial to write | VMID collisions under concurrency, IP collisions (Pitfall 2) | Never on a multi-worker uvicorn deployment |
| Bare `asyncio.gather` for the WS bridge | Matches the spec snippet | Half-open hangs, leaked ttyd connections (Pitfall 10) | Never — use FIRST_COMPLETED + cancel |
| `--once` on ttyd | "Workspace done = gone" simplicity | Tab-close kills live agent sessions (Pitfall 4) | Only for genuinely one-shot, throwaway runs the user never reconnects to |
| Stub ttyd as a bare WS echo in tests | Fast Tier-2 tests | Hides the framing/sub-protocol bug (Pitfall 3) until real infra | Never — make the stub protocol-accurate |
| No saga compensation (raise and bail) | Happy path ships faster | Orphan clones exhaust the 100-id pool (Pitfall 7) | Only with a reconciler janitor as the safety net, and even then add compensation |
| DHCP + poll instead of static IPs | Flexible addressing | Boot races, reconnect-after-restart breakage (Pitfall 6) | If your network truly can't do a static pool; otherwise prefer static |
| Polling-only status, no WS-driven invalidation | Simple frontend | List/terminal drift, stale destructive actions (Pitfall 11) | MVP only if destructive actions are server-gated |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Proxmox clone/start/destroy | Assuming the HTTP 200 means done | Poll `/nodes/{node}/tasks/{upid}/status` to `stopped` + assert `exitstatus==OK` (Pitfall 1) |
| Proxmox VMID allocation | `nextid`/scan then clone (TOCTOU) | DB unique reservation before clone; treat collision as retry (Pitfall 2) |
| Proxmox LXC (vs VM) IP discovery | Expecting qemu-guest-agent; polling for IP | Static IP per VMID injected at clone, or bounded DHCP-discovery step (Pitfall 6) |
| Unprivileged LXC + nesting | Forgetting `nesting=1` so Node/npm/agent sandboxes fail; or running privileged "to make it work" | Keep unprivileged + `nesting=1` (§9.1); never drop to privileged to paper over a permission error |
| cloud-init userdata | Putting long-lived git/Proxmox creds in it (guest-readable) | Short-lived scoped creds, scrubbed after clone; control-plane secrets never injected (Pitfall 13) |
| ttyd WebSocket | Raw byte passthrough; no `tty` sub-protocol; no JSON init; resize as data | Negotiate `tty` subprotocol, send JSON init, command-prefix frames, resize via `'1'`+JSON (Pitfall 3) |
| ttyd lifecycle | `--once` + ttyd as PID1 tears down Claude on disconnect | Persistent ttyd (+ tmux for true detach), explicit terminate path (Pitfall 4) |
| ttyd binding | Bind `lo` but proxy connects to LAN IP | Bind reachable interface, or tunnel from control plane (Pitfall 5) |
| nginx WS proxy | Default 60s read timeout drops long sessions | `proxy_read_timeout`/`proxy_send_timeout` raised (§10.1) **and** WS ping/pong (Pitfall 10) |
| xterm.js FitAddon | `fit()` on a hidden/zero-size container; no ResizeObserver cleanup | Fit after layout/visible; disconnect ResizeObserver + dispose terminal on unmount (Pitfall 15) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Leaked ttyd/proxy connections on half-open WS | Control-plane FD/connection count climbs; node memory from lingering ttyd | Cancel sibling bridge task + WS keepalive (Pitfall 10) | A few dozen disconnect/reconnect cycles |
| Synchronous Proxmox calls blocking the event loop | API latency spikes during create; `/health` slow under load | Run blocking proxmoxer calls in a threadpool / async wrapper; never block the loop | First time two creates overlap |
| VMID pool exhaustion via orphans | "No free VMID" with few active workspaces | Saga compensation + reconciler janitor (Pitfall 7) | After ~100 cumulative failed/leaked creates (pool is 200–299) |
| Tight TanStack Query poll across many panels | Constant `/api/workspaces` traffic; backend churn | Reasonable interval + WS-event-driven invalidation (Pitfall 11) | 10+ open panels polling in lockstep |
| Reconnect storm without jitter | CPU/connection burst when backend blips | Jittered backoff + stop-on-terminal-error (Pitfall 10) | Several panels reconnecting simultaneously |
| FitAddon `fit()` on every resize event unthrottled | Janky resize, excess `'1'` resize frames to ttyd | Debounce resize; only send resize control frame on actual dimension change | react-mosaic drag-resize (continuous events) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `root@pam` / over-broad Proxmox token | Control-plane compromise = full cluster compromise | Dedicated least-privilege role scoped to the worker pool (Pitfall 14) |
| Git/Proxmox creds in cloud-init userdata | Untrusted agent/project code reads them | Short-lived scoped creds, scrubbed post-clone; control-plane secrets never injected (Pitfall 13) |
| Unauthenticated writable ttyd reachable beyond intended LAN | Anyone on the network gets root shells in every worker | Hard LAN boundary as precondition; bind to LAN interface only; document the threat (Pitfall 12) |
| `ALLOWED_ORIGINS=*` / missing security headers | CSRF-style WS abuse; info leakage | Non-permissive CORS, security-headers middleware on every response (Pitfall 12) |
| Mutable action tags / wide CI permissions | Supply-chain tampering; leaked publish creds | SHA-pin actions, per-job least-privilege permissions, protected publish environment (Pitfall 14) |
| Secrets/userdata in event-log `data` or structured logs | Credential disclosure via logs | Redact repo URLs/creds from logs and event payloads (Pitfall 13) |
| Worker egress unrestricted | Compromised agent exfiltrates / pivots | Accept as v1 risk explicitly, or firewall worker egress; never silently assume safe |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Tab close = session destroyed (`--once`) | Lost in-flight agent work, no way to reconnect | Detach-on-close; destroy is the only kill path (Pitfall 4) |
| Reconnect overlay that retries forever on a dead workspace | User stares at "reconnecting…" for a gone container | Distinguish blip (retry) vs `error`/`destroyed` (show terminal error) (Pitfall 10) |
| Sidebar status lagging terminal reality | Confusion; clicking actions on stale state | WS-event-driven cache invalidation; server-gate destructive actions (Pitfall 11) |
| Buttons offered for illegal transitions | Cryptic errors when clicked at the wrong time | Disable per state in UI + reject server-side with clear envelope error (Pitfall 8) |
| Terminal stuck at 80x24 in a big panel | TUI (`claude`) renders wrapped/garbled | Send resize control frames on FitAddon changes (Pitfall 3/15) |
| No boot progress detail on a 60s+ create | User thinks it hung | Stream saga steps (cloning/starting/waiting) as the modal already intends (§8.3) |
| Mosaic layout lost on refresh | User re-arranges panels every reload | Persist Mosaic tree in Zustand + localStorage; reconcile against live workspaces (Pitfall 15) |

## "Looks Done But Isn't" Checklist

- [ ] **Workspace create:** Often missing UPID task-wait — verify clone *completes* before start, against a slow/real clone, not a mock.
- [ ] **VMID allocation:** Often missing concurrency guard — verify two simultaneous creates don't collide (partial unique index + reservation).
- [ ] **Failed create:** Often missing cleanup — verify a forced boot failure leaves **no** orphaned CT and the row is `error`, not `creating`.
- [ ] **WS proxy:** Often missing ttyd framing/sub-protocol — verify against **real ttyd**, not the echo stub; confirm input and resize work.
- [ ] **WS teardown:** Often missing sibling-task cancellation — verify no leaked ttyd connection after the browser closes (check FD count).
- [ ] **ttyd reachability:** Often a `lo`-vs-LAN-IP contradiction — verify the control plane can actually reach ttyd at the address the proxy/health-poll uses.
- [ ] **Reconnect:** Often missing the live-session case — verify refreshing the browser reattaches to the *same* Claude process (not a fresh one, not a dead one).
- [ ] **State machine:** Often missing illegal-transition rejection — verify Stop-during-`creating` and Start-on-`destroyed` fail safely server-side.
- [ ] **Soft-delete + reuse:** Often missing partial unique index — verify destroy-then-recreate reusing a VMID succeeds.
- [ ] **xterm.js unmount:** Often missing dispose/observer cleanup — verify opening+closing many panels doesn't grow memory or leak ResizeObservers.
- [ ] **Secrets:** Often leaked via cloud-init/logs — verify no creds in `/etc/burrow/worker.env` post-boot or in event `data`.
- [ ] **Capacity guard:** Often a stale read — verify the RAM check is fresh and that concurrent creates can't both pass the guard and overcommit the node.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Orphaned clones (Pitfall 7) | LOW (with janitor) / MEDIUM (manual) | Run the reconciler: list pool VMIDs, diff vs live rows, destroy unowned CTs, mark stale `creating` rows `error` |
| VMID collision / pool exhaustion (Pitfall 2/9) | MEDIUM | Add partial unique index + reservation; clean tombstones from allocation; destroy orphans to free ids |
| ttyd framing wrong (Pitfall 3) | MEDIUM | Implement the `tty` sub-protocol + JSON init + command-prefix adapter; fix the test stub to be protocol-accurate |
| `--once` killed live sessions (Pitfall 4) | LOW (config) | Drop `--once` from `burrow-boot.sh`, reprovision/re-pull template; add tmux for cross-restart detach |
| ttyd on `lo` unreachable (Pitfall 5) | LOW | Rebind ttyd to the worker LAN interface; redeploy boot script |
| Leaked WS connections (Pitfall 10) | MEDIUM | Rewrite bridge to FIRST_COMPLETED+cancel, add keepalive; restart control plane to drop leaked FDs |
| State stuck in `creating` (Pitfall 8) | LOW | Reconciler marks timed-out `creating` rows `error` + destroys their CTs; define `error` exit path |
| Leaked secret in userdata/logs (Pitfall 13) | HIGH | Rotate the exposed credential immediately; scrub logs/snippets; fix injection to scoped+scrubbed creds |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Proxmox task (UPID) polling | Phase 1 | Integration test: clone task must reach `OK` before start; works against a delayed-task mock |
| 2. VMID allocation race | Phase 1 | Concurrency test: two parallel creates → one succeeds, one gets a clean retryable error |
| 3. ttyd protocol framing | Phase 1 (proxy) + Phase 2 (xterm adapter) | E2E against a protocol-accurate ttyd stub; manual against real ttyd in dev |
| 4. `--once` / detach-vs-terminate | Phase 0 (boot) + Phase 2 (UI) + Phase 4 (auto-stop) | Refresh browser → same Claude process; close panel ≠ destroy |
| 5. ttyd binding reachability | Phase 0 + Phase 1 | Control plane `curl`s ttyd at the proxy's target address successfully |
| 6. IP allocation strategy | Phase 1 | `lxcIp` known/valid before health poll; survives stop/start (static) |
| 7. Saga compensation / orphans | Phase 1 (compensate) + Phase 4 (janitor) | Forced boot failure leaves no CT, row=`error`; janitor reaps an injected orphan |
| 8. State-machine edge cases | Phase 1 (server) + Phase 2 (UI) | Illegal transitions rejected with envelope error; in-flight lock blocks double-destroy |
| 9. Soft-delete vs unique | Phase 1 | Destroy then recreate reusing a VMID succeeds; allocation ignores tombstones |
| 10. WS timeouts/teardown/storms | Phase 1 (proxy) + Phase 2 (frontend) | No leaked FDs after disconnect; long-idle session survives; jittered backoff |
| 11. Poll vs WS drift | Phase 2 (+ Phase 4) | WS events invalidate the query; destroyed workspace leaves list immediately |
| 12. LAN-only leakage | Phase 1 (headers/CORS/bind) + Phase 4 | No public exposure; CORS non-`*`; headers present on every response |
| 13. Secrets in cloud-init/.env | Phase 3 (boot) + Phase 1 (logs) + Phase 4 | No creds in worker env post-boot or in event/log payloads; gitleaks green |
| 14. Least-privilege tokens (Proxmox + CI) | Phase 0/1 (Proxmox) + CI phase | Token can't touch non-pool VMIDs; actions SHA-pinned; per-job permissions minimal |
| 15. xterm.js lifecycle/leaks | Phase 2 | Open/close 50 panels → flat memory, no orphan ResizeObservers; resize sends control frame |

---

### Pitfall 15 (frontend lifecycle, detailed): xterm.js FitAddon timing + dispose-on-unmount leaks + Mosaic state persistence

**What goes wrong:**
Three Phase-2 frontend traps cluster here:
- **FitAddon timing:** calling `fitAddon.fit()` while the panel is hidden, zero-sized, or mid-mount measures a 0x0 (or wrong) container and sets the terminal to 1 column or a wrong geometry; react-mosaic's drag-resize fires a torrent of resize events, each potentially mis-fitting.
- **Dispose leaks:** mounting xterm.js in a `useEffect` without `terminal.dispose()` and `resizeObserver.disconnect()` in cleanup leaks the terminal, the canvas/WebGL context, the WS, and the ResizeObserver every time a panel closes. With a tiling UI where users open/close/split panels constantly, this leaks fast.
- **Mosaic/Zustand persistence drift:** persisting the Mosaic tree (panel layout) to Zustand/localStorage is desired, but on reload the tree can reference workspace IDs that are now `destroyed`/gone, rendering empty/broken leaves; and Zustand persistence of a `MosaicNode<string>` tree needs reconciliation against the live workspace list.

**Why it happens:**
React strict-mode double-mounts and async layout make "fit now" unreliable; cleanup is easy to forget because the leak isn't visible in a quick demo; and persisted layout vs live data is a two-sources-of-truth problem (cf. Pitfall 11).

**How to avoid:**
- Fit only when the container is visible and has nonzero size (observe with ResizeObserver and fit on its callback, debounced); on actual dimension change, also emit the ttyd `'1'`+`{columns,rows}` resize control frame (Pitfall 3).
- In the terminal hook cleanup: close the WS, `terminal.dispose()`, and `resizeObserver.disconnect()` — every mount must have a matching teardown. (ESLint's `no-leaked-resize-observer` can catch the observer half.)
- Persist the Mosaic tree but **reconcile on load**: drop leaves whose workspace no longer exists (or is destroyed), and don't auto-open panels for gone workspaces. Treat the live workspace list as authoritative over the persisted layout.

**Warning signs:**
Terminal renders at 1 column or wrong size on first paint or after a split; memory/canvas-context count grows as panels open/close; broken/empty panels after a reload; resize lag during mosaic drag.

**Phase to address:** Phase 2 (TerminalPanel/useTerminal lifecycle + layoutStore reconciliation). Verify via an open/close-many-panels memory test and a reload-with-destroyed-workspace test.

---

## Sources

- Proxmox task/UPID semantics & polling: Proxmox forum threads on clone task status and config-after-clone races; proxmoxer Tasks tool docs (`tasks.blocking_status` / wait helpers). https://forum.proxmox.com/threads/api-clone-status-process.66464/ , https://proxmoxer.github.io/docs/latest/tools/tasks/ , https://forum.proxmox.com/threads/concurrent-cloning-of-vm.97549/
- Proxmox REST not setting IP immediately after clone (IP/config race): https://forum.proxmox.com/threads/rest-api-not-setting-ipv4-address-for-lxc-container.104538/
- ttyd `--once` semantics (one client, exits on disconnect) and disconnect behavior: ttyd man page; tsl0922/ttyd issues #1028, #672, #840. https://man.archlinux.org/man/extra/ttyd/ttyd.1.en , https://github.com/tsl0922/ttyd/issues/672
- ttyd WebSocket protocol (`tty` subprotocol, JSON init/AuthToken, `'0'`input/`'1'`resize/`'2'/'3'` pause-resume command prefixes): ttyd protocol dev guide and ttyd-porting write-ups. https://github.com/tsl0922/ttyd , https://moebuta.org/posts/porting-ttyd-to-golang-part-i/
- FastAPI/Starlette WS bridge half-open + `asyncio.gather` cancellation footgun: fastapi discussions #9149, #9031, issue #3934; fastapi-proxy-lib teardown design. https://github.com/fastapi/fastapi/discussions/9149 , https://github.com/fastapi/fastapi/issues/3934 , https://github.com/WSH032/fastapi-proxy-lib
- xterm.js FitAddon resize issues + ResizeObserver/dispose leaks: xtermjs/xterm.js issues #4841, #4283, #4113; ESLint React `no-leaked-resize-observer`. https://github.com/xtermjs/xterm.js/issues/4841 , https://www.eslint-react.xyz/docs/rules/web-api-no-leaked-resize-observer
- Burrow spec internal contradictions/decisions: `docs/tech-spec.md` (§3.1, §5.3, §6.2, §6.4, §9.1–9.3, §10.1, Appendix B), `docs/ci-cd-and-testing.md` (§4.3–4.5, §5.5), `.planning/PROJECT.md` (security posture, open questions).

---
*Pitfalls research for: Proxmox-orchestrated browser terminal multiplexer with ephemeral Claude Code workers*
*Researched: 2026-06-09*
