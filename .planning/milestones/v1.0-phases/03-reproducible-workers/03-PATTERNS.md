<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 3: Reproducible Workers - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 8 (2 modified, 6 new)
**Analogs found:** 8 / 8 (every new/modified file has an in-repo precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cc-worker-config/lxc/worker-template/burrow-boot.sh` (MODIFY: stub → live) | boot script | request-response + file-I/O | `cc-worker-config/lxc/host-prime/lib/common.sh` (strict-mode + `err_trap` idiom) + its own Phase-0 stub (frozen ttyd tail) | exact (role) + frozen-contract reuse |
| `cc-worker-config/lxc/worker-template/provision-template.sh` (MODIFY: add `jq` to bake) | config / provisioner | batch | itself (line 34 `apt-get install` list) | exact (in-place edit) |
| `cc-worker-config/plugins/manifest.json` (NEW) | config (data) | transform (consumed by boot) | RESEARCH §"Manifest JSON-Schema" example + `Template.plugin_manifest` (tech-spec §11.1) | role-match (no existing committed manifest) |
| `cc-worker-config/plugins/manifest.schema.json` (NEW) | config (schema) | transform | RESEARCH §"Manifest JSON-Schema (the shared source of truth)" | role-match (first JSON-Schema in repo) |
| `api/tests/integration/test_manifest_schema.py` (NEW) | test (unit) | request-response | `api/tests/integration/test_bootconfig.py` (sentinel + envelope-shape assertion idiom) | role-match (CI unit test) |
| `api/tests/boot/test_burrow_boot.py` (NEW) | test (integration harness) | event-driven (subprocess) + file-I/O | `api/tests/integration/conftest.py` (loopback-fake substrate) + `api/tests/integration/test_bootconfig.py` (`_SENTINEL_CREDENTIAL` no-leak idiom) | role-match (new tier; reuses two precedents) |
| `api/tests/boot/conftest.py` (NEW, optional) | test fixtures | event-driven | `api/tests/integration/conftest.py` (fixture + ephemeral-port loopback server) | exact (fixture pattern) |
| `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` (NEW) | docs (ADR) | n/a | `docs/adr/ADR-0002-boot-config-pull-at-boot.md` (Status/Context/Decision/Consequences/Revisit-trigger) | exact (ADR template) |

> The harness is the **Python `subprocess`** option (Claude's discretion per CONTEXT.md / RESEARCH Open Question 3). It reuses the existing `pytest` runner and the loopback-fake idiom — zero new CI tooling. If `bats-core` is chosen instead, the analogs for fakes still apply; only the assertion syntax differs.

## Shared Patterns

These cross-cutting patterns apply to multiple new files. Copy them once, reference them everywhere.

### A. Strict-mode + ERR trap (every shell file on the boot path)
**Source:** `cc-worker-config/lxc/host-prime/lib/common.sh` lines 12-28
**Apply to:** `burrow-boot.sh` (the boot script must mirror this shape, plus secret redaction)
```bash
set -euo pipefail
IFS=$'\n\t'

# Print the failing command + line number on any non-zero exit (set -e).
# shellcheck disable=SC2154  # BASH_COMMAND/LINENO are bash built-ins.
err_trap() {
  local exit_code=$?
  printf 'ERROR: command failed (exit %d) at %s:%d: %s\n' \
    "$exit_code" "${BASH_SOURCE[1]:-?}" "${BASH_LINENO[0]:-0}" "${BASH_COMMAND}" >&2
  exit "$exit_code"
}
trap err_trap ERR

# log <message...> — structured-ish stderr line so stdout stays clean for data.
log() {
  printf '[host-prime] %s\n' "$*" >&2
}
```
**Adaptation for `burrow-boot.sh`:** change the log prefix to `[burrow-boot]` (the existing stub uses `log() { echo "[burrow-boot] $*"; }` on line 24 — keep that prefix), and add `$BASH_COMMAND` redaction to the trap per RESEARCH Pattern 3 (`local cmd="${BASH_COMMAND//ghp_*/[redacted]}"`). The redaction is a backstop; the real guarantee is structural (token only ever in a subshell-local env var → `GIT_ASKPASS`).

### B. SPDX two-line header (every source file — non-negotiable, CICD-06)
**Source:** every file in the repo. Shell: `burrow-boot.sh` lines 1-3. Python: `test_bootconfig.py` lines 1-2. Markdown/JSON-with-comment: ADR/CONTEXT front-matter lines 1-4.
**Apply to:** all 6 new files + verify the 2 modified files keep theirs.
```bash
# shell / .sh
#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
```
```python
# python
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
```
> `manifest.json` and `manifest.schema.json` are strict JSON (no comment syntax). Per the repo's REUSE setup these need a `.license` sidecar OR a `REUSE.toml`/`.reuse/dep5` entry — the planner must confirm how the repo currently licenses comment-less files (run `uvx reuse lint`; do NOT add a `//` comment to a `.json` the schema validator must parse).

### C. Sentinel no-leak assertion (every test that touches the credential)
**Source:** `api/tests/integration/test_bootconfig.py` lines 29-30, 126-154
**Apply to:** `test_burrow_boot.py::test_no_credential_leak` (the worker-side analogue of the shipped server-side gate)
```python
# A high-entropy value that cannot occur incidentally; if it shows up in a log
# record or an event blob, the credential leaked (T-01-18, block_on=high).
_SENTINEL_CREDENTIAL = "SENTINEL-bootcred-9f2c4e7a1b6d8054-DO-NOT-LOG"
...
for record in caplog.records:
    rendered = record.getMessage()
    assert _sentinel_token not in rendered, f"credential leaked into log: {rendered!r}"
    for value in record.__dict__.values():
        assert _sentinel_token not in str(value), "credential leaked into a log extra"
```
**Adaptation for the boot harness:** the worker side has no `caplog` (the script is a subprocess), so capture its `stdout`+`stderr` (and the post-boot `/etc/burrow/worker.env` written under a temp `$HOME`) and assert the sentinel token AND the repo URL are absent from every captured byte. The server-side test proves the endpoint never logs the credential; this proves the worker never leaks it post-fetch.

### D. Standard envelope unwrap (`.data`) — boot script ↔ frozen endpoint
**Source:** `api/routers/internal.py` lines 106-113 (the camelCase payload the boot script consumes)
**Apply to:** `burrow-boot.sh` fetch step + the fake control plane in `test_burrow_boot.py`
```python
# api/routers/internal.py — the FROZEN response shape the boot script parses with jq.
payload = {
    "configRepo": settings.config_repo,
    "configBranch": settings.config_branch,
    "projectRepo": ws.project_repo,
    "projectBranch": ws.project_branch,
    "gitCredential": git_credential,
}
return respond(payload)   # wraps in {data, meta, error}
```
**Boot-script consumption (camelCase keys, unwrap `.data`):** `jq -e '.data'` then `.data.configRepo`, `.data.configBranch`, `.data.projectRepo`, `.data.projectBranch`, `.data.gitCredential`. The fake CP in the harness must emit this exact shape (`{"data": {...}, "meta": {...}, "error": null}`) so the script and the real endpoint can never drift. **Contract is frozen — do not change the endpoint (out of scope).**

## Pattern Assignments

### `cc-worker-config/lxc/worker-template/burrow-boot.sh` (boot script, request-response + file-I/O)

**Analogs:** `host-prime/lib/common.sh` (strict-mode/`err_trap`); the file's own Phase-0 stub (frozen ttyd tail + `[burrow-boot]` log prefix); `api/routers/internal.py` (the response contract it consumes).

**What to keep verbatim from the existing stub (lines 22, 24, 95-99) — FROZEN, do not regress:**
```bash
set -euo pipefail
log() { echo "[burrow-boot] $*"; }
...
# --- ttyd: PERSISTENT (no --once, SC-8) + LAN bind (no `lo`, SC-9) ------------
exec ttyd \
  --port 7681 \
  --writable \
  --interface 0.0.0.0 \
  bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"
```
> ADR-0006 (no `--once`) and ADR-0007 (`--interface 0.0.0.0`) freeze this tail. A boot-harness static assertion must grep that `--once` is **absent** and `--interface 0.0.0.0` is **present** (RESEARCH Test Map, last two rows). The `CLAUDE_CMD` rtk-fallback block (lines 78-81) and the `START_DIR` selection (lines 85-88) are also reusable as-is.

**What to replace (lines 26-75, the documented stub):** swap the env-var-default config block for the live pull. New functions, each small (mirrors `common.sh`'s `require_*` decomposition):

1. **`resolve_vmid`** — RESEARCH §"VMID self-resolution" (`hostname -s` → suffix), but the **authoritative mapping is operator-recorded** in `cc-worker-config/lxc/host-prime/30-network-notes.md` / ADR-0004 (VMID ↔ static-IP is operator config; the hostname-suffix convention is illustrative). Validate the parsed VMID is an integer; non-integer → `return 1` → ERR trap. (Pitfall 4: a wrong VMID 404s the endpoint.)

2. **`fetch_bootconfig`** — RESEARCH Pattern 2: bounded retry (~5×, capped backoff), `curl -fsS --max-time 10 "${CONTROL_PLANE}/api/v1/internal/bootconfig/${VMID}"`, then `jq -e '.data'`. Make `CONTROL_PLANE` **required** now (the Phase-0 stub's warn-and-skip on lines 43-48 was explicitly "the `:?` guard returns in Phase 3" — flip it to fail-if-unset).

3. **`clone_with_token`** (the security core) — RESEARCH Pattern 1: in-memory `GIT_ASKPASS` helper inside a **subshell**, `x-access-token` username, `GIT_TERMINAL_PROMPT=0`, `git -c credential.helper=` (empty). Token from `.data.gitCredential` → local → unset after clone. **Never** in the URL, **never** to `/etc/burrow/worker.env`. (Anti-patterns: token-in-URL, env-file persistence, prompt hang.)

4. **`process_manifest`** — RESEARCH §"Manifest iteration with a boot-time jq type gate (fail-closed)": jq structural gate (required keys + `type ∈ {claude-plugin,binary,npm-global}`), unknown/malformed → `return 1` → ERR trap (fail-closed, locked decision). Iterate only `type=="claude-plugin"`; `binary`/`npm-global` are baked (skip).

5. **`install_claude_plugin`** — RESEARCH Pattern 4: `rm -rf "$dest"` then `git clone --depth=1 --branch <ref>` (idempotent, byte-reproducible, SC-2), then `jq '.enabledPlugins[$n]=true'` into `~/.claude/settings.json`. **A1/Open-Q-2:** the exact `enabledPlugins` shape on `claude-code@2.1.170` is [ASSUMED] — confirm at dev-homelab smoke; the master CLAUDE.md copy is independent and must work regardless.

**ERR trap (Shared Pattern A) + redaction (RESEARCH Pattern 3):** install the trap before the first risky line; redact `$BASH_COMMAND` as a backstop.

**Do NOT follow** the tech-spec §9.3 `burrow-boot.sh` snippet (`--once`, `--interface lo`, env-injected config) — it is SC-reversed. The script in this directory is authoritative (RESEARCH §State of the Art).

---

### `cc-worker-config/lxc/worker-template/provision-template.sh` (config/provisioner, batch)

**Analog:** itself, line 34.

**Single edit** — add `jq` to the existing `apt-get install` list (RESEARCH §Environment Availability: `jq` is **absent** and has no viable fallback):
```bash
# line 34, before:
apt-get install -y git curl build-essential ttyd
# after:
apt-get install -y git curl build-essential ttyd jq
```
> Optional second edit ONLY if the planner bakes a Python `jsonschema` boot validator instead of the jq gate: `apt-get install -y python3-jsonschema`. RESEARCH recommends the jq gate at boot (no new worker dep) + the full `jsonschema` schema as the CI source of truth — so the default is **`jq` only**. The existing header comment (lines 17-18, 47-48) already states "claude-plugin types are PULLED AT BOOT (Phase 3) and must NOT be baked" — that bake-vs-pull split is already documented; no change needed there.

---

### `cc-worker-config/plugins/manifest.json` (config data, transform)

**Analog:** RESEARCH §"Manifest JSON-Schema" + `Template.plugin_manifest` (tech-spec §11.1, stored as TEXT JSON).

**Shape** — object keyed by plugin name; each entry `{ source, ref, type }`, `type ∈ {claude-plugin, binary, npm-global}`, `ref` an **immutable** tag/SHA for `claude-plugin` types (SC-2; Pitfall 1 warns against `ref: "main"` for a `claude-plugin`):
```json
{
  "schemaVersion": "1.0.0",
  "plugins": {
    "example-plugin": {
      "source": "github.com/<org>/<plugin-repo>",
      "ref": "v1.2.3",
      "type": "claude-plugin"
    }
  }
}
```
> **No secrets / no real topology** (CLAUDE.md): `source` values are placeholders or public repos. The committed manifest must validate against `manifest.schema.json` (the CI gate below depends on it). The existing baked plugins (`rtk` = binary, `gsd` = npm-global, per `provision-template.sh` lines 49-56) are the reference for the `binary`/`npm-global` entry shapes if listed here for documentation.

---

### `cc-worker-config/plugins/manifest.schema.json` (config schema, transform)

**Analog:** RESEARCH §"Manifest JSON-Schema (the shared source of truth)" — copy verbatim as the starting point.
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Burrow worker plugin manifest",
  "type": "object",
  "required": ["schemaVersion", "plugins"],
  "properties": {
    "schemaVersion": { "type": "string" },
    "plugins": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["source", "ref", "type"],
        "properties": {
          "source": { "type": "string", "minLength": 1 },
          "ref": { "type": "string", "minLength": 1 },
          "type": { "enum": ["claude-plugin", "binary", "npm-global"] },
          "description": { "type": "string" }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```
> This same schema is the source of truth for **both** the CI `pytest` test (`test_manifest_schema.py`) and (if the planner chooses the Python boot validator) the worker boot gate. `additionalProperties: false` + the `enum` is what makes "unknown type fails" provable (the locked fail-closed decision). The boot-time jq gate in `burrow-boot.sh` must enforce the **same** required-keys + enum constraint so the two never diverge.

---

### `api/tests/integration/test_manifest_schema.py` (test/unit, request-response)

**Analog:** `api/tests/integration/test_bootconfig.py` (header docstring style, SPDX, focused assertions) + RESEARCH §"CI schema test (pytest)".

**Imports pattern** (mirror `test_bootconfig.py` lines 1-2 SPDX + stdlib-first imports):
```python
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit: the committed plugin manifest validates against its JSON-Schema (WORK-05).

Catches manifest drift in CI (Pitfall 5) and proves an unknown plugin `type` is
rejected fail-closed (the locked decision)."""
import json
import pathlib
import jsonschema   # add to api/pyproject.toml dev group (4.26.0, verified PyPI)
```

**Core pattern** (RESEARCH §"CI schema test"):
```python
_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root
_MANIFEST = _ROOT / "cc-worker-config" / "plugins" / "manifest.json"
_SCHEMA = _ROOT / "cc-worker-config" / "plugins" / "manifest.schema.json"

def test_committed_manifest_matches_schema() -> None:
    schema = json.loads(_SCHEMA.read_text())
    manifest = json.loads(_MANIFEST.read_text())
    jsonschema.validate(manifest, schema)  # raises ValidationError on drift

def test_unknown_type_is_rejected() -> None:
    schema = json.loads(_SCHEMA.read_text())
    bad = {"schemaVersion": "1.0.0",
           "plugins": {"x": {"source": "s", "ref": "r", "type": "wat"}}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
```
> **Path note:** `parents[3]` from `api/tests/integration/` reaches the repo root — verify the depth against the actual file location (RESEARCH places it in `tests/integration/`; the Project-Structure block also shows it there). Add `import pytest` (the example used `__import__("pytest")` inline — prefer the clean top-level import to match `test_bootconfig.py` line 24). **Dev-dep gate:** adding `jsonschema==4.26.0` to `api/pyproject.toml [dependency-groups].dev` requires a `uv lock` refresh (CI lockfile-freshness gate) — it is a well-known package, not an [ASSUMED] one, so no human-verify checkpoint.

---

### `api/tests/boot/test_burrow_boot.py` (test/integration harness, event-driven subprocess + file-I/O)

**Analogs:** `api/tests/integration/conftest.py` (loopback-fake substrate, ephemeral-port server, fixture lifecycle) + `api/tests/integration/test_bootconfig.py` (`_SENTINEL_CREDENTIAL` no-leak idiom) + `api/tests/e2e/stub_ttyd_server.py` (the "stub binary that records argv and exits" precedent).

**Loopback-fake fixture pattern** (mirror `conftest.py` lines 115-144 — an ephemeral-port server yielded as a handle, torn down via `async with`):
```python
# conftest.py precedent: bind on an ephemeral loopback port, yield the URL, auto-teardown.
async with serve(handler, "127.0.0.1", 0, subprotocols=[...]) as server:
    host, port = server.sockets[0].getsockname()[:2]
    state = StubTtyd(url=f"ws://{host}:{port}")
    yield state
```
**Adaptation:** the boot harness needs a **fake control plane** (Python `http.server` on `127.0.0.1:0`) serving the standard envelope (Shared Pattern D) at `/api/v1/internal/bootconfig/<vmid>` with a **sentinel** `gitCredential`; a "down" variant (refuse / 503) drives the retry-then-fail test. Set `CONTROL_PLANE` in the subprocess env to that loopback URL (RESEARCH §"Hermetic Boot-Harness Strategy" step 3 — the same env-override seam the integration tier uses).

**Fake git remotes** (RESEARCH strategy step 2): `git init --bare` on disk for the config repo (with `claude/CLAUDE.md`, `plugins/manifest.json`, a tag for ref-pinning) and the project repo; point `configRepo`/`projectRepo` + the manifest `source`/`ref` at `file://` paths. Real-but-hermetic clones; the idempotence test compares two cloned trees byte-for-byte.

**Stub `ttyd` on `PATH`** (the `stub_ttyd_server.py` "no real terminal" precedent, applied as a fake binary): a script that records its argv and `exit 0`, prepended to `PATH` for the subprocess, so the boot completes without a real terminal and the test can assert the frozen argv (`--interface 0.0.0.0` present, `--once` absent).

**Drive the script + assert exit codes** (RESEARCH strategy step 4 — `set -euo pipefail` + ERR trap means failure paths must be non-zero):
```python
import subprocess
# run burrow-boot.sh under a temp HOME + temp /etc/burrow, capture all output.
proc = subprocess.run(
    ["bash", str(_BOOT_SCRIPT)],
    env={**base_env, "CONTROL_PLANE": fake_cp_url, "HOME": str(tmp_home)},
    capture_output=True, text=True,
)
assert proc.returncode == 0            # happy path
# failure paths (down CP, bad manifest, unknown type) → assert proc.returncode != 0
```

**Scrub-proof assertion** (Shared Pattern C — the worker-side analogue of `test_bootconfig.py`):
```python
captured = proc.stdout + proc.stderr
assert _SENTINEL_CREDENTIAL not in captured        # token in NO log line
assert fake_project_repo_url not in captured       # repo URL in NO log line
worker_env = (tmp_etc / "burrow" / "worker.env").read_text() if ... else ""
assert _SENTINEL_CREDENTIAL not in worker_env       # token NEVER persisted (SC-3)
```

**Test cases** (RESEARCH Test Map → one test each): `test_fetch_then_clone_happy_path`, `test_bootconfig_retry_then_fail`, `test_bad_manifest_fails_boot`, `test_only_claude_plugins_installed`, `test_two_boots_identical_plugin_tree`, `test_no_credential_leak`, plus the static `test_frozen_ttyd_line` (grep the script for `--once` absent / `--interface 0.0.0.0` present).
> **`testpaths = ["tests"]`** in `pyproject.toml` already includes a new `tests/boot/` dir — no config change needed (add an `__init__.py` to match the existing `tests/integration/__init__.py` and `tests/e2e/__init__.py`). `asyncio_mode = "auto"` is already set, so `async def test_*` works with no decorator (as `test_bootconfig.py` relies on).

---

### `api/tests/boot/conftest.py` (test fixtures, event-driven) — optional but recommended

**Analog:** `api/tests/integration/conftest.py` (lines 39-75: `monkeypatch`-isolated settings + an `async` fixture yielding a live loopback server handle; lines 98-144: a small state class + `serve(...)` on `127.0.0.1, 0`).

Extract the fake-CP server, the bare-repo factory, and the stub-`ttyd`-on-`PATH` setup into fixtures here so each test stays focused (the `conftest.py` precedent keeps the loopback substrate out of the test bodies). SPDX header + module docstring mirror `tests/integration/conftest.py` lines 1-18.

---

### `docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md` (docs/ADR)

**Analog:** `docs/adr/ADR-0002-boot-config-pull-at-boot.md` — copy the section skeleton exactly.

**Structure to mirror** (ADR-0002 headings): front-matter SPDX comment (lines 1-4) → `# ADR-0009: ...` → `## Status` (Accepted) → `## Context` → `## Decision` → `## Consequences` → `## Revisit trigger`.

**Content (from CONTEXT.md B4 decision):**
- **Decision:** cadence = **boot-time-latest** (boot pulls `cc-worker-config` branch HEAD each boot, tech-spec §988); reproducibility comes from **manifest ref-pinning** (each `claude-plugin` pins an immutable tag/SHA), not from snapshotting the config repo per workspace.
- **Context:** note the plugin-type split (`binary`/`npm-global` baked at provision; `claude-plugin` pulled fresh).
- **Consequences:** two boots of the same manifest → identical plugin tree (SC-2); a `ref: "main"` is intentionally non-reproducible "latest" (Pitfall 1).
- **Revisit trigger** (the alternative ADR-0002 records as a fallback): **per-workspace plugin version pinning / snapshot-at-create**, deferred until the manifest stabilizes (CONTEXT.md Deferred Ideas).
> Numbering: ADR-0008 is the highest existing; ADR-0009 is the next free number (verified — `docs/adr/` holds 0001-0008).

## No Analog Found

None. Every new/modified file has a concrete in-repo precedent (the phase is, per RESEARCH §"Don't Hand-Roll" key insight, mostly *wiring* shipped precedents). Two areas carry [ASSUMED] details to confirm at the dev-homelab smoke, not in CI:

| Detail | File | Reason / Action |
|--------|------|------|
| Exact `enabledPlugins` on-disk shape for `claude-code@2.1.170` (directory install) | `burrow-boot.sh` `install_claude_plugin` | A1 / Open-Q-2: documented key, but the precise shape for a directory (non-marketplace) install is [ASSUMED]. Confirm at smoke (`claude plugin list` / `--debug`). Master CLAUDE.md copy is independent and unaffected. |
| Credential username convention (`x-access-token`) | `burrow-boot.sh` `clone_with_token` | A2 / A3: depends on the operator's `mint_repo_credential` mechanism (pending). If it is a deploy-key / GitLab job token, the askpass `Username` branch changes. The frozen endpoint returns the token; the username is operator-config. |
| VMID-from-hostname mechanics | `burrow-boot.sh` `resolve_vmid` | A3: the authoritative VMID↔IP mapping is operator-recorded in `30-network-notes.md` / ADR-0004. The hostname-suffix parse is illustrative; confirm against the real scheme before finalizing. |
| Config-repo auth model | `burrow-boot.sh` config clone | A5 / Open-Q-1: the frozen endpoint mints a credential scoped to the **project** repo only. Default assumption: `cc-worker-config` is operator-reachable (public / same-org). If it needs separate auth, that is a contract question for the operator, NOT a code change (endpoint frozen). |

## Metadata

**Analog search scope:** `cc-worker-config/lxc/{worker-template,host-prime}/`, `cc-worker-config/systemd/`, `api/routers/`, `api/tests/{integration,e2e}/`, `api/pyproject.toml`, `docs/adr/`.
**Files scanned (read in full or targeted):** `burrow-boot.sh`, `common.sh`, `provision-template.sh`, `internal.py`, `test_bootconfig.py`, `tests/integration/conftest.py`, `tests/e2e/stub_ttyd_server.py` (header), `ADR-0002`, `ADR-0004`, `30-network-notes.md`, `pyproject.toml`.
**No skills directory present** (`.claude/skills/` / `.agents/skills/` absent) — patterns derive from `CLAUDE.md` (repo + global) conventions only.
**Pattern extraction date:** 2026-06-11
