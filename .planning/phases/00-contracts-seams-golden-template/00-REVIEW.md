<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
reviewed: 2026-06-10T00:00:00Z
depth: deep
files_reviewed: 38
files_reviewed_list:
  - api/config.py
  - api/lib/envelope.py
  - api/models/base.py
  - api/models/compute.py
  - api/models/workspace.py
  - api/models/event.py
  - api/models/template.py
  - api/compute/provider.py
  - api/compute/fakeProvider.py
  - api/compute/proxmoxProvider.py
  - api/db/provider.py
  - api/db/sqliteProvider.py
  - api/db/postgresProvider.py
  - api/db/migrations/001_init.sql
  - api/main.py
  - api/tests/conftest.py
  - api/tests/unit/test_db_provider.py
  - api/tests/unit/test_fake_compute.py
  - api/tests/unit/test_envelope.py
  - api/tests/unit/test_models.py
  - api/tests/unit/test_seam_leakage.py
  - cc-worker-config/lxc/host-prime/00-api-user-role.sh
  - cc-worker-config/lxc/host-prime/10-template-download.sh
  - cc-worker-config/lxc/host-prime/20-create-template.sh
  - cc-worker-config/lxc/host-prime/40-control-plane.sh
  - cc-worker-config/lxc/host-prime/lib/common.sh
  - cc-worker-config/lxc/host-prime/30-network-notes.md
  - cc-worker-config/lxc/worker-template/burrow-boot.sh
  - cc-worker-config/lxc/worker-template/provision-template.sh
  - cc-worker-config/systemd/burrow-worker.service
  - .github/workflows/ci.yml
  - REUSE.toml
  - .env.example
  - .gitignore
  - ui/package.json
  - ui/tsconfig.json
  - ui/src/placeholder.ts
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 0: Code Review Report

**Reviewed:** 2026-06-10
**Depth:** deep
**Files Reviewed:** 38
**Status:** issues_found

## Summary

Phase 0 ships contracts, provider seams, and the host-prime/golden-template kit.
The Python contract layer (envelope, CamelModel, compute/db ABCs, FakeComputeProvider,
SqliteProvider) is sound: the snake↔camel round-trip is correct, the Fake is
genuinely deterministic and models the lifecycle honestly, and the ttyd boot
command correctly drops `--once` and binds `0.0.0.0` per ADR-0006/0007. The secret
hygiene in the host-prime scripts is mostly disciplined (printf-not-echo, `set +x`,
silent reads, refuse-unless-gitignored, 0600).

However, three BLOCKER-class defects make the shipped artifacts non-functional or
unsafe as wired:

1. The strict-mode `IFS=$'\n\t'` in `common.sh` silently breaks the ACL-grant loop
   in `00-api-user-role.sh` — the security-critical least-privilege grant passes
   `--users burrow@pve` as a single argument and `pveum` will reject it.
2. `burrow-worker.service` wires no environment, but `burrow-boot.sh` hard-requires
   `CONTROL_PLANE` (`:?`) — the unit aborts on every boot with an unbound-variable
   error, contradicting the "persistent" guarantee.
3. The `vmid` uniqueness invariant that `30-network-notes.md` and the static-IP
   scheme depend on ("a VMID collision *is* an IP collision, so the DB unique
   constraint on `vmid` guards both") is not present in `001_init.sql`.

WARNINGs cover a vacuous seam-leakage SQL guard, unenforced SQLite foreign keys,
a control-plane `.env` writer that refuses-closed in its real deployment context,
and a couple of latent contract mismatches the Phase-1 saga will hit.

## Critical Issues

### CR-01: `IFS=$'\n\t'` breaks the ACL-grant word-split — least-privilege grant never applies

**File:** `cc-worker-config/lxc/host-prime/00-api-user-role.sh:174-183` (root cause `lib/common.sh:13`)
**Issue:** `common.sh` sets `IFS=$'\n\t'` (drops space as a field separator). The
ACL loop relies on *space* word-splitting of the unquoted `$principal`:
```bash
for principal in "--users ${USER}" "--tokens ${USER}!${TOKEN}"; do
  pveum acl modify "$POOL" $principal --roles BurrowProvisioner --propagate 1
```
With space removed from `IFS`, `$principal` expands to the single argument
`--users burrow@pve` instead of two arguments `--users` + `burrow@pve`. Verified:
```
ARGC=4 :: [/pool/x][--users burrow@pve][--roles][BurrowProvisioner]
```
`pveum acl modify` receives an unparseable `--users burrow@pve` token and the grant
fails. Because this runs under `set -e` with `trap ERR`, the script aborts at the
first ACL call — the user/token are created but hold **zero** privileges. The whole
point of STEP 0 (scoped least-privilege ACLs) silently does not happen.
**Fix:** Split the principal into an array so quoting survives the restricted IFS:
```bash
for principal in "--users ${USER}" "--tokens ${USER}!${TOKEN}"; do
  read -r -a pargs <<<"$principal"   # safe split into [flag, value]
  pveum acl modify "$POOL"    "${pargs[@]}" --roles BurrowProvisioner --propagate 1
  pveum acl modify "$TMPL"    "${pargs[@]}" --roles BurrowProvisioner
  pveum acl modify "$STORAGE" "${pargs[@]}" --roles BurrowProvisioner
  pveum acl modify "$NODE"    "${pargs[@]}" --roles BurrowProvisioner
done
```
(Apply the same fix to the commented reversal/SDN loops so the recovery path also works.)

### CR-02: worker boot service has no environment — `burrow-boot.sh` aborts on every boot

**File:** `cc-worker-config/systemd/burrow-worker.service:17-21` (interacts with `burrow-boot.sh:36`)
**Issue:** `burrow-boot.sh` hard-requires the control-plane URL:
```bash
CONTROL_PLANE="${CONTROL_PLANE:?CONTROL_PLANE must be set ...}"
```
and reads `CONFIG_REPO` / `CONFIG_BRANCH` / `PROJECT_REPO` / `PROJECT_BRANCH` from
the environment. The systemd unit sets **no** `Environment=` and **no**
`EnvironmentFile=`. `provision-template.sh:71` creates `/etc/burrow/worker.env` but
nothing references it. Result: on every clone boot, `${CONTROL_PLANE:?...}` triggers
"CONTROL_PLANE: unbound variable" under `set -u`, the script exits non-zero,
`Restart=on-failure` re-runs it, and it fails identically in a 5s loop. The
"persistent LAN-bound ttyd" never starts. This contradicts the unit's own claim
("ttyd is persistent, the unit stays active for the life of the session").
**Fix:** Wire the placeholder env file into the unit so boot can source it:
```ini
[Service]
Type=simple
EnvironmentFile=-/etc/burrow/worker.env
ExecStart=/opt/burrow-boot.sh
Restart=on-failure
RestartSec=5
```
(The leading `-` tolerates an empty/missing file.) The Phase-3 pull-at-boot will
still populate `CONTROL_PLANE`/`CONFIG_*` at runtime, but the unit must at least be
able to deliver them; today there is no channel at all.

### CR-03: `workspaces.vmid` has no UNIQUE constraint — the documented IP-collision guard does not exist

**File:** `api/db/migrations/001_init.sql:10`
**Issue:** `30-network-notes.md:21-23` states the safety invariant:
> "A VMID collision *is* an IP collision, so the DB unique constraint on `vmid`
> guards both at once."
and the static-IP-from-VMID scheme (ADR-0004) depends on it. But the schema declares
`vmid INTEGER` with no `UNIQUE`. Only `templates.name` carries `UNIQUE`. The
"bounded scan + DB unique reservation" the network notes rely on as the
collision-avoidance backstop is absent, so a race or a logic bug in the Phase-1
create saga can persist two workspaces with the same `vmid` — which is the same
static IP — with no DB enforcement to stop it. This is a data-integrity / network-
collision risk that the design explicitly delegates to this constraint.
**Fix:** Add the partial unique index so live (non-soft-deleted) workspaces cannot
reuse a VMID, while still allowing destroyed/soft-deleted history to retain its old
value:
```sql
CREATE UNIQUE INDEX idx_workspaces_vmid_live
  ON workspaces(vmid)
  WHERE vmid IS NOT NULL AND deletedAt IS NULL;
```
(A plain `UNIQUE` column would block VMID reuse after destroy, which the pool needs;
the partial index matches the soft-delete model.)

## Warnings

### WR-01: raw-SQL seam guard is vacuous — it strips the strings it claims to scan

**File:** `api/tests/unit/test_seam_leakage.py:83-99,102-115`
**Issue:** `test_raw_sql_is_confined` calls `_strip_comments_and_strings`, which drops
every `STRING` token, then searches the remainder for `"SELECT "`, `"INSERT INTO"`,
etc. But raw SQL only ever appears *inside* string literals (e.g.
`conn.execute("SELECT * FROM workspaces")`). Those are exactly the tokens stripped.
Verified: stripping `conn.execute("SELECT * FROM workspaces")` yields
`conn . execute ( )` — `"SELECT "` is gone. The test therefore passes vacuously and
can never detect the leak it advertises; it gives false assurance that "raw SQL is
confined to sqliteProvider.py." (The `proxmoxer`/`aiosqlite` NAME-token check in the
sibling test is sound — only the SQL check is broken.)
**Fix:** Scan the *unstripped* source for the SQL fragments, and instead drop only
COMMENT and docstring-position STRING tokens. Simplest correct form: search the raw
text but exclude the file's module/function docstrings, or scan only `STRING` token
contents (where SQL actually lives) for the keywords:
```python
def _string_literals(source: str) -> list[str]:
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.STRING:
            out.append(tok.string.upper())
    return out
# then: any(kw in lit for lit in _string_literals(text) for kw in _SQL_KEYWORDS)
```
Add a guard fixture that deliberately embeds `SELECT ...` in a non-owning file and
asserts the test FAILS, so the guard is proven to bite.

### WR-02: SQLite foreign keys are never enabled — `events.workspaceId` FK is a no-op

**File:** `api/db/sqliteProvider.py:51,76,102,120,151,164,175,183` (every `aiosqlite.connect`)
**Issue:** SQLite enforces foreign keys only when `PRAGMA foreign_keys = ON` is set
*per connection*; it defaults OFF. No connection in `SqliteProvider` issues that
pragma, so the `events.workspaceId TEXT NOT NULL REFERENCES workspaces(id)` constraint
in `001_init.sql:24` is silently unenforced. `logEvent` will happily insert event rows
for a non-existent or wrong `workspaceId`, producing orphaned audit records with no
error. The schema documents an integrity guarantee the runtime does not provide.
**Fix:** Enable the pragma on every connection (centralize the connect):
```python
async def _connect(self) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(self._database_path)
    await conn.execute("PRAGMA foreign_keys = ON")
    return conn
```
and route all methods through it. Add a regression test asserting `logEvent` with an
unknown workspace id raises.

### WR-03: control-plane `.env` writer refuses-closed in its real deployment context

**File:** `cc-worker-config/lxc/host-prime/40-control-plane.sh:154-158`
**Issue:** The gitignore gate is:
```bash
if ! git -C "$APP_HOME" check-ignore .env >/dev/null 2>&1 && \
   ! git check-ignore "$ENV_FILE" >/dev/null 2>&1; then
  log "REFUSING to write ${ENV_FILE}: not confirmed gitignored."
```
On a real control-plane host, `$APP_HOME` (`/opt/burrow`) is a deploy target, not a
git checkout, so `git -C /opt/burrow check-ignore` errors (not a repo). The second
clause runs `git check-ignore /opt/burrow/.env` from the operator's CWD, which is
also typically not a repo containing that path. Both fail → the script refuses to
write `.env` and **never assembles the secret** in the exact environment it was built
for. The refuse-closed behavior is safe (no leak), but the script is effectively
non-functional for its STEP-3 purpose. Contrast `00-api-user-role.sh`, which runs in
the repo checkout where the check passes.
**Fix:** Don't gate secret-write on git at all when writing to a non-repo deploy
path; instead enforce the *real* safety property directly — that `$ENV_FILE` lives
under a 0700 root-owned dir outside any git work-tree — and rely on `umask 077` +
`chmod 0600`. If a git check is desired, scope it to a path you actually control
(e.g. confirm `$APP_HOME` is *not* a git work-tree, which is the safe condition here),
rather than requiring `.env` to be gitignored in a directory that has no `.git`.

### WR-04: `Template.plugin_manifest` / `WorkspaceEvent.data` typed as `dict` but stored as TEXT JSON

**File:** `api/models/template.py:20`, `api/models/event.py:19` (schema `001_init.sql:27,35`)
**Issue:** `Template.plugin_manifest: dict[str, Any]` and `WorkspaceEvent.data:
dict[str, Any]`, but `001_init.sql` stores `pluginManifest`/`data` as `TEXT` JSON
blobs. `CamelModel` has `from_attributes=True`, so a future read path that does
`Template.model_validate(dict(row))` will receive the column as a **str** (the raw
JSON text) and Pydantic will raise a `ValidationError` (str is not dict). Phase 0
ships no read method for templates/events, so it doesn't fail yet, but the contract
is already wrong and the Phase-1 read path will hit it. (The Workspace path is fine
because `SqliteProvider` only stores scalar columns there.)
**Fix:** Either decode in the provider before validation (mirror how `logEvent` does
`json.dumps`):
```python
raw = dict(row)
raw["plugin_manifest"] = json.loads(raw["plugin_manifest"])
return Template.model_validate(raw)
```
or give the models a `field_validator(mode="before")` that `json.loads` a `str`
input. Pin the decision with a round-trip test so Phase 1 doesn't rediscover it.

### WR-05: PR-title action is not actually SHA-pinned despite the policy comment

**File:** `.github/workflows/ci.yml:88`
**Issue:** The header (lines 9-10) states "Third-party actions are SHA-pinned … the
trailing comment records the human-readable version." But the semantic-PR action is:
```yaml
uses: amannn/action-semantic-pull-request@e32d7e603df1aa1ba07e981f2a23455dee596825 # TODO pin exact SHA
```
The `# TODO pin exact SHA` admits the pin is unverified — the 40-hex value may be a
placeholder/guess rather than a real release commit. An unverified or wrong SHA in a
workflow that runs with the repo `GITHUB_TOKEN` is a supply-chain gap (and if the SHA
doesn't resolve, the `pr-title` job errors on every PR). Every other action in the
file carries a real SHA + version comment; this one breaks the stated invariant.
**Fix:** Resolve the action's tag to its real commit SHA and record it:
`gh api repos/amannn/action-semantic-pull-request/git/ref/tags/vX.Y.Z`, then replace
the SHA and the trailing comment with `# vX.Y.Z` (drop the TODO).

### WR-06: `getNextVmid(used)` + separate `usedVmids()` invites a TOCTOU the contract can't close

**File:** `api/compute/provider.py:55-65`
**Issue:** The ABC exposes both `usedVmids() -> set[int]` and
`getNextVmid(pool_start, pool_end, used)`, forcing the saga to (1) fetch used VMIDs,
(2) compute the next free one, then (3) clone — three steps with no reservation
between them. Two concurrent create sagas can both observe the same free VMID and
both clone it (and, per CR-03, the DB won't stop the duplicate). The Fake masks this
because it's single-threaded and stateful, so saga tests will pass while the real
provider races. The contract is being "frozen before the saga is written" (per the
module docstring), so this is the moment to fix the shape, not Phase 1.
**Fix:** Either fold allocation into an atomic reserve step (e.g. a
`reserveVmid(pool_start, pool_end) -> int` that the DB unique index from CR-03 backs),
or document that VMID reservation MUST be done via a DB insert under the unique
constraint *before* `cloneCt`, and drop the `used` param from `getNextVmid` so callers
can't be fooled into the read-then-act pattern. At minimum, add CR-03's unique index
so the race fails closed.

## Info

### IN-01: `.env.*` gitignore pattern can shadow `.env.example` ordering intent

**File:** `.gitignore:5-7`
**Issue:** `.env`, then `.env.*`, then `!.env.example`. The negation correctly
re-includes `.env.example` (it comes after `.env.*`), so this works today. But the
broad `.env.*` also ignores files like `.env.local`, `.env.production` — intended —
while a future `.env.example.bak` etc. would need its own negation. Low risk; noting
because secret-file ignore rules are load-bearing here.
**Fix:** None required. Optionally tighten to `.env` and `.env.local` explicitly if the
broad glob ever surprises someone.

### IN-02: `40-control-plane.sh` references nginx/systemd sources that don't exist yet

**File:** `cc-worker-config/lxc/host-prime/40-control-plane.sh:39-43`
**Issue:** `NGINX_SITE_SRC=.../nginx/burrow.conf` and `SYSTEMD_UNIT_SRC=.../systemd/burrow.service`
are referenced, but the repo ships neither (only `systemd/burrow-worker.service`
exists). The script guards both with `[[ -f ... ]]` and logs a skip, so it degrades
gracefully — but a STEP-3 run installs no nginx site and no control-plane unit,
leaving the "verify with curl …:8000/health" closing log misleading.
**Fix:** Either add the `nginx/burrow.conf` + `systemd/burrow.service` artifacts in the
phase that owns them, or adjust the closing log to state these are operator-supplied
until that phase lands.

### IN-03: `ProxmoxComputeProvider.__init__` reads the CA path but constructs no client

**File:** `api/compute/proxmoxProvider.py:30-33`
**Issue:** The skeleton stores `self._ca_cert_path` to "make the contract explicit,"
but no `ProxmoxAPI(..., verify_ssl=<ca path>)` client is built (correctly deferred to
Phase 1). The risk is that the CA-pinning intent lives only in a docstring and an
unused attribute; a Phase-1 implementer could wire `verify_ssl=False` and nothing in
Phase 0 prevents it. Acceptable for a skeleton, but the guarantee is currently
aspirational.
**Fix:** Add a Phase-1 test stub now (xfail/skip) asserting the constructed client
passes the CA path and never `verify_ssl=False`, so the guard exists before the body.

### IN-04: `events.data` default `'{}'` vs model requiring a dict — empty-string risk

**File:** `api/db/migrations/001_init.sql:27`, `api/db/sqliteProvider.py:178`
**Issue:** `logEvent` always writes `json.dumps(data)`, so the column default `'{}'`
is never exercised by this code path — fine. But the column also allows `NULL`
(`data TEXT DEFAULT '{}'` has no `NOT NULL`), so a direct/manual insert could store
`NULL`, which the future `WorkspaceEvent.data: dict` read path (see WR-04) would
reject. Minor; flagged alongside WR-04.
**Fix:** Make the column `data TEXT NOT NULL DEFAULT '{}'` to match the non-optional
model field.

---

_Reviewed: 2026-06-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
