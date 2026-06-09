<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Proxmox Host Priming — Day-0 Operator Spec

**Researched:** 2026-06-09
**Status:** Day-0 priming spec. Synthesizes three verified research blocks (role/auth +
node-exec, host prerequisites, control-plane + kit + runbook). Reconciles their
contradictions and flags remaining open decisions as ADR candidates.
**Confidence:** HIGH on all `pveum`/`pct`/`pveam`/`pvesh` syntax, privilege identifiers,
storage content-type rules, firewall defaults, privsep semantics, and the
"`pct exec`/`pct push` are not exposed by the HTTPS API" finding — all verified against
current (2026) Proxmox VE 8.x documentation, not training data. MEDIUM where noted
(storage sizing math, `/cluster/options --next-id` bounds, `/pool` ACL membership nuance).

> **Why this doc exists.** The tech-spec assumes a primed Proxmox host (a `burrow@pve`
> token, a golden template at the configured VMID, a rootfs storage, a static-IP plan)
> but never spells out the one-time operator steps that produce them. Burrow's runtime
> (`ProxmoxComputeProvider`) *consumes* all of this; it never creates it. This closes the
> gap the operator surfaced: "what about the setup scripts the operator runs on their
> Proxmox to prime it for use?"

> **Topology placeholders.** Per the security posture, no real hostnames, node names, IPs,
> or VMIDs appear here. Placeholders: `<pve-host>`, `<node>`, `<bridge>` (e.g. the LAN
> bridge), `<subnet>`, `<gw>`, `<rootfs-storage>`, `<tmpl-storage>`, `<template-vmid>`,
> `<pool-start>`–`<pool-end>` (worker VMID range), `<control-plane-host>`. The committed
> kit ships these as placeholders; the operator fills their own LAN values into the
> gitignored `.env` and the `30-network-notes.md` decision record.

---

## 1. The single biggest finding: there is no API for `pct exec` / `pct push`

**Verified:** `pct exec` and `pct push` are **node-local CLI commands only** — they are
**not** exposed by the Proxmox HTTPS REST API. Unlike QEMU VMs (which expose
`/nodes/{node}/qemu/{vmid}/agent/exec` via the guest agent), **LXC containers have no
exec / push / file-write API surface.** `proxmoxer`, being a thin HTTPS wrapper over that
API, therefore **cannot** write `/etc/burrow/worker.env` into a container through any
provider method. (Confirmed on the Proxmox forum: "There is no API endpoint for executing
commands in LXC containers — `pct exec` and `pct push` are CLI only.")

This collides with the current spec/requirements, which assume injection via
`pct exec`/`pct push` (REQUIREMENTS **WORK-03**, ROADMAP **SC-4**, ARCHITECTURE
"injectBootConfig"). That assumption silently requires a mechanism that exists only on the
node's shell — not over the API the control plane actually speaks. **This is a real gap
that must be resolved by an ADR before Phase 1.**

### Three ways to close it

| Option | Mechanism | API-only? | New trust channel? | Keeps `ComputeProvider` seam clean? |
|---|---|---|---|---|
| **A. SSH-to-node push** | Control plane SSHes to `<node>` as a restricted key, runs `pct push` | No (needs SSH) | Yes — a second, root-gated channel | No — re-introduces node coupling |
| **B. Pull-at-boot (RECOMMENDED)** | Worker `curl`s its own non-secret config from a new control-plane internal endpoint at boot; secrets fetched short-lived and discarded | Yes (pure HTTP) | No | Yes — `injectBootConfig` becomes a DB write |
| **C. API-only injection** | No API path writes an arbitrary file into a CT rootfs; only `net0`/static-IP is API-settable | n/a | n/a | n/a — does not solve env injection |

**Recommendation: adopt Option B (pull-at-boot).** It is the only choice that (a) needs
zero node-local CLI, (b) keeps the `ComputeProvider` honest — `injectBootConfig` becomes
"persist intent to the DB," which the `FakeComputeProvider` no-ops trivially, (c) keeps
secrets out of any worker-readable surface (PITFALLS #13), and (d) requires no second SSH
trust channel and no expansion of the Proxmox role.

**What Option B changes:**

- `injectBootConfig` is a **DB write**, not a node command. The worker, knowing its own
  VMID from its hostname/static IP, calls a new internal endpoint:
  `GET /api/v1/internal/bootconfig/{vmid}` → returns the per-workspace, **non-secret**
  identifiers (`CONFIG_REPO`, `CONFIG_BRANCH`, `PROJECT_REPO`, `PROJECT_BRANCH`) the
  control plane already holds in SQLite.
- Secrets (git deploy tokens) **never travel through any injected env**. The worker
  requests a **short-lived, repo-scoped** credential from the same endpoint at boot, uses
  it for `git clone`, and discards it — it is never written to `/etc/burrow/worker.env`.
- `burrow-boot.sh` **pulls** its config (one bounded, retried HTTP call) instead of
  **receiving** it. The control plane must be reachable from the worker subnet — it
  already is (the WS terminal proxy reaches the worker, and the worker reaches
  `CONFIG_REPO` on the internet).

**Reserve Option A (restricted SSH key) as a fallback only** if a future requirement forces
writing a file into the container filesystem before first boot that the worker cannot fetch
over HTTP. If adopted, it is mandatory to: SSH as `root@pam` (since `pct` needs root),
lock the public key with a forced command and `restrict`, and have the wrapper validate the
VMID is in `[<pool-start>, <pool-end>]` and reject everything else:

```
restrict,command="/usr/local/sbin/burrow-inject" ssh-ed25519 AAAA... burrow-control-plane
```

The wrapper reads `$SSH_ORIGINAL_COMMAND`, allowlists the VMID, size-limits stdin, blocks
shell metacharacters, and only ever runs `pct push <vmid> <tmpfile> /etc/burrow/worker.env`.

> **ADR candidate #1 (highest priority): "LXC boot-config injection."** Record the
> no-`pct`-over-API finding and decide **Option B (pull-at-boot)**. This rewrites WORK-03 /
> SC-4 / SC-5 and adds the `GET /api/v1/internal/bootconfig/{vmid}` contract to the API
> spec + a pull step to `burrow-boot.sh`.

---

## 2. Least-privilege role + token recipe

### 2.1 Reconciled privilege set

The three research blocks proposed slightly different privilege lists. Reconciliation, with
rationale per disputed privilege:

| Privilege | Verdict | Why |
|---|---|---|
| `VM.Audit` | **Include** | Read CT status/config (capacity scan, state machine reads) |
| `VM.Clone` | **Include** | Clone golden template → worker |
| `VM.Allocate` | **Include** | Create **and destroy** the worker CT (remove uses the same priv as create) |
| `VM.Config.Network` | **Include** | `pct set -net0` static IP at clone |
| `VM.Config.Options` | **Include** | Set general/feature options on the clone |
| `VM.PowerMgmt` | **Include** | Start / stop / shutdown lifecycle |
| `Datastore.AllocateSpace` | **Include** | Allocate the clone's rootfs volume on the pool storage |
| `Datastore.Audit` | **Include** | Read/browse storage; some PVE versions emit this check alongside `AllocateSpace` during clone (prevents a 403 class) |
| `Sys.Audit` | **Include** | Read node status/RAM for the capacity guard + task (UPID) status |
| `VM.Config.Disk` | **Exclude** | Burrow never resizes/adds disks post-clone. (Block B included it for "rootfs config on the clone," but with `--full` the rootfs is copied from the template; no disk edit occurs. Add only if a concrete clone-time disk edit appears.) |
| `VM.Config.CPU` / `VM.Config.Memory` | **Exclude** | Clone copies the template's sizing; Burrow does not resize cores/RAM at create. (Block C included these speculatively.) |
| `VM.Console` | **Exclude** | The terminal path is ttyd over the worker's LAN address, not the Proxmox console API. |
| `Pool.Audit` | **Optional** | Only if the capacity/allocation scan reads pool membership. Cheap; include if you adopt the `/pool` scoping model below. |
| `SDN.Use` (on the bridge) | **Conditional** | Required on modern PVE 8.x **only if SDN permission enforcement is on**. On a plain Linux-bridge homelab the check may not fire; grant it on the bridge to be safe — it is the single most-missed privilege for "set network on a clone." |
| `Pool.Allocate` | **Exclude** | Means "create/modify/remove a *pool*," **not** "clone into a pool." Burrow does not manage pools. (Corrects the spec draft.) |
| `Datastore.Allocate` | **Exclude** | Means "create/remove a *datastore*" — far too broad. |
| `Sys.Modify`, `Sys.PowerMgmt`, `Permissions.Modify`, `Realm.*`, `VM.Migrate`, `VM.Backup`, `VM.Snapshot`, `VM.GuestAgent.Unrestricted` | **Exclude** | None are needed for ephemeral clone-and-destroy workers. |

**Authoritative minimal role (9 privileges, + conditional `SDN.Use`):**

```
VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt \
Datastore.AllocateSpace Datastore.Audit Sys.Audit
```

### 2.2 Scoping — least privilege beyond "grant at /"

Granting the role at `/` works but is over-broad on three axes. Scope tighter:

| Privilege subset | Granted at | Caps blast radius to |
|---|---|---|
| `VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt` | `/pool/burrow-workers` | Burrow's own CTs only — a leaked token cannot touch unrelated production guests |
| `VM.Clone VM.Audit` | `/vms/<template-vmid>` | The golden template as a clone source |
| `Datastore.AllocateSpace Datastore.Audit` | `/storage/<rootfs-storage>` | One storage pool, not every datastore |
| `Sys.Audit` | `/nodes/<node>` (per scheduling node) | Per-node status reads; no cluster/HA/Corosync exposure |
| `SDN.Use` (if enforced) | the `<bridge>` / vNet | The one bridge, not global |

`GET /cluster/nextid` needs **no grant** — it works for any authenticated token, so it does
not widen the role. (Note: Burrow does **not** use `/cluster/nextid` for allocation — it is
not race-safe and not range-bounded; see §5.)

> **ADR candidate #2: "Proxmox ACL scoping model."** `/pool/burrow-workers` (tighter, but
> the create path must also add each new VMID to the pool, e.g.
> `pvesh set /pools/burrow-workers -vms <id>`, or pre-add the whole range) **vs** `/vms`
> cluster-wide (simpler, broader). This changes the `ProxmoxComputeProvider.clone` surface
> (whether clone must also touch pool membership). Recommended: `/pool` for a real
> least-privilege fence; record the membership obligation in the ADR.

### 2.3 The privsep nuance (most common silent-403 cause)

With `--privsep 1` (the **default** for new tokens), a token's effective permissions are the
**intersection of the user's and the token's ACLs**. The token can never exceed the user;
granting only the user leaves a privsep token with **zero** effective rights. **Grant the
role to BOTH the user and the token at every path.** This is the single most common reason a
freshly created Burrow token "authenticates but every clone returns 403."

### 2.4 The `pveum` recipe (idempotent; both principals; scoped)

```bash
#!/usr/bin/env bash
set -euo pipefail
USER="burrow@pve"; TOKEN="burrow"
POOL="/pool/burrow-workers"
STORAGE="/storage/<rootfs-storage>"
NODE="/nodes/<node>"                 # repeat per scheduling node
TMPL="/vms/<template-vmid>"
PRIVS="VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt \
Datastore.AllocateSpace Datastore.Audit Sys.Audit"

# 1. Role (delete-then-add keeps privs authoritative; modify is the re-run path)
pveum role list --output-format json | grep -q "\"BurrowProvisioner\"" \
  && pveum role modify BurrowProvisioner --privs "$PRIVS" \
  || pveum role add    BurrowProvisioner --privs "$PRIVS"

# 2. User (no password; token-only)
pveum user list --output-format json | grep -q "\"$USER\"" \
  || pveum user add "$USER" --comment "Burrow control plane (token-only)"

# 3. Pool exists (resource pool fences the worker range)
pveum pool add burrow-workers 2>/dev/null || true
# Add the template + (optionally) the whole worker range to the pool:
#   pvesh set /pools/burrow-workers -vms <template-vmid>

# 4. Token WITH privsep (value prints ONCE — capture into .env, never commit, never log)
pveum user token list "$USER" --output-format json | grep -q "\"$TOKEN\"" \
  || pveum user token add "$USER" "$TOKEN" --privsep 1 --comment "Burrow provisioner"
#  -> full-tokenid = burrow@pve!burrow ; value = <SECRET>  (.env PROXMOX_TOKEN_VALUE)

# 5. Grant role to BOTH user and token at every scoped path (privsep intersects user∩token)
for principal in "--users $USER" "--tokens burrow@pve!$TOKEN"; do
  pveum acl modify "$POOL"    $principal --roles BurrowProvisioner --propagate 1
  pveum acl modify "$TMPL"    $principal --roles BurrowProvisioner
  pveum acl modify "$STORAGE" $principal --roles BurrowProvisioner
  pveum acl modify "$NODE"    $principal --roles BurrowProvisioner
done
# (SDN.Use on <bridge> only if SDN enforcement is on.)
```

> **Simplest get-it-working fallback** (acceptable for a disposable LAN-only token; migrate
> to the scoped form before the token is anything but disposable):
> `pveum acl modify / --users "$USER" --roles BurrowProvisioner` **and**
> `pveum acl modify / --tokens "burrow@pve!$TOKEN" --roles BurrowProvisioner`. Both
> principals are still required under privsep.

> **The token is non-idempotent.** A second `pveum user token add` creates a *second* token
> and **will not re-print the first UUID**. Guard it (the `grep -q || add` above) and, on
> re-run with an existing token, **prompt the operator to rotate or reuse** — do not silently
> churn tokens. This is the one place the kit cannot silently converge; surface it loudly.

---

## 3. Host prerequisites checklist

One-time operator priming, assembled into a re-runnable `prime-host.sh`. Every step is
written **check → act** so a second run is a no-op. Ordering (dependencies):
`0 verify → 1 template image → 2 storage chosen → [build golden template, Phase 0] →
4 features on template → 3 network/DHCP plan → 5 user/role/token/ACLs → 6 residual verifies`.

### 3.0 Pre-flight (verify, do not change)

| Check | Command | Why |
|---|---|---|
| PVE 8.x | `pveversion` | Confirms current command surface (`pveum acl modify`, `--features`, `--next-id`) |
| API reachable on 8006 from the control plane | *(from `<control-plane-host>`)* `curl -sk https://<pve-host>:8006/api2/json/version` | `proxmoxer` talks HTTPS:8006; `verify_ssl=False` matches the self-signed cert |
| Time synced | `chronyc tracking` | PVE 8 ships **chrony** enabled by default — this is a **verify**, not an install. Token auth + TLS are clock-sensitive; clones inherit host time |
| `<bridge>` exists and is the LAN bridge | `ip link show <bridge>` | The static-IP plan (§4) depends on knowing the bridge's subnet — **stop** if absent |

### 3.1 CT template image (Ubuntu 24.04 standard)

```bash
pveam update                                              # refresh appliance DB (idempotent)
pveam available --section system | grep ubuntu-24.04-standard   # discover exact name
TMPL="ubuntu-24.04-standard_<ver>_amd64.tar.zst"          # pin exact build string
pveam list <tmpl-storage> | grep -q "$TMPL" || pveam download <tmpl-storage> "$TMPL"
```

- The `vztmpl` content type is supported **only by `dir`-type storage** (lands in
  `/var/lib/vz/template/cache/` for `local`). `lvmthin`/`zfspool`/`lvm` carry
  `rootdir`/`images` only — so the **template cache and the worker rootfs generally live on
  different storages**.
- `pveam download` is privileged but **non-destructive** (adds a file). Pin `$TMPL` to the
  exact build so a re-download can't silently swap versions.

### 3.2 Storage for the worker rootfs pool

| Type | `rootdir`? | Thin? | Fit for `--full` ephemeral pool |
|---|---|---|---|
| `lvmthin` | yes | **yes** | **Recommended** — full clones are thin; only written blocks consume space |
| `zfspool` | yes | **yes** | Recommended — thin + compression |
| `dir` (qcow2) | yes | yes | Workable; slower, file-on-filesystem |
| `lvm` (thick) | yes | **no** | **Avoid** — every `--full` clone reserves the full rootfs up front |

- **The `--full` tie-in:** cloning from a CT *template* defaults to a **linked clone**; pass
  `full=1` for independent ephemeral workers whose `destroy` actually frees space. On
  thin storage a full clone is copy-on-write-thin (cheap); on **thick LVM** each clone
  physically reserves the full rootfs (the trap — do not run the pool on thick LVM). Budget
  the longer full-clone time into the **UPID wait**, not the ttyd health timeout.
- **Sizing (MEDIUM):** on thin storage, budget actual per-worker divergence (apt cache,
  `node_modules`, cloned project, Claude state), not `count × full-rootfs`. The **real
  limiter is RAM** (capacity guard at the node-RAM threshold caps concurrency long before
  disk does). **Monitor thin-pool fill** — an over-committed pool that fills is a hard
  outage.
- Inspection (`pvesm status`) is read-only. **Creating/resizing a pool is privileged and
  destructive** — keep it out of the re-runnable path; do it as a deliberate admin action.

### 3.3 Template features: unprivileged + nesting

```bash
pct config <template-vmid> | grep -E 'unprivileged|features'   # read (idempotent)
pct set <template-vmid> --features nesting=1                    # re-runnable no-op if set
# unprivileged is set at CREATE time (--unprivileged 1; default for `pct create` is 1).
```

- `nesting=1` exposes procfs/sysfs so **systemd** (`burrow-worker.service`) and Node's
  sandboxing work correctly inside an unprivileged CT. **No host-side change is required** —
  the backend translates it to `lxc.apparmor.allow_nesting=1` automatically.
- **Reject the "Docker-in-LXC needs `keyctl`/`fuse`/unconfined AppArmor / privileged"
  advice** — Burrow runs Node + Claude + systemd, **not** Docker. Stay **unprivileged +
  `nesting=1`** (the secure choice). Never drop to privileged to paper over a permission
  error. Clones inherit the template's `features`, so set it **once** on the template.

### 3.4 Firewall (resolves reachability, PITFALLS #5)

- The Proxmox firewall is **disabled by default at all levels**; VM/CT `enable` defaults to
  **0**. Out of the box nothing blocks control-plane → worker `:7681` (ttyd) or
  control-plane → `:8006` (API).
- **Conditional prerequisite:** if the operator later enables the PVE firewall, `:8006` is
  auto-permitted (default management rule), but control-plane → worker `:7681` needs an
  **explicit allow** on the CT (or a security group applied to the pool). Enabling the
  firewall is a privileged, connectivity-affecting change — keep it out of the default
  priming path; if adopted, add the `:7681` allow in the same change.

### 3.5 Residual one-time prerequisites

| Prerequisite | Action | Notes |
|---|---|---|
| Self-signed cert | none on host | Control plane uses `verify_ssl=False` (v1) — document, don't "fix" |
| Golden template exists + is **template-marked** | `pct config <template-vmid>`; confirm `template:` flag (`pct template <vmid>` converts it) | Linked-clone-default applies only to template-marked CTs |
| Host packages | none beyond stock PVE | `pveam`/`pct`/`pvesh`/`pveum` ship with PVE. No cloud-init host package (LXC has none). No `qemu-guest-agent` (VM-only; irrelevant to LXC — this is *why* static-IP-from-VMID is the design) |

---

## 4. Static-IP-from-VMID scheme (SC-6)

Static-IP-from-VMID is the safer default: unprivileged LXC has no guest agent and the
interfaces API is unreliable for DHCP leases, so Burrow **computes** the IP from the VMID and
knows the address the instant a VMID is allocated — no polling, no race. A VMID collision
*is* an IP collision, so the DB unique constraint on `vmid` guards both.

**The scheme (operator records their LAN values in `30-network-notes.md`):**

- Worker VMID pool is `[<pool-start>, <pool-end>]`. Map `VMID → <subnet>.<last-octet>`
  (e.g. with a `/24` LAN, worker `2NN` → `<subnet>.2NN/24`, gateway `<gw>`, bridge
  `<bridge>`).
- **Reserve the worker IP range out of the DHCP server's pool** (router/pfSense/dnsmasq —
  **off-host**, no Proxmox command). If DHCP can hand out a worker IP, a worker boot causes a
  LAN conflict. This off-host reservation is the load-bearing collision-avoidance step.
- Keep the template and the control plane on addresses **outside** the worker range.

**Applied at clone time (runtime, not priming — needs `VM.Config.Network`):**

```bash
pct set <vmid> -net0 name=eth0,bridge=<bridge>,ip=<subnet>.<oct>/<prefix>,gw=<gw>
```

`ip=` takes CIDR; `gw=` is a bare gateway IP. Documented here so §2's `VM.Config.Network`
scoping is justified; the per-clone `pct set` itself runs inside the create saga.

> **ADR candidate #3: "Static-IP-from-VMID."** Record the scheme, the VMID→IP formula, and
> the off-host DHCP-exclusion obligation. (Already an ARCHITECTURE decision; the ADR pins the
> LAN-specific contract.)

---

## 5. VMID allocation (host-side facts that constrain the control plane)

- **`pvesh get /cluster/nextid` is NOT race-safe and NOT range-bounded** — verified
  "multiple calls got the same VMID." Burrow must **not** use it for allocation.
- Burrow's `getNextVmId` must be **bounded to `[<pool-start>, <pool-end>]`**, **exclude the
  template VMID**, union DB-known VMIDs with actual Proxmox VMIDs (`/cluster/resources`), and
  pick the first free in-range id under a lock — backed by a DB **unique reservation** on
  `vmid` (partial index excluding soft-deleted rows). (This is already WS-10 / SC-3.)
- *(Optional, PVE 8.x, MEDIUM)* `pvesh set /cluster/options --next-id lower=<start>,upper=<end>`
  steers the GUI/`nextid` default but is still not race-safe — treat as cosmetic.
- There is **no hard "reserve a VMID range" mechanism** in Proxmox; the range is convention,
  made real by the bounded scan + DB unique reservation + the `/pool` ACL fence (§2.2).

---

## 6. Proposed priming-kit file set in `cc-worker-config`

The spec's `lxc/` tree has `control-plane/` and `worker-template/` but **no operator-facing
ordering**. Add a numbered `lxc/host-prime/` as the ordered entry point, plus `PRIMING.md`
(the Day-0 runbook). Numeric prefixes encode the hard dependency chain.

```
cc-worker-config/
├── PRIMING.md                          # NEW — the Day-0 runbook (human reads first)
└── lxc/
    ├── host-prime/                     # NEW — ordered operator scripts, run on the Proxmox host
    │   ├── lib/common.sh               #   shared strict-mode + preflight + guard helpers
    │   ├── 00-api-user-role.sh         #   pveum: burrow@pve user + BurrowProvisioner role + scoped ACL + token (§2)
    │   ├── 10-template-download.sh     #   pveam update/available/download Ubuntu 24.04 CT template (§3.1)
    │   ├── 20-create-template.sh       #   wraps worker-template/create-template.sh + provision + `pct template` (§3.3)
    │   ├── 30-network-notes.md         #   NOT a script — the static-IP/VMID/subnet decision record (§4)
    │   └── 40-control-plane.sh         #   provision the control-plane box (§7)
    ├── control-plane/                  # spec §4.2 — control-plane spec/config artifacts
    ├── worker-template/                # spec §4.2 — create-template.sh, provision-template.sh
    ├── systemd/  nginx/  plugins/  claude/   # spec §4.2
```

| Step | Script | Runs on | Produces | Depends on |
|---|---|---|---|---|
| 00 | `00-api-user-role.sh` | any node (`root@pam`) | user, role, scoped ACL, **token (printed once)** | bare cluster |
| 10 | `10-template-download.sh` | template's node | Ubuntu 24.04 CT template in `<tmpl-storage>` | 00 (or root) |
| 20 | `20-create-template.sh` | template's node | golden template CT, `pct template`-converted | 10 |
| 30 | `30-network-notes.md` | (read) | recorded static-IP scheme for the LAN | — (before 40 + Phase 1) |
| 40 | `40-control-plane.sh` | `<control-plane-host>` | running `burrow.service` + nginx + `.env` (token from 00) | 00, 20, 30 |

`30` is deliberately a **markdown note, not a script** — the static-IP scheme is a decision
the operator records for their LAN (placeholders only in the repo), not something to
automate.

### Idempotency & safety contract (shared `lib/common.sh`)

- **Strict mode line 1:** `set -euo pipefail`; `IFS=$'\n\t'`; an `ERR` trap that prints the
  failing line. `pipefail` matters because steps pipe `pveam available | grep` and
  `pvesh get | jq`.
- **Preflight before any mutation:** `require_root`, `require_cmd pveum pct pveam pvesh`,
  `require_node <node>` — a wrong-host run aborts having changed nothing.
- **Idempotency (check → act):** `user list | grep || add`; role `add || modify`;
  `pct status || pct create`; `install -d`/`ln -sf`/`install -m` are idempotent; `acl modify`
  re-asserting is a no-op. **The token is the one non-idempotent resource** — guard it and
  prompt on re-run.
- **Confirmation prompts for destructive steps:** removing the nginx default site,
  destroying a pre-existing template VMID on re-run, overwriting an existing `.env` —
  each requires a typed `yes`.
- **No secrets echoed/committed:** `umask 077`; `read -rsp` (silent) for the token;
  `{ set +x; } 2>/dev/null` around the secret write; never pass the token as a CLI arg
  (visible in `ps`/history); `.env` ends `0600 burrow:burrow`; the kit refuses to write
  `.env` unless `git check-ignore .env` passes; `gitleaks` is the backstop.
- **Reversal block per script** (user/role/token removal; `pveam remove`; `pct destroy`;
  `systemctl disable --now` + `rm -rf /opt/burrow` while **preserving `/data`**).

---

## 7. Control-plane host prep (`40-control-plane.sh`)

The control plane is best run as its **own dedicated unprivileged LXC** (or small VM) —
Ubuntu 24.04, **not** cloned from the worker template, **not** ephemeral. The one persistent
box. Matches the spec's `burrow.service` paths.

- **Service account:** `id -u burrow || useradd --system --create-home --home-dir /opt/burrow
  --shell /usr/sbin/nologin burrow` — a non-login account that owns `/opt/burrow` and `/data`
  and nothing else.
- **Layout:** `/opt/burrow/{api,ui/dist,venv,.env,.env.example}`,
  `chown -R burrow:burrow /opt/burrow`, `.env` is `chmod 600`.
- **State dir:** `install -d -o burrow -g burrow -m 750 /data` (SQLite WAL writes
  `burrow.db{,-wal,-shm}`; the process needs write to the *directory*). Keeping `/data`
  separate from `/opt/burrow` makes it the backup target and survives an app redeploy.
- **Runtime:** Ubuntu 24.04 ships Python 3.12. Install uv, `uv venv /opt/burrow/venv
  --python 3.12`, install from the lockfile. *(Containerized deploy substitutes the
  `Dockerfile.api` image for the venv — support both; state the choice in `PRIMING.md`.)*
- **nginx:** install the spec's site, `rm -f sites-enabled/default` (confirm first),
  `nginx -t && systemctl reload nginx` (validate before reload — a bad config that fails
  `restart` leaves nginx down). Pin `listen` to the LAN interface on a multi-homed host
  (PITFALLS #12).
- **systemd:** `install` the unit, `daemon-reload`, `enable --now burrow.service`. Optional
  hardening: `ProtectSystem=strict`, `ReadWritePaths=/data`, `NoNewPrivileges=yes`,
  `ProtectHome=yes`.
- **`.env` assembly (the secret crux):** `umask 077`; copy `.env.example` → `.env`; fill
  non-secret keys (`PROXMOX_HOST`, `PROXMOX_USER=burrow@pve`, `PROXMOX_TOKEN_NAME=burrow`,
  `TEMPLATE_VMID`, `WORKER_POOL_START/END`, `DEFAULT_NODE`, `DATABASE_PATH=/data/burrow.db`,
  `CONFIG_REPO`) from operator input/placeholders; read the **token** at a hidden prompt
  (`read -rsp`), `{ set +x; }` around the write, `printf` (never `echo`), `unset`, leave
  `0600 burrow:burrow`. The token came from step 00, printed **once** and unrecoverable.

> **`.env.example` note:** keep `burrow@pve` + token name; add a comment that the token must
> be `privsep=1` and granted its own ACL (the §2.3 nuance).

---

## 8. The ordered Day-0 runbook (`PRIMING.md`)

Fresh operator, bare Proxmox cluster → first workspace. All placeholders.

```
PRECONDITIONS (operator confirms; runbook checks)
  P1  PVE cluster reachable; you have root@pam on a node.
  P2  A CT-rootfs storage exists (thin: lvmthin/zfspool) AND a vztmpl (dir) storage.
  P3  The LAN bridge <bridge> exists on the LAN the control plane shares.
  P4  DNS/host entry for the control-plane box.
  P5  cc-worker-config cloned on the node; .env is gitignored in burrow.

STEP 0 — Identity & least privilege          [host-prime/00-api-user-role.sh]
  Run as root@pam. Creates burrow@pve, BurrowProvisioner role (verified privs),
  pool-scoped ACL to BOTH user and token, and the API token.
  >>> COPY THE TOKEN UUID NOW — shown exactly once, unrecoverable. <<<
  GATE: `pvesh get /access/permissions --token "burrow@pve!burrow=<uuid>"` shows
        pool/storage/node-scoped rights only — and NOTHING on out-of-pool VMIDs.

STEP 1 — Network decision                    [host-prime/30-network-notes.md]
  Record the static-IP-from-VMID scheme for YOUR LAN: VMID -> <subnet>.<oct>,
  gw <gw>, bridge <bridge>, pool <pool-start>-<pool-end>. Reserve that IP range
  OUT of DHCP. Single source of truth for `pct set net0` AND the control plane's
  IP computation. (ADR candidate #3.)

STEP 2 — Golden template                     [host-prime/10- then 20-]
  10: pveam download Ubuntu 24.04 CT template.
  20: pct create <template-vmid> (unprivileged 1, features nesting=1), provision
      inside, `pct template`.
  GATE (manual, Phase 0): clone once by hand with --full, start, confirm ttyd
       comes up on the LAN interface and `claude` launches. Destroy the test clone.

STEP 3 — Control plane                        [host-prime/40-control-plane.sh]
  burrow user, /opt/burrow + /data, uv venv, nginx site, burrow.service. Assemble
  .env; paste the STEP-0 token at the hidden prompt (never echoed; .env 0600).
  GATE: `curl http://127.0.0.1:8000/api/v1/health` -> db: ok, compute: ok.
        compute:ok proves the token + scoped ACL actually authenticate.

STEP 4 — First workspace (the real acceptance gate)   [LAN browser smoke]
  create  -> pick a small repo + branch, submit
  live    -> terminal panel shows an interactive, resizable claude session
  stop    -> status stopped, LXC stopped, disk preserved
  start   -> status running, terminal reconnects to the SAME session
  destroy -> LXC gone, VMID freed, row soft-deleted
  ACCEPTANCE: all five succeed end-to-end against real Proxmox. This is the
  Definition-of-Done for "Burrow can create its first workspace" and validates
  UPID waits, static-IP reachability, the ttyd subprotocol bridge, and saga
  compensation in one operator-visible pass.
```

Each earlier gate **localizes failure** so the five-step smoke test, when it fails, fails for
a workspace-logic reason — not an over/under-scoped token or a ttyd bound to `lo`.

### Operator verification commands (run from `<control-plane-host>` with the token)

```bash
export PVE_TOKEN='burrow@pve!burrow=<uuid>'           # from .env
api(){ curl -sk -H "Authorization: PVEAPIToken=$PVE_TOKEN" "https://<pve-host>:8006/api2/json$1"; }
api /cluster/nextid                                   # token auth (401 = bad token)
api /nodes/<node>/status                              # 403 = missing Sys.Audit at /nodes/<node>
api /nodes/<node>/lxc/<template-vmid>/config          # can see the template (VM.Clone/Audit)
api /nodes/<node>/lxc/<out-of-pool-vmid>/config       # NEGATIVE: expect 403 if scoped to /pool
pvesh get /access/permissions --token "$PVE_TOKEN"    # authoritative scope check (catches privsep mistake)
```

`pvesh get /access/permissions --token ...` prints exactly which paths/privs the **token**
resolves to after the user∩token intersection — the fastest way to catch "granted the user
but not the token."

---

## 9. Reconciled contradictions across the three research blocks

| Topic | Block A | Block B | Block C | Reconciled decision |
|---|---|---|---|---|
| Boot-config injection | Pull-at-boot (no `pct` over API) | Assumes `pct exec`/`pct push` | Assumes `pct push`/`pct exec` | **Pull-at-boot (Option B)** — A's finding is correct and authoritative; B/C inherited the spec's wrong assumption. ADR #1. |
| Role privileges | 9 privs; drop `Pool.Allocate`, `VM.Config.Disk` | adds `VM.Config.Disk`, `VM.Console` | adds `VM.Config.CPU/Memory`, `Pool.Audit` | **9-priv set (§2.1)**; exclude Disk/CPU/Memory/Console; `Pool.Audit` optional with `/pool` scoping |
| ACL scope | `/pool` + storage + node (tight) | `/vms` + storage (simpler) | `/pool/burrow-workers` + template | **`/pool` recommended**; `/vms` is the simpler fallback. ADR #2 (changes clone surface) |
| Clone mode | `--full` (linked is the CT-template default) | `--full`, thin storage | `--full` per ARCH GAP #5 | **`--full`** on thin storage; budget clone time into the UPID wait |
| Token idempotency | guard explicitly | guard explicitly | prompt rotate/reuse on re-run | **Guard + prompt**; never silently churn |

---

## 10. Open decisions — ADR candidates

1. **LXC boot-config injection** *(highest priority)* — record the no-`pct`-over-API finding;
   decide **Option B (pull-at-boot)**. Rewrites WORK-03 / SC-4 / SC-5; adds
   `GET /api/v1/internal/bootconfig/{vmid}` + the secret-handling-at-boot contract.
2. **Proxmox ACL scoping model** — `/pool/burrow-workers` (tight; clone must touch pool
   membership) vs `/vms` cluster-wide (simple; broad). Changes the
   `ProxmoxComputeProvider.clone` surface.
3. **Static-IP-from-VMID** — the VMID→IP formula + the off-host DHCP-exclusion obligation
   (already an ARCHITECTURE decision; ADR pins the LAN contract).
4. **Clone mode** — `--full` (confirmed) — fold into the existing Phase 0 clone-mode ADR.
5. **Control-plane runtime base** — bare-host venv vs `Dockerfile.api` image (ties to the
   open `burrow-api` runtime-base question; `PRIMING.md` should support both).

**Operator decisions left open (not ADRs — homelab facts):** exact `<rootfs-storage>` name
and type (the `/storage/...` ACL must match it); thin-pool fill monitoring if `--full` on
thin storage; whether to enable the PVE firewall (and the `:7681` allow if so).

---

## Sources

- Proxmox VE: [pveum.1](https://pve.proxmox.com/pve-docs/pveum.1.html),
  [pct.1](https://pve.proxmox.com/pve-docs/pct.1.html),
  [pveam.1](https://pve.proxmox.com/pve-docs/pveam.1.html),
  [pvesh.1](https://pve.proxmox.com/pve-docs/pvesh.1.html),
  [User Management (privileges, tokens, privsep)](https://pve.proxmox.com/wiki/User_Management),
  [Storage](https://pve.proxmox.com/wiki/Storage),
  [Linux Container (nesting/features)](https://pve.proxmox.com/wiki/Linux_Container),
  [Proxmox VE Firewall](https://pve.proxmox.com/wiki/Proxmox_VE_Firewall),
  [Time Synchronization](https://pve.proxmox.com/wiki/Time_Synchronization),
  [Proxmox VE API (token header, privsep)](https://pve.proxmox.com/wiki/Proxmox_VE_API)
- Forums: [no API for `pct exec`/commands in LXC](https://forum.proxmox.com/threads/execute-command-in-node-with-api.112290/),
  [permissions via API (VM.Clone/Allocate/Datastore.AllocateSpace/SDN.Use, pool scoping)](https://forum.proxmox.com/threads/confusion-about-permissions-when-going-via-api.182761/),
  [node status 403 needs Sys.Audit](https://forum.proxmox.com/threads/vm-403-permission-check-failed-nodes-pve2-sys-audit.113139/),
  [token perms = user∩token](https://forum.proxmox.com/threads/api-token-permissions-problem.141221/),
  [`/cluster/nextid` not race-safe](https://forum.proxmox.com/threads/is-there-an-atomic-way-to-get-the-next-free-vm_id-and-reserve-it.123984/),
  [CT template clone defaults to linked, `--full` for independent](https://forum.proxmox.com/threads/ct-template-cannot-clone-as-linked.97201/)
- [authorized_keys forced-command restriction](https://blog.sanctum.geek.nz/restricting-public-keys/)
- Internal: `docs/tech-spec.md` §4.2/§9/§10; `.planning/research/{ARCHITECTURE,PITFALLS}.md`;
  `.planning/{PROJECT,REQUIREMENTS,ROADMAP}.md` (authoritative internal specs)
