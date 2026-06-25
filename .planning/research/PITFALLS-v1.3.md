<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Pitfalls Research — v1.3 "Go Live"

**Domain:** First real-Proxmox bring-up + in-app setup wizard + LXC workspace persistence (stop/start + scrollback restore) + first live GHCR release (cosign keyless / SLSA / harden-runner egress)
**Researched:** 2026-06-24
**Confidence:** HIGH on Proxmox privsep/ACL/snapshot/CRIU semantics, cosign-keyless + `gh attestation verify` flags, and the Fake-vs-real `proxmoxer` gap (verified against current 2026 Proxmox VE 8.x docs/forums, sigstore/cosign + cli/cli docs, and Burrow's own `docs/test-it-out-checklist.md` + `PROXMOX-PRIMING.md`). MEDIUM on snapshot-storage edge cases and tmux/ttyd multiplexer detach behavior (depends on the exact multiplexer Burrow ships in WSX-03).

> **Scope note.** This file is the **v1.3-specific** pitfalls layer. The v1.0-era pitfalls (UPID polling, VMID race, ttyd framing, WS bridge teardown, xterm lifecycle) remain in `.planning/research/PITFALLS.md` and still apply — they are the *substrate* these new pitfalls sit on. This document covers only the **new** v1.3 surface: first-real-infra, the wizard, persistence, and first GHCR/cosign release. Several pitfalls below reference resolved Burrow ADRs (pull-at-boot = ADR-0002, static-IP-from-VMID = ADR-0004, persistent no-`--once` ttyd = ADR-0006, ttyd `0.0.0.0` bind = ADR-0007) and the H1–H19 / CD-1–CD-10 acceptance IDs from `docs/test-it-out-checklist.md`.
>
> **Phase numbering.** v1.3 resumes at **Phase 10**. Provisional v1.3 phases referenced below: **P10 Setup Wizard**, **P11 Persistence (WSX-02/03)**, **P12 Real-Infra Acceptance (ACC-01)**, **P13 First Release (ACC-02/03)**, **P0-kit** = the operator host-prime kit in `cc-worker-config` (already built, but the wizard/acceptance must not silently re-implement it).

---

## Critical Pitfalls

### Pitfall 1: The Fake-vs-real `proxmoxer` gap — "passed CI over the Fake" hides error shapes and async UPID waits

**What goes wrong:**
Every v1.0–v1.2 contract is green over `FakeComputeProvider` (api 202, ui 117). The Fake returns synchronous, well-shaped Python objects with no task IDs, no locking, no partial state. Real `proxmoxer` returns: (a) **UPIDs** for every mutating call (clone/start/stop/snapshot/destroy/`config set`) that must be polled to `stopped` + `exitstatus == "OK"`; (b) HTTP errors as `proxmoxer.core.ResourceException` carrying a status code and a Proxmox message string (`"CT is locked (disk-move)"`, `403 Permission check failed`), **not** the tidy exceptions the Fake raises; (c) timing — a `--full` clone of a 30 GB rootfs takes seconds-to-minutes; the Fake completes instantly. Code that "works" because the Fake never made it wait, never locked a CT, and never returned a 403 will fail the first time it touches the homelab.

**Why it happens:**
The Fake exists precisely so CI is hermetic (ci-cd §4.4 — real Proxmox is out of CI by design). That guarantee is load-bearing and correct, but it means the **error-handling and task-polling code paths are the least-exercised in the whole app** — they only ever run against a provider engineered to never trigger them. A green pipeline gives false confidence that the real path works.

**How to avoid:**
- Build an `respx`/`responses`-mocked **proxmoxer integration tier** (ci-cd §4.3 already calls for "mocked Proxmox") that returns *real-shaped* responses: a UPID string for mutations, a `tasks/{upid}/status` sequence (`running` → `stopped`+`OK` and a `stopped`+failed variant), and `ResourceException`-class errors (403, 596 "CT is locked", 500). Assert the provider polls, surfaces the Proxmox message, and triggers saga compensation on a failed `exitstatus`.
- Audit every `ProxmoxComputeProvider` method for "does this assume the call is synchronous?" — clone, start, stop, **snapshot**, **rollback**, destroy, `config set` (net0/hostname) **all** return UPIDs.
- Treat the H8 (compensation) and H9 (five-step) homelab gates as the first real exercise and **expect** the first run to surface a Fake-vs-real mismatch; budget a debug pass.

**Warning signs:**
"CT is locked (disk-move/create)"; `KeyError`/`AttributeError` parsing a response that the Fake shaped differently; a create that succeeds on an idle node but fails under load; an `exitstatus` that is `OK`-but-actually-failed because the code never read it.

**Phase to address:** P12 (ACC-01 is where this surfaces), but the *defense* belongs in a **mocked-proxmoxer integration tier added before P12** — ideally early in P11/P12 so the snapshot/rollback paths (new code) are written against real-shaped responses from day one.

---

### Pitfall 2: The reaper / idle auto-stop DESTROYS a persistent stopped workspace (state-machine hazard)

**What goes wrong:**
v1.0's reaper "reconciles desired vs actual: destroys row-less pool CTs, frees leaked VMIDs, fails timed-out `creating` rows." v1.0's auto-stop "stops idle workspaces." WSX-02 introduces a **new, legitimate** durable state: a workspace deliberately `stopped` with its rootfs preserved, meant to be `start`ed again later. If the reaper's "actual vs desired" logic, or the idle reconciler, treats *stopped-with-no-live-ttyd* or *stopped-for-N-minutes* as "garbage to reclaim," it will **destroy a workspace the operator intends to resume** — silent data loss of the worker's disk (project checkout, Claude state, scrollback). This is the single highest-blast-radius v1.3 hazard because persistence's whole value proposition is "your work survives."

**Why it happens:**
The reaper was written when **every** stopped/row-less CT was by definition an orphan (workers were ephemeral; the only durable states were `creating`/`running`/`destroyed`). WSX-02 changes that invariant without the reaper knowing. "Idle → stop" and "stopped → reap" were safe to chain when stop meant "on the way to destroy"; now they are not. The reconciler's desired-state model has a new state it doesn't recognize.

**How to avoid:**
- **Introduce an explicit `persistent` / lifecycle-class flag on the workspace row** and make the reaper's orphan rule "destroy CTs **with no owning row**" — never "destroy CTs whose owning row is `stopped`." A `stopped` row IS desired state; only a missing row is an orphan.
- **Re-derive the idle auto-stop terminal action:** idle → `stop` (preserve disk), **full stop**. There must be **no** `stopped → destroy` edge driven by a timer for a persistent workspace. If a TTL-to-destroy policy is ever wanted, it must be an explicit, separately-configured, opt-in policy with a long horizon and operator-visible warning — not the idle reconciler.
- **Lock the state machine first, write persistence second.** Add the transition table edges (`stopped → starting → running`, `stopped` is durable, `destroy` is the ONLY disk-removing path) and a regression test that **fails if a `stopped` persistent workspace is ever destroyed by a reconcile pass** before any snapshot code lands.
- Re-run the H17 reaper acceptance with a **persistent stopped workspace present as a negative control**: the reaper must destroy the injected off-node orphan and leave the stopped persistent workspace untouched.

**Warning signs:**
A workspace the operator stopped yesterday is gone today; `reaper.destroyed` logged against a VMID that had a live `stopped` row; the VMID pool "frees" ids that belonged to persistent workspaces; disk usage dropping unexpectedly overnight.

**Phase to address:** **P11 (Persistence) owns this** — the state-machine + reaper changes MUST land in the same phase as WSX-02, before the snapshot feature, with the negative-control regression test as a phase gate. Re-verified on real infra in P12 (H17 with a persistent-workspace negative control).

---

### Pitfall 3: Persisting the PVE API token through the wizard leaks it into logs / the data·meta·error envelope / git

**What goes wrong:**
The setup wizard accepts a real `burrow@pve!burrow=<uuid>` token in the browser, ships it to the API, validates it against Proxmox, and stores it. Every hop is a leak site: (1) the token in a `POST` body gets dumped by request-logging middleware; (2) a validation **failure** echoes the offending value back in `error.message` ("could not auth with token `<secret>`"); (3) the wizard's "show me what I configured" `GET` returns the token in `data`; (4) it lands in `.env` but the file is committed because `.gitignore` wasn't checked; (5) it appears in an event-log `data` blob or a structured-log line. The Proxmox token is a powerful credential (clone/start/stop/destroy across the worker pool); leaking it is the v1.3 equivalent of leaking root.

**Why it happens:**
The wizard is a *new* ingress for a secret that previously only ever arrived via the operator-run host-prime kit (which already has hardened secret hygiene: `read -rsp`, `set +x`, `printf`, `git check-ignore .env`). The browser/API path has none of that by default — structured JSON logging (a repo requirement) will happily serialize the whole request body, and the standard envelope will happily round-trip whatever it's given.

**How to avoid:**
- **Never store the raw token in a place the wizard reads back.** Write it to the gitignored `.env` (0600, the same target the kit uses) and treat it as **write-only from the wizard's perspective** — the wizard confirms "token configured ✓", never returns it.
- **Redact at the logging boundary, not at each call site:** a request/response log filter that drops/masks known secret fields (`token`, `tokenValue`, `proxmoxToken`, `Authorization`, `PVEAPIToken`) before anything is serialized. Add a test that posts a token and asserts it appears in **no** log sink.
- **Never put the token (or any fragment of it) in `error.message`.** Validation errors say "authentication failed (403)" with the Proxmox status, never the credential. The envelope's `error` object is operator-facing and log-bound; treat it as public.
- **Refuse to write `.env` unless it's gitignored** — mirror the kit's `git check-ignore .env` guard in the wizard's persistence step; fail closed if the control-plane checkout would commit it. `gitleaks` (CI + pre-commit) is the backstop, not the primary control.
- The token still never reaches a worker (it's control-plane-only; workers use pull-at-boot per ADR-0002) — keep that invariant; the wizard must not "helpfully" pass Proxmox creds downstream.

**Warning signs:**
A token-looking string in `journalctl -u burrow.service`, in an event drawer `data` field, in `error.message`, or in `git log -p`; `gitleaks` hit on `.env`; the wizard's review screen displaying the token back.

**Phase to address:** **P10 (Setup Wizard)** — secret hygiene is a phase-1 wizard gate (redaction filter + write-only-token + gitignore guard + the "token in no log sink" test), not a later hardening pass.

---

### Pitfall 4: Proxmox token ACL too broad OR too narrow — the privsep silent-403 + the missing snapshot/SDN privilege

**What goes wrong:**
Two opposite failures, both first-real-run blockers:
- **Too broad:** the easy path is `root@pam` or a `PVEAdmin` token. A leaked control-plane token (Pitfall 3) then = full-cluster compromise, and a Burrow bug can destroy unrelated production guests.
- **Too narrow / wrong principal (the common one):** under `--privsep 1` (the default), a token's effective rights are the **intersection of the user's and the token's ACLs**. Grant the role to the user but not the token and the token authenticates yet **every clone/start returns 403**. Separately, the v1.0 9-privilege role (`VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt Datastore.AllocateSpace Datastore.Audit Sys.Audit`) was scoped for **ephemeral clone-and-destroy** — it has **no `VM.Snapshot`**. WSX-02's snapshot/rollback path will 403 on the first `snapshot` call because that privilege was deliberately excluded. And "set net0 on the clone" can 403 with a silent **`SDN.Use`** requirement if SDN enforcement is on.

**Why it happens:**
The privsep intersection is non-obvious and the #1 silent-403 cause for fresh Proxmox tokens (PROXMOX-PRIMING §2.3). The role was correctly minimized for v1.0's feature set; v1.3 **adds a capability (snapshots)** without anyone revisiting the privilege list. The host-prime kit grants exactly 9 privileges; nobody widened it for WSX-02.

**How to avoid:**
- **If WSX-02 uses Proxmox snapshots** (`pct snapshot` / rollback) rather than plain stop/start, the role needs **`VM.Snapshot`** added at `/pool/burrow-workers`, granted to **both** the user and the token. Update `00-api-user-role.sh`'s `PRIVS` and re-run it (idempotent role `modify`). **Decide first** whether persistence even needs snapshots (see Pitfall 6 — plain stop/start preserves the disk without any snapshot privilege).
- **Keep the scoped model** (`/pool/burrow-workers` + `/vms/<template>` + `/storage/<rootfs>` + `/nodes/<node>`), never `/` and never `root@pam`. The wizard **validates** a provided token; it does not create or widen it (the PVE-side user/role/token stays operator-run — PROJECT.md: "validates a provided token + guides the manual steps, not silently around them").
- **The authoritative scope check is the `--token` form:** `pvesh get /access/permissions --token "burrow@pve!burrow=<uuid>"` — this resolves the user∩token intersection and catches "granted user but not token." The wizard's validation should call the API-token equivalent so it sees what the *token* sees, not what the user sees.
- A 403 on `set net0` → grant `SDN.Use` on the bridge/vNet (the commented block in the kit).

**Warning signs:**
Token authenticates (`/version` works) but every clone is `403 Permission check failed`; snapshot calls 403 while clone/start succeed; `set net0` 403; the wizard reports "connected ✓" but the first real create fails 403.

**Phase to address:** **P0-kit + P10** — the privilege decision (especially whether `VM.Snapshot` is needed) is driven by **P11's** persistence design, so it must be settled when P11 is designed and reflected in the kit and the wizard's validation **before P12**. The wizard (P10) owns the privsep-aware `--token` validation check.

---

### Pitfall 5: Unprivileged-LXC suspend/CRIU does not work — "persistence" must be stop/start, not suspend/resume

**What goes wrong:**
The natural mental model for "make a workspace survive" is suspend/resume (freeze the running process tree, thaw it later — RAM state + scrollback intact). **On stock Proxmox VE 8.x, suspending an unprivileged LXC fails**: CRIU (`lxc-checkpoint`) cannot dump the nested user-namespace ("Can't dump nested uts namespace"); checkpoint/restore for containers is not fully implemented/tested in Proxmox and breaks specifically on the user-namespace remapping that unprivileged containers require. If WSX-02 is built on `pct suspend`/resume, it will fail on the first real homelab CT — and Burrow's template is deliberately **unprivileged + nesting=1** (the secure choice; never drop to privileged to "fix" this).

**Why it happens:**
Suspend/resume is the intuitive "persist the live session" primitive, and it *works for QEMU VMs*, so it's easy to assume it works for LXC too. The CRIU-on-unprivileged limitation is invisible until you run it on a real unprivileged CT — the Fake provider obviously doesn't model CRIU.

**How to avoid:**
- **Design WSX-02 as stop → (disk preserved) → start, NOT suspend → resume.** A clean `pct stop` then `pct start` preserves the **rootfs** (project checkout, Claude state on disk) but **not** live RAM/process state — the `claude` process is gone and restarts fresh on `start`. That is the correct, achievable v1.3 persistence: the *disk* survives, not the *running process*. This is exactly what the H9 step-3/step-4 gate already assumes ("the LXC stops but its disk is preserved" → "start... terminal reconnects").
- **Do not promise live-process survival across stop/start.** Set the requirement (and the UI copy) to "your files and history survive; the session restarts." Scrollback restore (WSX-03) is the mechanism that makes the *restart* feel continuous (Pitfall 8), separate from disk persistence.
- If true live-process survival is ever a hard requirement, it is **out of v1.3 scope** (it would force privileged containers or a VM substrate — both contradict the security posture). Flag, don't silently attempt.

**Warning signs:**
`pct suspend <vmid>` returns a CRIU "can't dump nested namespace" error; a "resume" that actually cold-boots; tests that pass on the Fake (no CRIU) but the real CT won't suspend; the requirement says "session survives stop/start" and someone reaches for suspend.

**Phase to address:** **P11 (Persistence)** — settle the stop/start-vs-suspend decision in the WSX-02 **design**, before writing it. Verified on real infra in P12 (H9 step 3→4).

---

### Pitfall 6: Snapshot storage-backend requirement + snapshot sprawl / thin-pool exhaustion

**What goes wrong:**
If WSX-02 uses Proxmox **snapshots** (e.g. snapshot-on-stop so start can roll back to a known-good point): (1) **snapshots only work on `zfspool` / `lvmthin`** — **`dir`-type storage does not support LXC snapshots at all** (the call fails), and the worker rootfs MUST already be on thin storage anyway (PROXMOX-PRIMING §3.2: `--full` on thick LVM reserves the full rootfs per clone). So a deployment that primed the pool on `dir` or thick LVM can clone but **cannot snapshot**. (2) Even on thin storage, snapshots accumulate: every snapshot pins the blocks it references, so an over-snapshotted **thin pool fills**, and a full thin pool is a **hard outage** (all writes on that pool fail, not just Burrow's). Snapshot sprawl (one per stop, never pruned) is a slow-motion disk-exhaustion bug.

**Why it happens:**
Snapshots look free on ZFS/thin (instant, copy-on-write), so the cost of *keeping* them is underestimated. The `dir`-storage incompatibility is invisible until a deployment that happens to use `dir` tries the feature. The thin-pool-fill failure mode is shared infrastructure — it takes down more than Burrow.

**How to avoid:**
- **Question whether snapshots are needed at all.** Plain stop/start (Pitfall 5) preserves the disk **without any snapshot** — that satisfies WSX-02 "survive stop/start." Snapshots only add value if you want *rollback to a point-in-time* (undo). If WSX-02 is just "stop and resume," **don't use snapshots** — avoid the whole storage-backend + sprawl class. (This also removes the `VM.Snapshot` privilege need from Pitfall 4.)
- If snapshots ARE adopted: **assert the storage backend supports them at validation/health time** (the wizard health-check should detect `dir`/thick-LVM rootfs storage and warn that snapshot persistence is unavailable), and **bound the snapshot count per workspace** (e.g. keep only the latest; prune on stop) so sprawl is structurally impossible.
- **Monitor thin-pool fill** as an operational precondition (PROXMOX-PRIMING §3.2) — surface it in the health-check, because a full thin pool is a node-wide outage, not a Burrow-only one.

**Warning signs:**
`snapshot feature not available for storage type dir`; `pct snapshot` failing on a deployment that clones fine; thin-pool `Data%` climbing toward 100%; node-wide write failures; snapshots accumulating with no prune.

**Phase to address:** **P11** (the snapshot-vs-plain-stop decision + sprawl bound) and **P10** (the wizard health-check detects an unsupported rootfs storage backend). Recommendation: **default to plain stop/start (no snapshots)** for v1.3 and treat point-in-time rollback as a deferred enhancement.

---

### Pitfall 7: Resume races the reconciler; stale static-IP/ARP after start

**What goes wrong:**
Two start-time races: (1) The operator clicks **Start** on a stopped workspace at the same moment the in-process reconciler runs a reconcile pass. The reconciler sees a `stopped` row with a stopped CT, the start saga sees the same row and begins `pct start` — without a per-workspace in-flight lock, the reconciler may "correct" the state mid-start (or two start attempts race), and the start UPID collides with the reconciler's view. (2) After `start`, the worker comes up on its **VMID-derived static IP** (ADR-0004). Because the IP is deterministic the address is correct, but the **LAN's ARP cache** (on the gateway, the control plane, or a switch) may still hold the entry from a *previous* worker that briefly used that IP, or the worker's NIC takes a moment to announce — so the first ttyd health-poll / WS reconnect hits a stale ARP mapping and times out, landing the start in `error` even though the CT is healthy.

**Why it happens:**
The reconciler was designed to fight orphans and stuck `creating` rows; it now shares the `stopped` state with a legitimate user-initiated start, and the two clocks (user action vs reconcile interval) are independent (cf. the v1.0 poll-vs-WS drift pitfall). Static IPs eliminate *DHCP* races but not *ARP* staleness — the same /24 octet gets reused across worker lifetimes, so the LAN can briefly believe the old MAC owns it.

**How to avoid:**
- **Per-workspace in-flight lock** on every mutating action (start/stop/snapshot/destroy) so the reconciler and a user-initiated start can't both act on one row. The v1.0 state machine already needs this for double-destroy; extend it to cover `start`. The reconciler must **skip rows with an in-flight marker**.
- **Make start idempotent against the reconciler:** the reconciler's job is "reconcile desired vs actual" — if desired is `running` (because a start is in flight) it should never `stop`/`destroy`; if desired is `stopped` it should never `start`. Desired state is the row's intent, set transactionally at the start of the action.
- **Bound + retry the post-start reachability check** as its own step distinct from the ttyd-health budget (mirror the create saga's IP/health separation). Treat a first-attempt connection refusal/timeout as retryable for a short window (let ARP settle / the NIC announce) before declaring `error`. A gratuitous-ARP on the worker at boot (or a short retry loop on the control plane) clears the stale mapping.

**Warning signs:**
Start lands in `error` but `pct status` shows the CT running and `curl` from the node works; intermittent start failures that vanish on a manual retry a few seconds later; the reconciler logging a stop/destroy against a workspace the user just started; two `start` UPIDs for one workspace.

**Phase to address:** **P11** (start-saga in-flight lock + reconciler desired-state skip; ARP/reachability retry on resume). Verified in P12 (H9 step 4 — start reconnects reliably, not flakily).

---

### Pitfall 8: Scrollback restore confusion — reconnect (history intact) vs full reboot (history gone), and ttyd-multiplexer detach pitfalls

**What goes wrong:**
WSX-03 "scrollback restore via worker multiplexer + reattach" conflates two very different cases:
- **Reconnect / detach-reattach (same boot):** the worker never rebooted; ttyd is persistent (no `--once`, ADR-0006) and `claude` runs inside a multiplexer (tmux/zellij). Reattaching re-renders the multiplexer's **live scrollback buffer** — history is intact. This works.
- **After a full worker reboot (stop → start, Pitfall 5):** the worker cold-booted, the multiplexer process and its in-RAM scrollback are **gone**. There is **nothing to reattach to** — `claude` is a fresh process. Promising "scrollback restored after stop/start" is **impossible from the multiplexer alone** because the buffer lived in RAM that's now wiped.

Compounding ttyd-multiplexer traps: (a) reattaching to a *dead* multiplexer session (the pane's process exited) shows an empty/hung pane; (b) **multiple ttyd clients to one tmux pane** — two browser tabs on the same workspace both attach to the same tmux session and **mirror each other** (every keystroke/resize from one appears in the other, and tmux forces the smallest attached client's window size, so one tab shrinks the other's TUI); (c) the multiplexer's **scrollback buffer has a line limit** (tmux `history-limit` default 2000) — "restore" silently truncates long sessions; (d) if ttyd is *not* actually wrapping a multiplexer (just `exec claude`), there is no detach at all and "reattach" gets a fresh shell.

**Why it happens:**
"Reattach restores scrollback" is true within a boot and false across one, but the two are easy to merge into one promise. The multiplexer is the right tool for *detach-reattach*, but it cannot resurrect RAM that a reboot cleared. The multi-client mirroring is a tmux default behavior nobody hits until two tabs open the same workspace.

**How to avoid:**
- **Define the two cases explicitly and set the requirement honestly:** scrollback is restored on **reconnect within the same boot** (multiplexer reattach); after a **stop/start (full reboot)** the session **starts fresh** — disk/files survive (Pitfall 5) but terminal history does not, unless you separately **persist scrollback to disk**. If "history across reboot" is required, the mechanism is **logging the pane to a file on the persistent rootfs** (`tmux pipe-pane`, or `claude`'s own session log) and **replaying the tail** into the new terminal on start — not multiplexer reattach.
- **Reattach to the right session and handle a dead one:** name the multiplexer session deterministically (e.g. `burrow`), `new-session -A` (attach-or-create) so a dead session is recreated rather than hung; detect "pane process exited" and show a clear "session ended, starting fresh" state, not a frozen pane.
- **Decide multi-client policy:** either **one client per workspace** (reject/replace a second attach, the simplest correct choice for a single operator) or accept mirroring but **disable tmux's smallest-client window forcing** (`aggressive-resize` / per-window sizing) so one tab can't shrink another. For a single-operator tool, single-client-per-workspace is the right default.
- **Raise/clamp the multiplexer `history-limit`** to a sane bound and document that scrollback beyond it is dropped; don't imply unlimited history.
- **Confirm ttyd actually wraps the multiplexer** (`ttyd ... tmux new -A -s burrow`) — if the template's boot script `exec`s `claude` directly, WSX-03 has no detach substrate and the template/boot script must change first.

**Warning signs:**
"My scrollback was empty after I restarted the workspace" (the impossible case promised); two tabs echoing each other's input; one tab's TUI shrinking when another opens; an empty/hung pane on reattach (dead session); history cut off at exactly 2000 lines; "reattach" giving a fresh prompt (no multiplexer).

**Phase to address:** **P11** (template/boot-script: ensure ttyd wraps a named multiplexer with attach-or-create + a sane history-limit + single-client policy; this is a `cc-worker-config` change). **P10/P11 UI** owns the honest copy distinguishing reconnect-restore from reboot-fresh. Verified in P12 (a homelab gate: reconnect shows history; stop/start shows fresh-but-files-intact).

---

### Pitfall 9: Wizard validates permissions with a destructive side effect, or with a misleading green health-check (TOCTOU + happy-green)

**What goes wrong:**
The wizard's "validate the token / verify the template / health-check" steps fail in two ways:
- **Destructive validation:** to "prove" the token can clone, the wizard actually **clones a CT** (or to prove start works, starts one) — leaving an orphan, consuming a VMID/IP, and possibly failing halfway. Validation should be **read-only**; a validation step that mutates is a footgun that pollutes the pool on every wizard run.
- **Misleading green:** the health-check returns `compute: ok` because the token **authenticated** (`/version` works), but it never checked the rights the token actually needs (clone on the pool, allocate on the storage, snapshot if used). The operator sees green, the first real create 403s. Conversely, a TOCTOU gap: the wizard validates the token/template/storage at time T, the operator changes something (revokes the token, deletes the template, fills the pool) before first use at T+N — "validated" is stale.

**Why it happens:**
"Can I authenticate?" is the easy check and feels like validation; "can I do the specific privileged operations?" requires the privsep-aware `--token` permission read (Pitfall 4) and storage/template existence checks. The destructive-validation trap comes from wanting a *high-confidence* check ("really clone one to be sure") at the cost of side effects. TOCTOU is inherent to any validate-then-use split.

**How to avoid:**
- **Validate read-only:** check token auth (`/version`), then **read** `/access/permissions` via the `--token` form to confirm the *specific* privileges are present at the *specific* scopes; **read** the template exists and is template-marked (`/nodes/{node}/lxc/{template}/config`); **read** the rootfs storage exists, is thin, and (if snapshots) supports snapshots (`/storage`); **read** node RAM for capacity. Never clone/start/snapshot to "test."
- **Make the health-check assert capabilities, not just connectivity:** `compute: ok` should mean "the 9 (or 10) privileges resolve on the right scopes AND the template AND the storage exist," not "the token authenticated." Distinguish `auth: ok` from `authorized: ok` from `template: ok` from `storage: ok` so a partial failure is legible.
- **Re-validate at point of use, fail gracefully:** the create saga must not assume the wizard's validation is still true — it already polls UPIDs and handles 403s (Pitfall 1); surface "the token that validated yesterday now 403s" as an actionable error, not a crash. Treat wizard validation as "best-effort precondition," the create saga as the real gate.
- The wizard **guides** the operator to run the host-prime kit's `00-api-user-role.sh` for anything missing — it does not silently create users/roles/tokens itself (PROJECT.md invariant).

**Warning signs:**
Orphan CTs appearing after running the wizard; `compute: ok` followed by a first-create 403; the wizard says "ready" but the template was deleted; a validation step that takes minutes (because it's actually cloning).

**Phase to address:** **P10 (Setup Wizard)** — read-only capability validation + capability-asserting health-check are core wizard correctness. Re-validation-at-use is a P12 acceptance (the wizard-green → real-create path).

---

### Pitfall 10: Wizard leaks Proxmox specifics past the ComputeProvider seam

**What goes wrong:**
The wizard's job is intrinsically Proxmox-shaped (token, node, template VMID, storage type, bridge). The temptation is to let `proxmoxer` types, Proxmox error strings, UPIDs, or storage-backend enums flow straight into the wizard's API DTOs and the UI — so the wizard's `/api/v1/setup/*` routes return `proxmoxer.ResourceException` messages, expose `vmid`/`upid`/`zfspool` as first-class fields, and the React wizard imports Proxmox vocabulary. This **breaks the `ComputeProvider` seam** (CLAUDE.md: "don't leak Proxmox or SQLite specifics past these interfaces; a hosted path must be additive"). The Fake provider then can't satisfy the wizard contract (it has no UPIDs, no `zfspool`), so the wizard's own CI tests (which run over the Fake — PROJECT.md: "CI-provable over a Fake/mock Proxmox connection") either can't be written or have to special-case Proxmox.

**Why it happens:**
The wizard is *about* connecting Proxmox, so it feels natural to surface Proxmox concepts directly — the abstraction seems like pointless ceremony for a feature whose whole purpose is provider-specific setup. But the seam is exactly what lets the wizard be CI-provable over the Fake and keeps the hosted path additive.

**How to avoid:**
- **Define `ComputeProvider` capability/validation methods** (e.g. `validateCredentials() -> {authed, authorized, missingPrivileges}`, `checkTemplate() -> {exists, ready}`, `checkStorage() -> {exists, supportsThin, supportsSnapshots}`, `nodeCapacity()`) that return **provider-neutral DTOs**. The Proxmox impl maps `proxmoxer` responses into them; the Fake impl returns canned "all green" DTOs so the wizard's happy/sad paths are CI-provable.
- **Wizard API DTOs use neutral vocabulary:** `health`, `capabilities`, `missingPermissions: string[]`, `storageSupportsSnapshots: bool` — not `upid`, `zfspool`, raw `proxmoxer` error objects. Proxmox error strings get mapped to envelope `error.code` + a sanitized `error.message` (which also serves Pitfall 3's redaction).
- **The existing seam-leakage test must cover the new wizard surface** — assert the wizard API + Fake provider satisfy the contract with no Proxmox-specific imports leaking past the provider boundary.

**Warning signs:**
`proxmoxer` imported in `api/.../setup` routes or in the UI; `upid`/`vmid`/`zfspool`/`lvmthin` as wizard API field names; the seam-leakage test not extended to the wizard; the wizard untestable over the Fake.

**Phase to address:** **P10 (Setup Wizard)** — the provider-neutral validation methods + extended seam-leakage test are part of the wizard's definition of done.

---

### Pitfall 11: Wizard partial-provision / resume — a half-finished setup that can't be re-entered cleanly

**What goes wrong:**
The wizard is a multi-step flow (connect token → verify template → health-check → first workspace). It fails or is abandoned mid-way: token validated and written to `.env`, but the template check failed; or the first workspace half-created. On re-entry the wizard either **starts over from scratch** (re-prompting for the token, re-writing `.env`, possibly minting confusion) or **assumes prior steps are done** (skips the token step, but the token was never actually persisted). Worst case, the "create first workspace" step ran partially and left an orphan CT (cf. saga compensation), and the wizard has no idea.

**Why it happens:**
Wizards are usually modeled as a linear happy path; partial completion and resume are afterthoughts. Setup touches durable state (`.env`, a real CT) so "just restart the wizard" isn't idempotent the way an in-memory form is.

**How to avoid:**
- **Model setup as idempotent, re-enterable steps with derived status** — mirror the host-prime kit's check→act idempotency (PROXMOX-PRIMING §6). On entry, the wizard **derives** what's done from real state: is `.env` populated and does the token still validate? does the template exist? is there at least one workspace? Each step shows done/pending from ground truth, not from a stored "wizard progress" cursor that can lie.
- **Each step is safe to re-run:** re-validating a token is read-only (Pitfall 9); re-writing `.env` prompts before overwrite (kit convention); "create first workspace" reuses the existing create saga **with its compensation** so a half-create is cleaned up, not orphaned.
- **The "first workspace" step is just a normal create** — don't fork a special wizard-only create path that lacks the saga's UPID-wait + compensation (Pitfall 1). Reuse, don't reimplement.

**Warning signs:**
Re-opening the wizard re-asks for a token that's already configured; a wizard "progress" flag out of sync with reality; an orphan CT from an abandoned "first workspace" step; `.env` clobbered without a prompt.

**Phase to address:** **P10 (Setup Wizard)** — derive-status-from-ground-truth + re-runnable steps + reuse-the-create-saga.

---

### Pitfall 12: First cosign keyless verify fails — OIDC identity/issuer mismatch, case sensitivity, tag-not-digest

**What goes wrong:**
ACC-03 CD-5/CD-8 verify the keyless signature, and the **first** verify almost always fails on one of: (1) the `--certificate-identity-regexp` doesn't match the actual Fulcio cert subject (the signing workflow's `…/.github/workflows/release.yml@refs/tags/v1.2.0` identity) — too-narrow or wrong-repo regex → "no matching signatures"; (2) wrong `--certificate-oidc-issuer` (must be exactly `https://token.actions.githubusercontent.com`); (3) **case sensitivity** — the GitHub URL in the identity regex is case-sensitive (`BraveBearStudios`) while the **GHCR image path is lowercased** (`ghcr.io/bravebearstudios/...`), so people mismatch the two; (4) **verifying a floating tag** (`:1.2.0`) instead of the immutable `@sha256:` digest — a tag verify can pass against a *different* artifact or fail confusingly if the tag moved.

**Why it happens:**
Keyless verify requires knowing the exact OIDC identity the signing job presented, which isn't obvious until you inspect a real signature. The lowercase-GHCR vs case-preserved-GitHub-URL split is a genuine footgun unique to GHCR. First-time signers don't yet have a known-good command to copy.

**How to avoid:**
- **Verify by digest, always** (`@sha256:<digest>`), never a tag — resolve the tag to a digest first (`docker buildx imagetools inspect … --format '{{.Manifest.Digest}}'`). Burrow's checklist already mandates this; enforce it in the runbook command.
- **Use the regex Burrow already documents:** `--certificate-identity-regexp 'https://github.com/BraveBearStudios/burrow/.*'` (case-preserved GitHub org) + `--certificate-oidc-issuer https://token.actions.githubusercontent.com`, against the **lowercased** `ghcr.io/bravebearstudios/...@sha256:…` ref. The two cases differing is expected, not a bug.
- **If the first verify says "no matching signatures," inspect the actual identity** with a catch-all (`--certificate-identity-regexp '.*' --certificate-oidc-issuer-regexp '.*'`) to read what the signature *actually* claims, then tighten the regex to match. Do this once to derive the known-good command, then pin it in the release notes/runbook (ci-cd §5.4 requires documenting the exact invocation).
- Run `cosign`/`gh` from **Git Bash on the Windows dev host**, not PowerShell (PowerShell mangles the regex/quoting — checklist Gotcha).

**Warning signs:**
"no matching signatures"; "none of the expected identities matched"; a verify that passes against a tag but you can't reproduce by digest; PowerShell quoting errors on the regex args.

**Phase to address:** **P13 (First Release / ACC-03)** — derive + document the known-good `cosign verify` command on the first real release; pin it in the runbook.

---

### Pitfall 13: GITHUB_TOKEN scope gaps + the release-please tag-retrigger trap + `gh attestation verify` exit-0 footgun

**What goes wrong:**
The publish path (`release.yml`) has three first-run traps:
- **Permission scope gaps:** keyless signing + attestation needs **exactly** `contents: read`, `packages: write`, `id-token: write`, `attestations: write` on the publish job. A **missing scope fails keyless signing with an opaque OIDC error** (not "you forgot a permission") — the most time-wasting first-run failure. Widening unrelated permissions doesn't help; the *specific* four must be present.
- **release-please tag-retrigger trap:** release-please creates the `v*` tag using the run's `GITHUB_TOKEN`, and **GitHub suppresses workflow events triggered by `GITHUB_TOKEN`** — so the new tag **may not auto-fire `release.yml`**, and nothing publishes despite a green release-please run. Silent non-publish.
- **`gh attestation verify` exit-0 footgun:** in some `gh` versions `gh attestation verify` has returned **exit 0 even on failure** (cli/cli#10418) — so a CI/runbook check that only tests `$?` can **pass while verification actually failed**. ACC-03 asserts "exit 0" but exit 0 alone is not proof.

**Why it happens:**
Least-privilege permission blocks default narrow, and the OIDC error doesn't name the missing scope. The `GITHUB_TOKEN` event-suppression is an intentional GitHub anti-recursion safety that surprises everyone the first time. The exit-code bug is a tool defect that makes a naive check lie.

**How to avoid:**
- **Set the publish job's four permissions explicitly and check them first** when keyless signing throws an OIDC error — don't go widening other things (checklist Gotcha). Keep them job-scoped (workflow default `contents: read`).
- **After merging the release PR, explicitly confirm `release.yml` ran** for the tag (`gh run list --workflow release.yml --branch v1.2.0` → both matrix legs green). If it didn't fire, re-run on the tag (`gh workflow run release.yml --ref vX.Y.Z`) or push a fresh tag under a **scoped GitHub App token** (App-token-pushed tags do trigger workflows). Bake this confirm-and-retrigger step into the release runbook (CD-3).
- **Don't trust `gh attestation verify` exit code alone** — assert on its **output** (the "verification succeeded"/verified-attestation text), or pair it with `cosign verify-attestation`, so a tool exit-0-on-failure can't produce a false green. Verify **both** images independently (`fail-fast: false` matrix means a green run can leave one image unverified — CD-8).
- Confirm **both SBOMs** (SPDX-json AND CycloneDX-json) per image (CD-7); a missing format is a silent D1 gap.

**Warning signs:**
Opaque "OIDC token" / "could not fetch token" errors during signing; a green release-please run with no GHCR image and no `release.yml` run; an attestation-verify step that's green but you can't independently confirm; only one image verified.

**Phase to address:** **P13 (First Release / ACC-02 + ACC-03)** — permission-set, tag-retrigger confirm, and output-based verify are first-release acceptance steps.

---

### Pitfall 14: harden-runner egress block-flip breaks publish/build when the allowlist is incomplete

**What goes wrong:**
All 5 CI/release jobs currently run `harden-runner` in **`egress-policy: audit`** (observe, don't block). ACC-02's block-flip turns on `egress-policy: block` with an `allowed-endpoints` allowlist. If the allowlist is incomplete, the **flip silently breaks** whatever phase needs an un-allowed endpoint: the `build-scan` job can't pull base-image layers or the Trivy vuln DB; the `publish` job can't reach **GHCR** or — the easily-missed set — the **cosign keyless infrastructure (Fulcio for the cert, Rekor for the transparency log, the TUF metadata mirror)**. A too-tight allowlist makes signing/attestation fail with network errors that look like cosign bugs.

**Why it happens:**
The allowlist **cannot be guessed**; it must be **derived from the real audit telemetry of the first live runs** (checklist: "cannot be done blind"). `build-scan` and `publish` need the widest allowlists, and the cosign-keyless endpoints (Fulcio/Rekor/TUF) are non-obvious because they're invoked transitively by the signing action, not written in the workflow.

**How to avoid:**
- **Audit first, block second, in this order:** run `ci.yml`, `release-please.yml`, AND `release.yml` in **audit** mode first (CI section 4 + the real release in section 5), **collect the observed egress endpoints per job** from the StepSecurity insights, then build the allowlist from that ground truth and flip to block (CD-9/ACC2-3). The block-flip **depends on the first real release having run** — it can't precede ACC-03.
- **Pre-seed the known-wide sets:** `build-scan` → Docker registry/layer hosts + Trivy DB + GHCR; `publish` → GHCR + **Fulcio + Rekor + TUF (sigstore)** + GitHub attestation API. Add these explicitly rather than discovering them by a failed run.
- **Re-run every workflow after the flip and confirm still-green** (publish still signs+attests, build-scan still pulls+scans) — the flip is only done when a re-run is green, not when the YAML edit merges.
- Cannot be validated on the Windows dev host (no runner) — this is a runner-only acceptance.

**Warning signs:**
Post-flip runs failing with connection/timeout errors to `ghcr.io`, `fulcio.sigstore.dev`, `rekor.sigstore.dev`, a TUF mirror, or a Trivy DB host; signing failing with network errors after the flip; build-scan unable to pull base layers.

**Phase to address:** **P13 (First Release / ACC-02)** — but **strictly after** the first audit-mode runs of all three workflows (ACC-02 CI half + ACC-03 release) have produced telemetry. The flip is the last step, not the first.

---

### Pitfall 15: release-please first-PR version surprise + no prior live run despite existing tags

**What goes wrong:**
Two first-release surprises: (1) The release-please manifest is seeded `1.1.0` (bootstrap-sha = the v1.1 commit), so the **first release PR proposes `v1.2.0`** — not whatever version someone expects from the v1.3 work. If commits since the seed include a `feat:`/breaking change, the proposed bump may differ from the mental model; an operator merging "to publish v1.3" can be confused by a `1.2.0` (or unexpected) tag. (2) Tags `v1.0/v1.1/v1.2` **exist on origin** (cut manually at milestone close) but **were never fetched locally**, **`gh release list` is empty**, and **no GHCR image exists** — so despite the tags, **no release/publish workflow has ever actually run live**. Anyone assuming "the release path is proven because tags exist" is wrong; the first real run is genuinely first.

**Why it happens:**
Manual milestone tags created a false impression of a working release history. release-please derives the next version from the **manifest seed + Conventional-Commit history**, which won't match a human's "this is the v1.3 release" intuition. The gap between "tags exist" and "a release was ever published" is invisible until you check `gh release list`.

**How to avoid:**
- **`git fetch --tags origin` first**, and read the manifest seed before merging the release PR — confirm the proposed version is what's intended (the first PR proposes `v1.2.0` per the `1.1.0` seed; reconcile the v1.3 milestone naming vs the semver release-please computes from commits).
- **Treat the first release/publish as genuinely first** — don't assume any prior live CI/CD run happened. The checklist is explicit: any doc claiming the path is "proven" means YAML parse + SHA-pin regex only, not a live run.
- **Confirm the tag→`release.yml` chain end to end** (Pitfall 13's tag-retrigger) since this is the first time the chain runs for real.
- Note the **Trivy gate has no waiver path** (`ignore-unfixed: false`) — an unfixable HIGH/CRITICAL in `python:3.12-slim`/`nginx:1.27-alpine` base images **fails the build even though Burrow code is clean**, and there's no allowlist in the workflow. The first release can be blocked by a base-image CVE outside Burrow's control; have a base-image-bump or a tracked-waiver plan ready.

**Warning signs:**
A release PR proposing a version nobody expected; assuming a prior publish happened; the first release blocked by a base-image CVE with no waiver path; the tag created but no GHCR image.

**Phase to address:** **P13 (First Release / ACC-02)** — version-seed reconciliation + "this is genuinely the first live run" framing + a base-image-CVE contingency.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Build WSX-02 on `pct suspend`/resume | "Live session survives" feels magical | Fails on every unprivileged CT (CRIU); silent on the Fake (Pitfall 5) | Never — unprivileged + CRIU is broken on stock PVE |
| Snapshot-on-every-stop with no prune | Free-looking rollback | Thin-pool fill = node-wide outage; sprawl (Pitfall 6) | Only with a per-workspace snapshot cap + thin-pool monitoring; prefer plain stop/start |
| Reaper keeps "destroy any stopped/row-less CT" rule | No reaper changes needed | Destroys persistent stopped workspaces — data loss (Pitfall 2) | Never once WSX-02 exists; the rule must become "no owning row" only |
| Wizard validates by actually cloning/starting | High-confidence check | Orphan CTs on every wizard run; pollutes the pool (Pitfall 9) | Never — validation must be read-only |
| Wizard surfaces raw `proxmoxer` errors/UPIDs/`zfspool` | Less mapping code | Breaks the ComputeProvider seam; un-CI-provable over the Fake (Pitfall 10) | Never — map to neutral DTOs |
| Token round-tripped through wizard data/logs | Simple "show config" UX | Powerful credential leaked (Pitfall 3) | Never — write-only, redacted |
| Verify cosign/attestation by tag, trust exit-0 | One-line check | Verifies the wrong artifact / passes on failure (Pitfall 12/13) | Never — by digest, assert on output |
| Flip harden-runner to block before audit telemetry | "Hardened sooner" | Silently breaks publish/build/signing (Pitfall 14) | Never — audit-first is mandatory |
| Scrollback "restored after reboot" via multiplexer only | Simple promise | Impossible (RAM wiped); broken promise (Pitfall 8) | Never — distinguish reconnect vs reboot; disk-log for cross-reboot |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| proxmoxer (real vs Fake) | Assuming sync returns + Fake-shaped errors | Poll UPIDs to `OK`; mock real `ResourceException` shapes in an integration tier (Pitfall 1) |
| Proxmox privsep token | Grant role to user only; omit `VM.Snapshot`; ignore `SDN.Use` | Grant to user AND token; add `VM.Snapshot` iff snapshots used; verify via `--token` `/access/permissions` (Pitfall 4) |
| Unprivileged LXC persistence | `pct suspend`/resume | `pct stop`→`pct start` (disk survives, process restarts) (Pitfall 5) |
| LXC snapshots | Snapshot on `dir`/thick-LVM storage; no prune | Require zfspool/lvmthin; cap snapshots/workspace; monitor thin-pool fill — or skip snapshots entirely (Pitfall 6) |
| Static-IP resume | Assume static IP = always reachable | Static IP avoids DHCP races, not stale ARP; bounded retry + gratuitous ARP on resume (Pitfall 7) |
| ttyd + multiplexer | `exec claude` (no detach); multi-tab mirroring; default history-limit | ttyd wraps `tmux new -A -s burrow`; single-client policy; raised history-limit (Pitfall 8) |
| PVE token in wizard | Logged / echoed in envelope / committed | Write-only to gitignored 0600 `.env`; redaction filter; `git check-ignore` guard (Pitfall 3) |
| Wizard ↔ ComputeProvider | Leak Proxmox vocabulary into wizard API/UI | Provider-neutral capability DTOs; Fake satisfies the contract; extend seam-leakage test (Pitfall 10) |
| cosign keyless verify | By tag; wrong/narrow identity regex; case mismatch | By `@sha256:` digest; documented identity+issuer; lowercase GHCR vs cased GitHub URL is expected (Pitfall 12) |
| GitHub release publish | Missing `id-token`/`attestations: write`; GITHUB_TOKEN tag no-trigger; trust exit-0 | Exactly the 4 perms; confirm `release.yml` fired / retrigger; assert on verify output (Pitfall 13) |
| harden-runner block | Guess the allowlist | Derive from first-run audit telemetry; pre-seed Fulcio/Rekor/TUF/GHCR/Trivy-DB; re-run green (Pitfall 14) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| PVE token leaked via wizard logs/envelope/git | Powerful clone/destroy credential exposed = worker-pool compromise | Write-only token, redaction filter, gitignore guard, no token in `error.message` (Pitfall 3) |
| Token over-broad (`root@pam`/`PVEAdmin`) for wizard convenience | Control-plane compromise = full-cluster compromise | Keep the scoped 9/10-priv role; wizard validates, never widens (Pitfall 4) |
| Wizard creates/widens the PVE user/role/token "to be helpful" | Burrow holds privilege-granting power; violates least-priv design | Wizard validates a provided token + guides the operator-run kit; never self-provisions PVE identity |
| Snapshot/persistence data on shared thin pool fills the node | Node-wide write outage (not just Burrow) | Cap + prune snapshots; monitor thin-pool; prefer plain stop/start (Pitfall 6) |
| Verifying supply-chain artifacts by tag / trusting exit-0 | A tampered/wrong artifact passes verification | Verify by digest, assert on output, both images independently (Pitfall 12/13) |
| Drop to privileged LXC to "fix" suspend/persistence | Loses the unprivileged security boundary for untrusted agent code | Stay unprivileged + nesting=1; redesign persistence as stop/start (Pitfall 5) |

## "Looks Done But Isn't" Checklist

- [ ] **Persistence (WSX-02):** Often missing the reaper carve-out — verify a `stopped` persistent workspace SURVIVES a reconcile pass (negative control in H17). Disk must be intact on `start`.
- [ ] **Persistence mechanism:** Often built on suspend — verify it's `pct stop`/`start` (disk survives, process restarts), not CRIU suspend that 403s/errors on the real unprivileged CT.
- [ ] **Snapshots (if used):** Often missing the storage-backend gate — verify the rootfs storage is zfspool/lvmthin (snapshot fails on `dir`), and snapshots are capped/pruned (no thin-pool fill).
- [ ] **Scrollback (WSX-03):** Often promises cross-reboot history — verify reconnect (same boot) shows history AND stop/start shows fresh-but-files-intact; multi-tab doesn't mirror/shrink.
- [ ] **Wizard token:** Often leaks — verify the token appears in NO log sink, NO envelope `data`/`error`, and `.env` is gitignored (post a token, grep every sink).
- [ ] **Wizard validation:** Often auth-only — verify `compute: ok` asserts the SPECIFIC privileges + template + storage exist (privsep `--token` read), not just that the token authenticates.
- [ ] **Wizard validation:** Often destructive — verify validation leaves NO orphan CT (read-only checks; the "first workspace" step uses the compensating create saga).
- [ ] **Wizard seam:** Often leaks Proxmox vocabulary — verify the wizard API/UI use neutral DTOs and the Fake provider satisfies the wizard contract (seam-leakage test extended).
- [ ] **Token privileges:** Often missing `VM.Snapshot` (if snapshots) / `SDN.Use` — verify the role on real infra via `pvesh get /access/permissions --token …`.
- [ ] **First cosign verify:** Often by tag / wrong identity — verify by `@sha256:` digest with the documented identity+issuer; both images.
- [ ] **Publish perms:** Often missing a scope — verify the publish job has exactly `contents:read packages:write id-token:write attestations:write`; keyless signing actually ran.
- [ ] **Tag→release chain:** Often silently doesn't fire — verify `release.yml` actually ran for the tag (GITHUB_TOKEN suppression) and produced GHCR images by digest.
- [ ] **harden-runner block-flip:** Often breaks signing — verify post-flip re-runs of all 5 jobs stay green (Fulcio/Rekor/TUF/GHCR/Trivy-DB allowed).
- [ ] **Fake-vs-real:** Often "passed CI" hides it — verify the snapshot/start/stop paths were written against real-shaped proxmoxer responses, not just the Fake.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Reaper destroyed a persistent workspace (Pitfall 2) | HIGH (data lost) | The disk is gone — recover from any backup; add the `no owning row` only rule + negative-control test so it can't recur; this is why the test is a phase gate |
| Token leaked via wizard (Pitfall 3) | HIGH | Rotate the PVE token immediately (mint a new one, update `.env`); scrub logs/event rows/git history; add the redaction filter + gitignore guard |
| Built persistence on suspend (Pitfall 5) | MEDIUM | Redesign WSX-02 as stop/start (disk-preserving); drop CRIU; re-test H9 step 3→4 on real CT |
| Snapshot sprawl filled the thin pool (Pitfall 6) | MEDIUM/HIGH | Prune old snapshots to free blocks; add a per-workspace cap + thin-pool monitor; consider dropping snapshots for plain stop/start |
| Wizard left orphan CTs (Pitfall 9/11) | LOW (with reaper) | The reaper reaps row-less orphans; make wizard validation read-only and the first-workspace step use the compensating saga |
| cosign/attestation verify won't pass (Pitfall 12/13) | LOW | Inspect the real cert identity with a catch-all regex, derive the known-good command, pin it; verify by digest; check the 4 publish perms |
| release.yml didn't fire on the tag (Pitfall 13) | LOW | `gh workflow run release.yml --ref vX.Y.Z` or push a fresh tag under a GitHub App token |
| harden-runner block broke publish (Pitfall 14) | LOW | Revert to audit, collect the missing endpoints from insights, add to allowlist, re-flip; pre-seed Fulcio/Rekor/TUF/GHCR/Trivy-DB |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Fake-vs-real proxmoxer gap | Mocked-proxmoxer integration tier (pre-P12), surfaces P12 | Integration tier returns real-shaped UPIDs + `ResourceException`; H8/H9 on real infra |
| 2. Reaper destroys persistent workspace | **P11** (with negative-control test as gate) | Reconcile pass leaves a `stopped` persistent workspace untouched; H17 with negative control |
| 3. PVE token leak via wizard | **P10** | Post-token test: token in no log sink / no envelope; `.env` gitignored |
| 4. Token ACL too broad/narrow (privsep, VM.Snapshot, SDN.Use) | P0-kit + P10 (driven by P11) | `pvesh … --token /access/permissions` shows scoped privs incl. snapshot iff used; first real create succeeds |
| 5. Unprivileged suspend/CRIU broken | **P11** (design decision) | WSX-02 is stop/start; real CT stop→start preserves disk (H9 3→4) |
| 6. Snapshot storage/sprawl | P11 (+ P10 health-check) | Storage-backend gate; snapshot cap/prune; thin-pool monitored — or no snapshots |
| 7. Resume race + stale ARP | **P11** | In-flight lock; reconciler skips in-flight; resume reachability retry; H9 step 4 reliable |
| 8. Scrollback reconnect-vs-reboot + multiplexer | **P11** (template/boot) + P10/P11 UI copy | Reconnect shows history; stop/start fresh-but-files; no multi-tab mirror; history-limit bounded |
| 9. Wizard validation destructive/misleading-green | **P10** | Read-only validation (no orphan); capability-asserting health-check |
| 10. Wizard leaks Proxmox past the seam | **P10** | Neutral DTOs; Fake satisfies wizard contract; seam-leakage test extended |
| 11. Wizard partial-provision/resume | **P10** | Re-enter wizard derives status from ground truth; first-workspace reuses compensating saga |
| 12. First cosign keyless verify | **P13** | `cosign verify` by digest with documented identity+issuer; both images; command pinned in runbook |
| 13. Publish perms / tag-retrigger / verify exit-0 | **P13** | 4 perms present; `release.yml` confirmed fired; verify asserts on output; both SBOMs |
| 14. harden-runner block-flip | **P13** (after audit telemetry) | Post-flip re-run of all 5 jobs green; signing still works |
| 15. release-please version surprise / no prior live run | **P13** | Version seed reconciled before merge; tag→publish chain confirmed end-to-end; base-image-CVE contingency |

## Sources

- **Burrow internal (authoritative):** `docs/test-it-out-checklist.md` (H1–H19 homelab gates, CD-1–CD-10 release/verify, the Gotchas section — privsep `--token` check, GITHUB_TOKEN tag-retrigger, lowercase-GHCR-vs-cased-GitHub-URL, audit-first harden-runner, 4 publish perms, two-SBOM requirement); `.planning/research/PROXMOX-PRIMING.md` (9-priv role, privsep intersection, thin-storage/`--full`, static-IP-from-VMID, no-`pct`-over-API/pull-at-boot); `.planning/research/PITFALLS.md` (v1.0 substrate: UPID polling, VMID race, ttyd framing, WS teardown); `.planning/PROJECT.md` (v1.3 scope, wizard "validate not self-provision" invariant, ComputeProvider seam); `docs/ci-cd-and-testing.md` §4.4 (Fake-in-CI), §5.4–5.5 (cosign/SLSA/perms/harden-runner); `docs/tech-spec.md` (ttyd `--once`, persistence open Qs).
- **Proxmox VE 8.x (verified 2026):** [Unprivileged LXC suspend/CRIU "can't dump nested namespace" — Proxmox forum](https://forum.proxmox.com/threads/can-not-suspend-lxc.34507/) and [CRIU on stock Proxmox containers](https://github.com/checkpoint-restore/criu/issues/1430); [LXC snapshots require zfspool/lvm-thin, `dir` unsupported — Proxmox forum](https://forum.proxmox.com/threads/lxc-container-snapshot-problem.155180/); [User Management / privileges / tokens / privsep](https://pve.proxmox.com/wiki/User_Management); [Storage (snapshot support, thin pools)](https://pve.proxmox.com/wiki/Storage).
- **Sigstore / cosign (verified 2026):** [cosign verify (keyless identity+issuer flags required)](https://github.com/sigstore/cosign/blob/main/doc/cosign_verify.md); [Verifying Signatures — Sigstore docs](https://docs.sigstore.dev/cosign/verifying/verify/); [cosign keyless requires `--certificate-identity(-regexp)` + `--certificate-oidc-issuer` — issue #3671](https://github.com/sigstore/cosign/issues/3671).
- **GitHub attestations / gh (verified 2026):** [`gh attestation verify` (`--owner`, `--predicate-type`, `oci://`)](https://cli.github.com/manual/gh_attestation_verify); [`gh attestation verify` exit-0-on-failure footgun — cli/cli#10418](https://github.com/cli/cli/issues/10418); [Configure GitHub Artifact Attestations — GitHub blog](https://github.blog/security/supply-chain-security/configure-github-artifact-attestations-for-secure-cloud-native-delivery/).

---
*Pitfalls research for: Burrow v1.3 "Go Live" — first real-Proxmox bring-up + setup wizard + workspace persistence + first GHCR/cosign release*
*Researched: 2026-06-24*
