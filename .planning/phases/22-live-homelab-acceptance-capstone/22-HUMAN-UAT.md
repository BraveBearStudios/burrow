<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: human_needed
phase: 22
verified: pending
---

# Phase 22: Live Homelab Acceptance Capstone - Human UAT

This is the operator runbook for the v1.4 acceptance capstone. It is run BY A HUMAN
on the real Proxmox homelab. Nothing here is CI-provable: CI never touches real
Proxmox, so every item is `result: [pending]` until you run it and record evidence.

Work top to bottom. Do Step 0 first (it redeploys the control plane to the release
that has the credential GUI and async-202). Then run UAT-1 through UAT-5. Each item
lists the exact commands, the expected output, and a recovery hint if it can fail.

## Conventions (read once)

- **Control plane box:** `bravebear@lintool03`, checkout at `~/burrow`, stack
  `compose.prod.yml`, host port `:8081`.
- **Proxmox box:** den01, API `10.0.0.6`, key-based SSH as `root@10.0.0.6`. Run the
  `ssh root@10.0.0.6 '...'` commands from whichever box has that key (the dev box or
  lintool03).
- Shorthand used below (set these in the shell you run curl from, on lintool03):
  ```bash
  BASE=http://127.0.0.1:8081/api/v1
  DEN="ssh root@10.0.0.6"
  ```
- Health can also be checked at `https://burrow.local.bravebearstudios.com/api/v1/health`.
  NEVER use `:80` on lintool03 (that is ntfy, returns `{"code":40401,...}`).
- All responses use the envelope `{ "data": ..., "meta": ..., "error": ... }`. Pipe
  through `jq .` if installed, else `python3 -m json.tool`.

## Placeholders to confirm BEFORE you start

Replace these with the confirmed live values. They are the assumptions this runbook
could not read from the code:

- `<NODE2>` = the confirmed second live worker node name (den01 is the first). It MUST
  be present in `WORKER_NODES` in `/opt/burrow/.env` alongside den01.
- `<IDLE_S>` = the live `idle_window_s` from `/opt/burrow/.env` (code default is
  `1800` = 30 min). UAT-1 lets you temporarily lower it to keep the wait short.
- `<REL>` = the exact published release tag to deploy and verify. This runbook uses
  `1.4.1`; confirm the tag that release-please actually published (it may be `1.4.0`).
- `<DIGEST>` = the `sha256:...` digest of the pulled image (UAT-5 shows how to read it).

## The operator runs every DESTROY step

The control plane's auto-mode classifier blocks the AGENT from destroying a workspace
it did not create. So YOU run every `DELETE /workspaces/{id}` and every den01
`pct destroy`. Steps that destroy are tagged **[OPERATOR-DESTROY]**.

## Success-criteria map

| UAT item | Success criterion |
|----------|-------------------|
| Step 0   | Precondition: v1.4 release deployed (Phase 18 GUI + Phase 19 async-202) |
| UAT-1    | Criterion 1 (ACC-04): reaper orphan + idle auto-stop + capacity |
| UAT-2    | Criterion 2 (ACC-04 item 9): least-loaded node selection across 2 nodes |
| UAT-3    | Criterion 3 (ACC-04): persistent survives stop/start; reaper spares it |
| UAT-4    | Criterion 4 (ACC-05): GUI credential store live on den01 |
| UAT-5    | Criterion 5 (ACC-06 rider): live signature + attestation re-verify |

## Tests

### Step 0: Deploy the v1.4 release to lintool03

The currently-deployed control plane is the pre-GUI, curl-only build. Phase 22 needs
the Phase 18 credential GUI and the Phase 19 async-202 create. Redeploy first.

**0a. Snapshot the secret key (must not change).**
```bash
ssh bravebear@lintool03
grep '^BURROW_SECRET_KEY=' /opt/burrow/.env
```
- expected: one non-empty `BURROW_SECRET_KEY=...` line. Note the last 6 chars; you will
  confirm it is unchanged after deploy. If you ever regenerate it, the stored token
  cannot decrypt and ACC-05 fails.

**0b. Fast-forward the checkout to the release.**
```bash
cd ~/burrow
git fetch origin
git status            # expect only the known local edit: M compose.prod.yml (:8081 remap)
git stash             # park the local compose remap so pull fast-forwards cleanly
git pull --ff-only origin main
git stash pop         # restore the :8081 host-port remap
```
- expected: a clean fast-forward to the v1.4 release commit; `git stash pop` reapplies
  the `:8081` remap with no conflict.
- recovery: if `git pull --ff-only` refuses (diverged), do NOT force. Run
  `git log --oneline -5 origin/main` and reconcile manually; the deploy checkout must
  never carry unpushed commits.

**0c. Bring up the new build. Pick ONE path.**

Path A: build locally from the pulled source (matches the current deploy style):
```bash
docker compose -f compose.prod.yml up -d --build
```

Path B: pull the signed, released images (pin to the release, not `latest`):
```bash
docker login ghcr.io      # only if the packages are private; use a PAT with read:packages
docker pull ghcr.io/bravebearstudios/burrow-api:<REL>
docker pull ghcr.io/bravebearstudios/burrow-ui:<REL>
# then point compose.prod.yml's two `build:` blocks at the pulled images and:
docker compose -f compose.prod.yml up -d
```
- expected: `burrow-api` and `burrow-web` both recreate and come up healthy
  (`burrow-web` waits on `burrow-api` `service_healthy`).
- recovery: if `docker login` fails or the package is private and inaccessible, use
  Path A (local build) instead: it needs no registry auth.

**0d. Confirm health and that the secret key is unchanged.**
```bash
grep '^BURROW_SECRET_KEY=' /opt/burrow/.env          # same last 6 chars as 0a
curl -s $BASE/health | jq .
curl -s https://burrow.local.bravebearstudios.com/api/v1/health | jq .
```
- expected: both health calls return `data: { status: "ok", db: "ok", compute: "ok" }`.
- recovery: if `compute` is `error`, check `/opt/burrow/.env` still has the Proxmox
  token and the CA path, and `docker compose -f compose.prod.yml logs -f burrow-api`.

**0e. Confirm the credential GUI renders.**
- In a LAN browser open `https://burrow.local.bravebearstudios.com`. Because setup was
  already completed on this deployment, confirm the admin-gated **Credentials /
  Settings** screen is reachable from the Navbar (it prompts for the admin secret).
  On a fresh DB the **SetupWizard** would show the new admin-secret and credentials
  steps.
- expected: the Credentials screen renders (admin-secret prompt, credential status
  panel, read-only audit panel). This is the Phase 18 GUI that the old build lacked.
- recovery: hard-refresh (the old SPA may be cached); confirm burrow-web recreated in
  `docker compose -f compose.prod.yml ps`.

- result: [pending]

### UAT-1: reaper, idle auto-stop, and capacity (Criterion 1, ACC-04)

Three independent checks. Run 1A, 1B, 1C in order.

**1A. Reaper destroys a real injected orphan LXC on a non-default node.**

Inject an orphan: a CT with a VMID in the worker range (969 to 1022) that has NO DB
row, placed on `<NODE2>` (a non-default node, so this also proves CR-01 node-correct
destroy). Pick a free in-range VMID, e.g. `1020`.

```bash
# On den01 / the second node. List a local template to clone from, or clone 9000:
$DEN "pveam list local | tail -n +1"          # see an available CT template
# Create a throwaway CT in the pool on <NODE2> (substitute a real template + storage):
$DEN "pct create 1020 local:vztmpl/<template>.tar.zst \
      --hostname burrow-orphan-1020 --pool burrow-workers \
      --cores 1 --memory 256 --rootfs local-lvm:1 --node <NODE2>"
# Confirm it exists and is a pool member with an in-range VMID:
$DEN "pct list | grep 1020"
```
- The reaper reaps any CT whose VMID is in the pool range and has no live DB row. It
  does not need to be running. Placing it in `/pool/burrow-workers` ensures the
  pool-scoped token can destroy it.

Trigger a reconcile pass and watch it get reaped. The reconciler runs every
`reconciler_period_s` (default 60s), so just wait one to two periods:
```bash
docker compose -f compose.prod.yml logs --since 3m burrow-api | grep reaper.destroyed
$DEN "pct list | grep 1020 || echo 'GONE (VMID freed)'"
```
- expected: a `reaper.destroyed` log line with `vmid=1020`, and `pct list` no longer
  shows 1020 (the VMID is freed). Any out-of-range or non-pool CT is untouched.
- recovery: if it is not reaped within ~2 minutes, confirm the VMID is really in
  `WORKER_POOL_START..WORKER_POOL_END` and the CT is in `/pool/burrow-workers`. If the
  api log shows a 403 on destroy, the token lacks rights on `<NODE2>`; grant the pool
  ACL on that node (as the golden-template setup did on den01), or manually
  `$DEN "pct destroy 1020"` and note the ACL gap.
- result: [pending]

**1B. Idle auto-stop fires after the real window; a brief reconnect does not trip it.**

Idle = the LAST terminal event for a running workspace is a `terminal.disconnected`
older than `idle_window_s`. A reconnect appends a fresh `terminal.connected`, which
flips the last event back to connected, so it is no longer idle.

Optional (recommended for a short UAT): temporarily lower the window so you do not wait
30 minutes. This exercises the same code path.
```bash
# On lintool03, add/lower the window and restart ONLY burrow-api (key unchanged):
grep -q '^IDLE_WINDOW_S=' /opt/burrow/.env \
  && sed -i 's/^IDLE_WINDOW_S=.*/IDLE_WINDOW_S=120/' /opt/burrow/.env \
  || echo 'IDLE_WINDOW_S=120' >> /opt/burrow/.env
docker compose -f compose.prod.yml up -d burrow-api
curl -s $BASE/health | jq .data     # confirm compute: ok after restart
```
Now create a workspace and drive the idle path:
```bash
# 1) Create (async 202) and capture the id:
WS=$(curl -s -X POST $BASE/workspaces -H 'content-type: application/json' \
  -d '{"name":"idle-test","projectRepo":"thezoid/fable-test","projectBranch":"main"}' \
  | jq -r .data.id)
echo "workspace=$WS"
# 2) Wait for running (list poll):
watch -n3 "curl -s $BASE/workspaces/$WS | jq -r .data.status"   # Ctrl-C at 'running'
```
- In a LAN browser, open this workspace's terminal panel once (appends
  `terminal.connected`), then close it (appends `terminal.disconnected`). Confirm the
  events:
```bash
curl -s $BASE/workspaces/$WS/events | jq -r '.data[].type'   # last line: terminal.disconnected
```
- **Brief-reconnect sub-check:** within the window, reopen the terminal briefly then
  close it again, and confirm auto-stop does NOT fire on the next pass:
```bash
sleep "$(( <IDLE_S> + 30 ))"   # or 150 if you set IDLE_WINDOW_S=120
curl -s $BASE/workspaces/$WS | jq -r .data.status
```
  If the last terminal event is a fresh `terminal.connected` (you reconnected), status
  stays `running`. Then leave it disconnected and wait one more window.
- **Idle sub-check:** with `terminal.disconnected` as the last event, wait past the
  window plus one reconcile period:
```bash
curl -s $BASE/workspaces/$WS | jq -r .data.status                 # expect: stopped
curl -s $BASE/workspaces/$WS/events | jq -r '.data[] | select(.type=="workspace.stopped")'
```
- expected: after the window elapses with `terminal.disconnected` last, status is
  `stopped` and a `workspace.stopped` event carries `reason: idle`. During the brief
  reconnect it stayed `running`.
- recovery: if it never stops, confirm the last terminal event really is
  `terminal.disconnected` (a lingering browser tab keeps a `terminal.connected`), and
  that `IDLE_WINDOW_S` took effect (check `docker compose logs burrow-api` at startup).
  Restore the real window when done: set `IDLE_WINDOW_S` back and `up -d burrow-api`.
- **[OPERATOR-DESTROY]** clean up the idle-test workspace:
```bash
curl -s -X DELETE $BASE/workspaces/$WS | jq .data
$DEN "pct list | grep -E ' (96[9]|9[7-9][0-9]|10[01][0-9]|102[0-2]) ' || echo 'worker range empty'"
```
- result: [pending]

**1C. Capacity holds under real concurrent creates.**

Fire several concurrent creates and confirm no overcommit: each create that succeeds
gets a DISTINCT VMID (the DB partial-unique index arbitrates the race), and creates
that would push a node past `capacity_threshold` (0.80 node-RAM fraction) are refused
with a capacity error rather than overcommitting.
```bash
for i in 1 2 3 4; do
  curl -s -X POST $BASE/workspaces -H 'content-type: application/json' \
    -d "{\"name\":\"cap-$i\",\"projectRepo\":\"thezoid/fable-test\"}" &
done; wait
curl -s $BASE/workspaces | jq -r '.data[] | "\(.name) \(.status) vmid=\(.vmid) node=\(.node)"'
```
- expected: the successful creates hold DISTINCT VMIDs (no duplicate), each on a fitting
  node; none share a VMID. If a node is near the RAM threshold, the excess creates come
  back as a capacity error (HTTP 4xx envelope with a capacity code), never as a silent
  overcommit. Rows settle to `running` or a compensated `error`, never stuck `creating`.
- recovery: if all four fail with capacity, the homelab is genuinely full; reduce the
  count or free RAM and retry. A duplicate VMID would be a real defect: capture the two
  rows and the api logs.
- **[OPERATOR-DESTROY]** destroy each `cap-*` workspace by id, then confirm the worker
  range is empty on den01:
```bash
for ID in $(curl -s $BASE/workspaces | jq -r '.data[] | select(.name|startswith("cap-")) | .id'); do
  curl -s -X DELETE $BASE/workspaces/$ID | jq -r '.data | "\(.id) \(.status)"'
done
$DEN "pct list | awk 'NR>1 && \$1>=969 && \$1<=1022'"    # expect: no rows
```
- result: [pending]

### UAT-2: least-loaded node selection across 2 live nodes (Criterion 2, ACC-04 item 9)

Precondition: `WORKER_NODES` in `/opt/burrow/.env` lists den01 AND `<NODE2>` (confirm
`docker compose logs burrow-api` at startup, or that a create can land on `<NODE2>`).

Create with node auto-select (omit `node`, or send `"node": null`) and confirm the
saga lands the worker on the genuinely least-loaded of the two nodes per live metrics.
```bash
# Read current RAM load per node to know which SHOULD win:
$DEN "pvesh get /nodes/den01/status --output-format json | jq '.memory'"
$DEN "ssh <NODE2> 'pvesh get /nodes/<NODE2>/status --output-format json' | jq '.memory'"
# Auto-select create:
WS=$(curl -s -X POST $BASE/workspaces -H 'content-type: application/json' \
  -d '{"name":"nodesel-test","projectRepo":"thezoid/fable-test"}' | jq -r .data.id)
watch -n3 "curl -s $BASE/workspaces/$WS | jq -r '.data | \"\(.status) node=\(.node)\"'"
```
- expected: `node` on the created row equals the least-loaded node (lowest used/total
  RAM fraction) at create time, not a hardcoded default. If den01 is busier, it lands
  on `<NODE2>`, and vice versa.
- recovery: if it always lands on den01, confirm `<NODE2>` is actually in
  `WORKER_NODES` and reachable, and that `<NODE2>` has free capacity below the
  threshold. Read the api log for the selected-node decision.
- **[OPERATOR-DESTROY]** destroy `nodesel-test`:
```bash
curl -s -X DELETE $BASE/workspaces/$WS | jq .data
```
- result: [pending]

### UAT-3: persistent workspace survives stop then start; reaper spares it (Criterion 3, ACC-04)

**3a. Create a PERSISTENT workspace and write work to disk + scrollback.**
```bash
WS=$(curl -s -X POST $BASE/workspaces -H 'content-type: application/json' \
  -d '{"name":"persist-test","projectRepo":"thezoid/fable-test","persistent":true}' \
  | jq -r .data.id)
watch -n3 "curl -s $BASE/workspaces/$WS | jq -r '.data | \"\(.status) vmid=\(.vmid) ip=\(.lxcIp)\"'"
```
- Note the `vmid` and `lxcIp`. In the browser terminal, type a marker so there is
  scrollback to restore, e.g. `echo BURROW-PERSIST-MARKER-42`, and write a file:
  `echo hello-persist > /root/persist-proof.txt`.
- Confirm the file on den01 (substitute the vmid):
```bash
$DEN "pct exec <vmid> -- cat /root/persist-proof.txt"     # expect: hello-persist
```

**3b. Stop then start; confirm disk + scrollback intact, same VMID/IP.**
```bash
curl -s -X POST $BASE/workspaces/$WS/stop  | jq -r .data.status     # expect: stopped
$DEN "pct status <vmid>"                                            # expect: status: stopped
curl -s -X POST $BASE/workspaces/$WS/start | jq -r '.data | "\(.status) vmid=\(.vmid) ip=\(.lxcIp)"'
```
- expected: after start, status `running`, SAME `vmid` and SAME `lxcIp` as 3a (disk
  preserved, not reprovisioned).
```bash
$DEN "pct exec <vmid> -- cat /root/persist-proof.txt"     # still hello-persist (disk intact)
```
- In the browser terminal on reconnect, confirm the `BURROW-PERSIST-MARKER-42`
  scrollback is replayed (the tmux `-A` reattach restores the buffered output), not a
  fresh shell.
- expected: disk file intact AND scrollback restored on reconnect.
- recovery: if the IP or VMID changed, the workspace was reprovisioned rather than
  restarted: capture both rows and the api logs. If scrollback is empty, confirm the
  worker uses `tmux new-session -A -s burrow` (the boot-harness reattach argv).

**3c. Reaper never destroys a persistent STOPPED workspace.**
```bash
curl -s -X POST $BASE/workspaces/$WS/stop | jq -r .data.status      # stopped again
# Let at least two reconcile periods pass (>= 2x reconciler_period_s):
sleep 150
curl -s $BASE/workspaces/$WS | jq -r .data.status                   # expect: stopped (still present)
$DEN "pct status <vmid>"                                            # expect: status: stopped (CT still exists)
docker compose -f compose.prod.yml logs --since 3m burrow-api | grep reaper.destroyed | grep <vmid> \
  && echo 'DEFECT: persistent stopped was reaped' || echo 'OK: reaper spared it'
```
- expected: the persistent stopped workspace is untouched across reconcile passes (its
  live DB row keeps its VMID in `live_vmids`, so the orphan predicate spares it). No
  `reaper.destroyed` line for its VMID.
- recovery: a reap here is a real regression in the WSX-04 carve-out. Capture the row,
  the events, and the reaper log line.
- **[OPERATOR-DESTROY]** destroy `persist-test` and confirm the VMID frees:
```bash
curl -s -X DELETE $BASE/workspaces/$WS | jq .data
$DEN "pct status <vmid> 2>&1 || echo 'GONE'"
```
- result: [pending]

### UAT-4: GUI credential store live on den01 (Criterion 4, ACC-05)

**4a. Confirm migration 004 applied on the real SQLite.**
```bash
docker exec burrow-api python3 -c "import sqlite3; c=sqlite3.connect('/data/burrow.db'); \
print('settings cols:', [r[1] for r in c.execute('PRAGMA table_info(settings)')]); \
print('audit_log present:', bool(list(c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'\"))))"
```
- expected: the `settings` columns include `proxmoxTokenEnc`, `proxmoxTokenLast4`,
  `gitTokenEnc`, `gitTokenLast4`, `adminSecretHash`, `credentialsUpdatedAt`, and
  `audit_log present: True`.
- recovery: if the columns are missing, migration 004 did not run: check
  `docker compose logs burrow-api` at startup for the migrate() step and that
  `DATABASE_PATH=/data/burrow.db` is what the container reads.

**4b. Set a Proxmox token via the GUI (admin-gated), no restart.**
- In the browser, open the Credentials screen, enter the admin secret when prompted,
  and submit a valid Proxmox token in the credentials form. The backend validates it
  read-only via `testConnection` BEFORE persisting, then applies it live
  (`set_proxmox_token_override` + `reset_compute`), so no restart is needed.
- Equivalent curl (fallback / verification), where `ADMIN` is the admin secret:
```bash
ADMIN='<admin-secret>'
curl -s -X POST $BASE/setup/credentials -H "X-Burrow-Admin: $ADMIN" \
  -H 'content-type: application/json' \
  -d '{"proxmoxTokenValue":"<valid-proxmox-token-uuid>"}' | jq .data
curl -s $BASE/setup/credentials -H "X-Burrow-Admin: $ADMIN" | jq .data
```
- expected: the save returns status with the token's `last4`; the status read shows the
  Proxmox credential set with that `last4` and a fresh `credentialsUpdatedAt`. No secret
  value is ever returned.
- recovery: a `401 admin_auth` means the admin secret is wrong or unset (re-enter it).
  A hard failure (auth/unreachable) means the token itself is bad; the backend refuses
  to store a broken token, which is correct.

**4c. Applies WITHOUT a restart: a create still works.**
```bash
WS=$(curl -s -X POST $BASE/workspaces -H 'content-type: application/json' \
  -d '{"name":"cred-nore-start","projectRepo":"thezoid/fable-test"}' | jq -r .data.id)
# Confirm the 202 came back immediately (no 504) and the row is creating->running:
watch -n3 "curl -s $BASE/workspaces/$WS | jq -r .data.status"     # creating -> running
```
- expected: `POST /workspaces` returns immediately with `202` + a `creating` row (no
  60s `504`), and the row reaches `running` using the just-set token, with NO
  control-plane restart in between. This is the async-202 + hot-swap proof.
- **[OPERATOR-DESTROY]** destroy `cred-nore-start`:
```bash
curl -s -X DELETE $BASE/workspaces/$WS | jq .data
```

**4d. Survives a restart: the stored token reloads at startup.**
```bash
BEFORE=$(curl -s $BASE/setup/credentials -H "X-Burrow-Admin: $ADMIN" | jq -r .data.proxmoxTokenLast4)
docker compose -f compose.prod.yml restart burrow-api
sleep 5
curl -s $BASE/health | jq -r '.data | "\(.status) db=\(.db) compute=\(.compute)"'   # ok/ok/ok
AFTER=$(curl -s $BASE/setup/credentials -H "X-Burrow-Admin: $ADMIN" | jq -r .data.proxmoxTokenLast4)
echo "last4 before=$BEFORE after=$AFTER"
```
- expected: after the restart, health is `ok/ok/ok` (the provider bound to the stored
  token at startup via the lifespan `CredentialResolver.proxmox_token()` load), and the
  `proxmoxTokenLast4` is unchanged (`before == after`). This works only because
  `BURROW_SECRET_KEY` was unchanged (Step 0a), so the ciphertext still decrypts.
- recovery: if `compute` is `error` after restart, or `last4` changed, confirm
  `BURROW_SECRET_KEY` is the same value from Step 0a. A changed key makes the stored
  ciphertext undecryptable and the resolver falls back to the `.env` token.
- result: [pending]

### UAT-5: live signature + attestation re-verify (Criterion 5, ACC-06 rider)

ACC-06 was already proven green on the GitHub runner in Phase 20 (the release run that
signed + attested the images, run `29355954285`). This item re-verifies a
homelab-PULLED image by digest, from the LAN, to close the loop.

**5a. Pull an image and read its digest.**
```bash
docker pull ghcr.io/bravebearstudios/burrow-api:<REL>
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/bravebearstudios/burrow-api:<REL>
# -> ghcr.io/bravebearstudios/burrow-api@sha256:<DIGEST>   (copy the sha256 part)
```

**5b. cosign verify (keyless, by digest, fails loudly).**
```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/BraveBearStudios/burrow/.*' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  ghcr.io/bravebearstudios/burrow-api@sha256:<DIGEST> | jq .
```
- expected: cosign prints the verified-claims summary (matched Fulcio identity, the
  OIDC issuer `token.actions.githubusercontent.com`, a Rekor transparency-log entry)
  and exits 0. Repeat for `burrow-ui`.
- recovery: verify by DIGEST, never by tag. If the identity regexp does not match,
  confirm the repo owner casing (`BraveBearStudios`) matches the workflow identity in
  the signing certificate.

**5c. gh attestation verify (assert on OUTPUT, not just exit code).**
```bash
gh attestation verify \
  oci://ghcr.io/bravebearstudios/burrow-api@sha256:<DIGEST> \
  --owner BraveBearStudios
```
- expected: an explicit verified line plus the SLSA provenance predicate bound to the
  digest. Assert on the printed verified output / JSON, not merely exit 0 (the T-14-01
  exit-0 trap), paired with the loud-passing cosign verify above.
- recovery: `gh auth status` must show a logged-in gh with `read:packages`. Note the
  GHCR path is lowercase (`bravebearstudios`) but the attestation `--owner` is the
  mixed-case GitHub org `BraveBearStudios`.
- result: [pending]

## Final teardown (operator)

Leave the homelab clean: no Burrow workers on den01 or `<NODE2>`.
```bash
# Destroy any remaining Burrow-created workspaces by id (OPERATOR-DESTROY):
for ID in $(curl -s $BASE/workspaces | jq -r '.data[].id'); do
  curl -s -X DELETE $BASE/workspaces/$ID | jq -r '.data | "\(.id) \(.status)"'
done
# Confirm the worker VMID range is empty on BOTH nodes:
$DEN "pct list | awk 'NR>1 && \$1>=969 && \$1<=1022'"
$DEN "ssh <NODE2> \"pct list | awk 'NR>1 && \\\$1>=969 && \\\$1<=1022'\""
# Restore the real idle window if you lowered it in 1B:
grep '^IDLE_WINDOW_S=' /opt/burrow/.env    # set back to the live value, then: up -d burrow-api
```
- expected: both `pct list` filters return no rows; `IDLE_WINDOW_S` restored to `<IDLE_S>`.

## Summary

- Total items: 6 (Step 0 precondition + UAT-1..5).
- Passed: 0.
- Pending: 6.

Run each item on the real homelab, flip its `result: [pending]` to passed with the
evidence (VMIDs, node names, event `reason: idle`, last4 before/after, the pulled
`@sha256:` digest, and the cosign / gh attestation verified output), then record the
roll-up into `22-VERIFICATION.md`. Passing all items closes v1.4.

## References

- Success criteria: `.planning/ROADMAP.md` Phase 22 (criteria 1 to 5).
- Prior H9 core (items 1 to 5, passed 2026-07-12) and the format precedent:
  `.planning/milestones/v1.3-phases/14-first-real-infra-acceptance/14-HUMAN-UAT.md`.
- Reaper + idle carve-out: `api/services/reconciler.py`; persistence bound:
  `api/services/workspaceService.py` + `api/db/migrations/003_persistent_and_settings.sql`.
- Credential store: `api/routers/setup.py`, `api/db/migrations/004_credentials_and_audit.sql`,
  startup reload in `api/main.py` (lifespan `CredentialResolver.proxmox_token()`).
- Async-202 create: `api/routers/workspaces.py` (`POST /workspaces`, `status_code=202`).
