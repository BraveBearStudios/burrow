<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 3: Reproducible Workers - Research

**Researched:** 2026-06-11
**Domain:** Bash boot orchestration, git one-shot credential hygiene, plugin-manifest schema validation, hermetic shell/JSON testing
**Confidence:** HIGH (internal substrate + git/bash mechanics) / MEDIUM (Claude Code plugin install internals — a fast-moving CLI)

## Summary

This phase replaces the Phase-0 `burrow-boot.sh` stub with the live pull-at-boot flow: the worker
self-resolves its VMID, calls the **already-shipped** `GET /api/v1/internal/bootconfig/{vmid}`
endpoint (frozen contract, `api/routers/internal.py`), pulls the master `CLAUDE.md` + a
JSON-Schema-validated plugin manifest from `cc-worker-config`, clones the project repo with a
short-lived credential that never touches disk, and `exec`s the frozen persistent/LAN-bound ttyd
into Claude Code. Every failure surfaces through the existing Phase-1 create-saga ttyd-health
timeout as a typed `boot.error` — **no new worker→control-plane endpoint** is added.

The phase is **CI-lint/unit-testable only**. Real Proxmox boot is the dev-homelab smoke gate, not
CI (consistent with WORK-01/03/04 and the project's "Looks Done But Isn't" acceptance authority).
The research therefore concentrates on *hermetic* testing: a `bats-core` (or Python `subprocess`)
harness that drives `burrow-boot.sh` against a fake control-plane HTTP server + fake git remotes on
loopback, and a Python `jsonschema` unit test that pins the manifest schema in CI. The credential
mechanics are the highest-risk surface: the established pattern is an **in-memory `GIT_ASKPASS`
helper in a subshell** feeding `x-access-token:<token>`, never embedding the token in the clone URL
(URL embedding leaks via `ps`, the reflog, and `.git/config` remote).

**Primary recommendation:** Author `burrow-boot.sh` as a set of small functions mirroring the
existing `host-prime/lib/common.sh` `err_trap` + strict-mode idiom; drive `claude-plugin` installs
by **`git clone --depth=1 --branch <ref>` into `~/.claude/plugins/` + an `enabledPlugins` write to
`~/.claude/settings.json`** (not `claude plugin install`, which needs a marketplace and is
network/interactive-fragile); validate the manifest with a baked Python `jsonschema` one-liner at
boot and the same schema in a CI `pytest` test; test the whole script with `bats-core` against
loopback fakes.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| VMID self-resolution | Worker (boot script) | — | The worker is the only place that knows its own hostname/IP (ADR-0004); the control plane keys off the VMID it is given. |
| Bootconfig fetch (repo/branch + credential) | Worker (boot script) → API `/internal/bootconfig` | — | Pull-at-boot (ADR-0002): the worker pulls; the endpoint is frozen and already shipped. |
| Credential minting | API (`mint_repo_credential` seam) | — | Already lives behind `WorkspaceService.mint_repo_credential` (Plan 01-05); the worker only *consumes* the minted token. |
| Manifest schema validation | Worker (boot, fail-closed) | Repo CI (schema unit test) | Boot fails closed on a bad manifest; CI catches manifest drift before it ships. |
| `claude-plugin` install | Worker (boot script, fresh-pull) | — | Pulled fresh each boot from `cc-worker-config` (SC-2 / B4 boot-time-latest). |
| `binary`/`npm-global` install | Golden template (`provision-template.sh`) | — | Baked at provision time (SC-2); never pulled at boot. |
| Boot-failure surfacing | Worker (ERR trap → non-zero exit) | API create-saga (ttyd-health timeout → `boot.error`) | Reuses the Phase-1 path; no new internal threat surface (YAGNI). |
| ttyd launch | Worker (boot script) | — | Frozen contract: persistent (no `--once`, ADR-0006), LAN-bound (`0.0.0.0`, ADR-0007). |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Cadence = boot-time-latest.** Boot pulls the `cc-worker-config` branch HEAD each boot
  (tech-spec §988). Reproducibility comes from **manifest ref-pinning** (each `claude-plugin` entry
  pins an immutable git tag/commit SHA), not from snapshotting the config repo per workspace.
  Recorded as **ADR-0009**; the ADR notes the snapshot-at-create alternative and the revisit trigger
  (per-workspace pinning once the manifest stabilizes).
- **Manifest = `cc-worker-config/plugins/manifest.json`** (JSON, tech-spec §11.1). Entry schema:
  `{ name, type: claude-plugin|binary|npm-global, source, ref }`. JSON-Schema validated **at boot**
  (malformed → non-zero, ERR-trapped) AND by an **in-repo schema unit test** in CI. An unknown /
  unsupported `type` at boot **fails the boot**.
- **Plugin-type split:** `binary` + `npm-global` are baked into the golden template at provision
  time; only `claude-plugin` types are pulled fresh at boot.
- **Boot-failure surfacing:** keep `set -euo pipefail`, add an **ERR trap** that logs a redacted
  line and exits non-zero. The control-plane create-saga ttyd-health timeout records the typed
  `boot.error`. **No new worker→control-plane endpoint.**
- **Bootconfig GET = bounded retry** (~5 attempts, capped backoff) then fail.
- **Credential** fed to `git clone` via an **in-memory `GIT_ASKPASS` / credential helper inside a
  subshell** — never on disk, never in `/etc/burrow/worker.env`, unset after clone, **never embedded
  in a clone URL**.
- **A scrub-proof test** asserts no token in `worker.env` post-boot and that the repo URL /
  credential never appears in any logged line or event payload.

### Claude's Discretion

- Exact retry counts / backoff curve.
- VMID-from-hostname resolution mechanics.
- Test harness choice (`bats-core` / `shunit2` vs a Python `subprocess` harness).
- ADR-0009 prose.

### Deferred Ideas (OUT OF SCOPE)

- Per-workspace plugin version pinning / snapshot-at-create cadence (ADR-0009 revisit trigger).
- A dedicated worker→control-plane boot-status POST endpoint (the saga health-timeout path covers
  `boot.error` for v1).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WORK-02 | Worker boots via `burrow-boot.sh`: pulls CLAUDE.md + plugin manifest from `cc-worker-config`, clones the project repo, launches ttyd shelling into Claude Code | "Architecture Patterns" (boot flow, fetch+retry, clone-with-askpass, ttyd exec); "Code Examples" (askpass helper, bounded retry, VMID resolution); the frozen `/internal/bootconfig` contract in `api/routers/internal.py` is the consumed dependency |
| WORK-05 | Plugin set is a versioned manifest; `claude-plugin` types pulled fresh at boot, `binary`/`npm-global` baked into template | "Manifest Schema & Validation" (JSON-Schema + the three install paths); "Don't Hand-Roll" (use git ref-pinning, not a bespoke version lockfile); idempotent-install pattern |

## Project Constraints (from CLAUDE.md)

The planner must verify every task honors these (same authority as locked decisions):

- **SPDX two-line header on every source file** — the boot script, the manifest's schema file,
  every test file, and the ADR all carry the AGPL-3.0-or-later header in the language's comment
  syntax. `uvx reuse lint` is a CI gate (CICD-06).
- **Conventional Commits** (`feat:`/`fix:`/`docs:`/`test:`/`chore:`); PR title must itself be a
  valid Conventional Commit (squash-merge).
- **Structured (JSON) logging on the backend.** The worker boot script logs to stdout/journald with
  a `[burrow-boot]` prefix (it is shell, not the Python backend) — but **no secret may ever reach a
  log line** (the scrub-proof test enforces this end-to-end).
- **Never commit secrets.** No real tokens/hostnames in the script, the manifest, tests, or
  fixtures. `.env` is gitignored; `.env.example` is the only template. Topology values are
  placeholders.
- **Tests with every change**; every bug fix lands a failing-first regression test in the right tier
  (CICD-03).
- **Provider seams stay clean** — the boot script consumes the HTTP endpoint only; it never reaches
  into Proxmox or SQLite specifics (it cannot — it is a worker-side shell script).
- **v1 is LAN-only, no auth** — do not add auth assumptions into the boot path. The bootconfig
  endpoint's source-IP check is defense-in-depth, off by default (Plan 01-05).
- **camelCase JSON ↔ snake_case** — the endpoint already returns `configRepo`, `configBranch`,
  `projectRepo`, `projectBranch`, `gitCredential` (camelCase); the boot script parses these exact
  keys with `jq`.

## Standard Stack

### Core (already present in the worker template / repo)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `bash` | 5.x (Ubuntu 24.04) | Boot orchestration | The boot script is shell by design; the unit (`burrow-worker.service`) execs it. `[VERIFIED: codebase]` |
| `git` | distro | Clone config + project repos | Already `apt-get install`-ed in `provision-template.sh`. `[VERIFIED: codebase]` |
| `curl` | distro | Bootconfig GET (`-fsSL`) | Already baked; the stub already uses it. `[VERIFIED: codebase]` |
| `jq` | distro (**add to bake**) | Parse the camelCase bootconfig JSON + iterate the manifest | jq is the standard for shell JSON parsing; it is **not yet** in `provision-template.sh`'s `apt-get install` list — add it. `[VERIFIED: codebase — absent]` |
| `ttyd` | distro | Persistent LAN-bound terminal | Frozen contract (ADR-0006/0007); already baked + the `exec ttyd ...` line is frozen. `[VERIFIED: codebase]` |
| `@anthropic-ai/claude-code` | 2.1.170 (pinned) | The agent the ttyd shell launches | Already baked in `provision-template.sh`. `[VERIFIED: codebase]` |

### Supporting (CI / test side)

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `bats-core` | 1.x (via `bats-core/bats-action@4.0.0`) | Hermetic bash unit/integration tests for `burrow-boot.sh` | The recommended harness — drives the script against loopback fakes. `[CITED: github.com/bats-core/bats-action]` |
| `jsonschema` (PyPI) | 4.26.0 | In-repo manifest schema unit test (CI) + the baked boot-time validator | `pip index versions jsonschema` → 4.26.0; importable under the repo's uv env. `[VERIFIED: PyPI]` |
| `pytest` | 9.0.3 (already a dev dep) | Host the manifest-schema test and (optionally) a Python `subprocess` boot harness | Already the project test runner; reuse it for the schema test. `[VERIFIED: codebase pyproject.toml]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `bats-core` shell harness | Python `subprocess` harness in `pytest` | Python keeps everything in the existing `pytest` CI job (one runner, one report) and reuses the loopback-fake idioms already in `tests/integration/conftest.py`. `bats-core` is more idiomatic for shell and gives clean per-`@test` isolation but adds a second CI tool + a setup action. **Either satisfies the locked decision (Claude's discretion).** Recommendation: Python `subprocess` harness if you want zero new CI tooling; `bats-core` if you want shell-native assertions. |
| Baked Python `jsonschema` boot validator | Pure-`jq` structural check at boot | `jq` can assert required keys + enum membership without a Python dep on the worker, keeping the boot path dependency-light. But the *same* schema then can't be shared verbatim with the CI test. Recommendation: a small `jq` "type ∈ {claude-plugin,binary,npm-global} and required keys present" gate at boot (fast, no new worker dep), plus the full `jsonschema` schema as the CI source of truth. If you prefer one schema everywhere, bake `python3 -m jsonschema` (Ubuntu 24.04 ships `python3`; add the `python3-jsonschema` apt package or `pip install`). |
| `git clone` into `~/.claude/plugins/` + `enabledPlugins` write | `claude plugin install <name>@<marketplace>` | The CLI install path requires a **marketplace** registration and is network-/interactive-fragile (and historically thin on non-interactive guarantees — see Pitfall 2). A pinned `git clone` of the plugin repo into the cache dir + a settings write is fully hermetic, byte-reproducible via the pinned ref, and matches what the Phase-0 stub already does (`cp -r ... ~/.claude/plugins/`). Recommendation: **clone + settings write.** `[CITED: code.claude.com/docs/en/plugins-reference]` |

**Installation (template bake additions to `provision-template.sh`):**
```bash
apt-get install -y git curl build-essential ttyd jq   # add jq
# optional, only if you bake the Python schema validator instead of the jq gate:
# apt-get install -y python3-jsonschema
```

## Package Legitimacy Audit

> This phase installs **no new application packages** into the API. The only new dependencies are
> developer/CI tools and one OS package; audited below.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `jq` | apt (Ubuntu 24.04 universe) | 10+ yrs | distro-standard | github.com/jqlang/jq | n/a (OS pkg) | Approved — bake into template |
| `jsonschema` | PyPI | mature (4.x line, years) | very high | github.com/python-jsonschema/jsonschema | OK (manual: long history, canonical impl) | Approved — CI dev dep / optional bake |
| `bats-core` | GitHub Action `bats-core/bats-action@4.0.0` | mature | n/a | github.com/bats-core/bats-core | n/a (CI action) | Approved if chosen — SHA-pin the action (CI convention) |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

*slopcheck was not run as a tool in-session (no new PyPI/npm app deps were introduced); `jsonschema`
is the canonical, long-lived reference implementation verified on PyPI (4.26.0) and importable under
the repo's uv env. If the planner chooses to add `jsonschema` to `api/pyproject.toml` dev-group,
gate it behind the normal lockfile-freshness CI step rather than a human-verify checkpoint — it is a
well-known package, not an [ASSUMED] one.*

## Architecture Patterns

### System Architecture Diagram

```
                         WORKER LXC (clone of golden template, booting)
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │ systemd: burrow-worker.service ──ExecStart──► /opt/burrow-boot.sh             │
  │                                                                                │
  │  set -euo pipefail + ERR trap (redacted log + non-zero exit)                   │
  │      │                                                                         │
  │      ▼                                                                         │
  │  (1) VMID = resolve_vmid()  ◄── hostname / static IP (ADR-0004)               │
  │      │                                                                         │
  │      ▼   bounded retry (~5×, capped backoff)                                   │
  │  (2) curl GET ${CONTROL_PLANE}/api/v1/internal/bootconfig/${VMID} ───────────────┐
  │      │     └─ jq → configRepo, configBranch, projectRepo, projectBranch,       │ │
  │      │            gitCredential   (camelCase envelope .data)                   │ │
  │      ▼                                                                         │ │
  │  (3) GIT_ASKPASS subshell (token in-mem only) ─► git clone config repo @branch │ │
  │      │     ├─ cp claude/CLAUDE.md  → ~/CLAUDE.md                              │ │
  │      │     └─ read plugins/manifest.json                                       │ │
  │      ▼                                                                         │ │
  │  (4) validate manifest (jq gate / jsonschema) — bad type/shape ⇒ exit ≠0       │ │
  │      │                                                                         │ │
  │      ▼   for each entry where type==claude-plugin:                            │ │
  │  (5) git clone --depth=1 --branch <ref> <source> ~/.claude/plugins/<name>     │ │
  │      │            + enable in ~/.claude/settings.json (idempotent)             │ │
  │      │      (binary/npm-global: SKIP — baked at provision time)               │ │
  │      ▼                                                                         │ │
  │  (6) GIT_ASKPASS subshell ─► git clone project repo @branch → ~/project        │ │
  │      │     └─ unset askpass / discard token (never to /etc/burrow/worker.env)  │ │
  │      ▼                                                                         │ │
  │  (7) exec ttyd --port 7681 --writable --interface 0.0.0.0 \                    │ │
  │           bash -lc "cd ~/project && exec ${CLAUDE_CMD}"   [FROZEN]             │ │
  └──────────────────────────────────────────────────────────────────────────────┘ │
                                                                                     │
  CONTROL PLANE (already shipped, Phase 1) ◄────────────────────────────────────────┘
  GET /api/v1/internal/bootconfig/{vmid}: vmid-in-pool gate → get_by_vmid →
     mint_repo_credential(project_repo) → {configRepo, configBranch, projectRepo,
     projectBranch, gitCredential}.  Credential returned ONCE, never logged.

  BOOT FAILURE PATH (no new endpoint):
     burrow-boot.sh exits non-zero ⇒ ttyd never comes up ⇒ create-saga step-6
     ttyd-health poll times out ⇒ WorkspaceService logs typed boot.error (redacted
     via _safe()) + compensates.  (Restart=on-failure retries transient boots.)
```

### Recommended Project Structure

```
cc-worker-config/
├── claude/
│   └── CLAUDE.md                       # master worker CLAUDE.md (authored this phase)
├── plugins/
│   ├── manifest.json                   # the versioned plugin manifest (tech-spec §11.1)
│   ├── manifest.schema.json            # JSON-Schema for the manifest (CI + boot validate)
│   └── <plugin>/install.sh             # binary/npm-global bake scripts (template-side)
└── lxc/worker-template/
    └── burrow-boot.sh                  # the live pull-at-boot script (replaces the stub)

api/tests/
├── integration/
│   └── test_manifest_schema.py         # pytest: manifest.json validates against schema (CI gate)
└── boot/                               # NEW tier (or tests/e2e/) for the boot-script harness
    ├── test_burrow_boot.bats           # bats-core harness  (OR)
    └── test_burrow_boot.py             # Python subprocess harness
                                        #   + a loopback fake control-plane + fake git remotes
```

### Pattern 1: In-memory GIT_ASKPASS one-shot credential (the security core)

**What:** Feed the short-lived token to `git` via `GIT_ASKPASS` pointing at a tiny helper that
echoes the token from an env var that lives only inside a subshell. The token is **never** in the
clone URL, never on disk, and is gone when the subshell exits.

**When to use:** Every authenticated clone (config repo if private; project repo always).

**Why not the URL:** `git clone https://x-access-token:TOKEN@host/repo` leaks the token via `ps
aux` (the full command line is world-readable on Linux), the shell history, `~/.git-credentials` if
a helper caches it, and `.git/config`'s saved `remote.origin.url`.

```bash
# Source: synthesis of git-scm gitcredentials docs + GitHub App installation-token convention.
# clone_with_token <token> <url> <dest> <branch> [extra git args...]
clone_with_token() {
  local token="$1" url="$2" dest="$3" branch="$4"; shift 4
  # Run the whole clone in a SUBSHELL so GIT_ASKPASS_TOKEN can never escape it.
  (
    export GIT_ASKPASS_TOKEN="$token"
    # GIT_ASKPASS is invoked twice: once for "Username for ...", once for "Password for ...".
    # For a GitHub App installation token / fine-grained PAT the username is the literal
    # "x-access-token" and the password is the token (per GitHub clone-with-app convention).
    export GIT_ASKPASS
    GIT_ASKPASS="$(mktemp)"
    cat >"$GIT_ASKPASS" <<'ASK'
#!/usr/bin/env bash
case "$1" in
  Username*) printf 'x-access-token\n' ;;
  *)         printf '%s\n' "$GIT_ASKPASS_TOKEN" ;;
esac
ASK
    chmod 700 "$GIT_ASKPASS"
    # GIT_TERMINAL_PROMPT=0 makes a missing/invalid credential fail fast instead of hanging.
    GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
      clone --branch "$branch" "$@" "$url" "$dest"
    local rc=$?
    rm -f "$GIT_ASKPASS"           # remove the helper script (it never contained the token)
    return $rc
  )
  # token + askpass are gone here: subshell exited, env vars not exported to the parent.
}
```

Notes the planner must capture as task verification:
- `git -c credential.helper=` (empty) **disables** any inherited credential helper so the token is
  never persisted to a store.
- The askpass helper script contains **no secret** (it reads the token from the env at call time);
  still `chmod 700` and `rm` it.
- The token comes from the bootconfig `.data.gitCredential`; assign it to a local, pass it into
  `clone_with_token`, then `unset` it. Never write it to `/etc/burrow/worker.env`.

### Pattern 2: Bounded-retry bootconfig GET with capped backoff

**What:** ~5 attempts with capped (e.g. min(2^n, 30)s) backoff; fail (non-zero) after the budget.
**When:** The one HTTP call to the control plane; a transient CP blip must not abort an otherwise-
good boot, but a real outage must surface as `boot.error`, not an infinite hang.

```bash
# fetch_bootconfig <control_plane> <vmid>  -> echoes the .data JSON on stdout, or returns non-zero.
fetch_bootconfig() {
  local cp="$1" vmid="$2" attempt=0 max=5 delay=1 body
  while (( attempt < max )); do
    attempt=$((attempt+1))
    if body="$(curl -fsS --max-time 10 "${cp}/api/v1/internal/bootconfig/${vmid}")"; then
      # Unwrap the standard envelope; a 404 (out-of-pool / no workspace) is -f-failed above.
      jq -e '.data' <<<"$body" && return 0
    fi
    log "bootconfig attempt ${attempt}/${max} failed; retrying in ${delay}s"
    sleep "$delay"
    delay=$(( delay*2 > 30 ? 30 : delay*2 ))   # capped backoff
  done
  log "bootconfig fetch exhausted ${max} attempts — failing boot"
  return 1
}
```

### Pattern 3: ERR trap that redacts then exits non-zero (mirror `common.sh`)

**What:** The repo already has the canonical pattern in `cc-worker-config/lxc/host-prime/lib/common.sh`
(`err_trap` prints the failing line + exits the code). Reuse the shape, but **redact** any
secret-shaped token from `$BASH_COMMAND` before logging (defense-in-depth even though the credential
should never be on a command line).

```bash
# Mirror host-prime/lib/common.sh err_trap, plus secret redaction on the failing command text.
err_trap() {
  local rc=$?
  # Never echo a token: scrub a github-token-shaped or long-opaque substring from the line.
  local cmd="${BASH_COMMAND//ghp_*/[redacted]}"
  printf '[burrow-boot] ERROR (exit %d) at %s:%d: %s\n' \
    "$rc" "${BASH_SOURCE[0]:-?}" "${BASH_LINENO[0]:-0}" "$cmd" >&2
  exit "$rc"
}
trap err_trap ERR
```

> The redaction here is a backstop. The **real** guarantee is structural: the token is only ever in
> a subshell-local env var fed to `GIT_ASKPASS`, never on a command line, so it cannot appear in
> `$BASH_COMMAND` in the first place. The scrub-proof test (Validation Architecture) proves both.

### Pattern 4: `claude-plugin` install = pinned clone + settings enable (idempotent)

**What:** For each manifest entry with `type == "claude-plugin"`, `git clone --depth=1 --branch
<ref>` the `source` into `~/.claude/plugins/<name>` and ensure it is enabled in
`~/.claude/settings.json`. Idempotent: a re-boot wipes/re-clones to the pinned ref so two boots of
the same manifest produce a byte-identical plugin tree (SC-2).

```bash
install_claude_plugin() {           # install_claude_plugin <name> <source> <ref>
  local name="$1" source="$2" ref="$3" dest="$HOME/.claude/plugins/$name"
  rm -rf "$dest"                     # idempotent: same manifest ⇒ same tree (Pitfall 1)
  git clone --depth=1 --branch "$ref" "https://$source" "$dest"
  # enable in settings.json via jq (create the file if absent); enabledPlugins keyed by name.
  local settings="$HOME/.claude/settings.json"
  [[ -f "$settings" ]] || echo '{}' >"$settings"
  local tmp; tmp="$(mktemp)"
  jq --arg n "$name" '.enabledPlugins[$n] = true' "$settings" >"$tmp" && mv "$tmp" "$settings"
}
```

> Confidence MEDIUM on the exact enablement key. `[CITED: code.claude.com/docs/en/plugins-reference]`
> documents `enabledPlugins` in the scope settings file (`~/.claude/settings.json` for `user` scope)
> and `~/.claude/plugins/` as the plugin location. The reference's first-class install path is
> `claude plugin install <name>@<marketplace>` which copies into `~/.claude/plugins/cache` — but
> that needs a marketplace and is network-fragile (Pitfall 2). The clone+enable approach is what the
> Phase-0 stub already does in spirit (`cp -r ... ~/.claude/plugins/`) and is fully hermetic. **The
> precise `enabledPlugins` schema is an [ASSUMED] detail to confirm against the installed
> `claude-code@2.1.170` on the dev-homelab smoke** — flag for human verify there.

### Anti-Patterns to Avoid

- **Token in the clone URL** (`https://x-access-token:$TOKEN@host/...`) — leaks via `ps`, reflog,
  `.git/config`. Use `GIT_ASKPASS` (Pattern 1).
- **Writing the credential to `/etc/burrow/worker.env`** — the whole point of pull-at-boot
  (ADR-0002) is that secrets never persist on the worker. The env file holds only non-secret
  `CONTROL_PLANE` (and is optional).
- **A new worker→CP "boot-status" POST** — explicitly deferred; reuse the saga health-timeout
  `boot.error` path (no new threat surface, YAGNI).
- **Pulling `binary`/`npm-global` at boot** — these are baked; pulling them at boot is slow and
  defeats reproducibility. Boot only touches `claude-plugin` types.
- **Silent manifest degradation** — an unknown `type` or malformed manifest must **fail the boot**
  (non-zero), not skip-and-continue. Fail-closed is the locked decision.
- **`set -e` swallowed by a pipe/subshell** — `set -euo pipefail` + verifying retry loops return
  explicit codes; do not let a `cmd || true` mask a real failure on the boot path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Plugin version reproducibility | A bespoke per-workspace lockfile / hash-of-tree snapshot | Git **ref-pinning** in the manifest (`ref` = tag/SHA) + fresh clone at the pinned ref | The locked B4 decision; git already gives immutable, verifiable refs. A custom lockfile re-invents what `git clone --branch <sha>` does for free. |
| One-shot git auth | A custom token-injecting wrapper that rewrites the URL | `GIT_ASKPASS` + `credential.helper=` (Pattern 1) | The standard, leak-resistant mechanism; URL rewriting is the classic leak vector. |
| JSON parsing in bash | `grep`/`sed`/`awk` over JSON | `jq` (already standard; bake it) | Hand-rolled JSON parsing is fragile and a known footgun; jq is the canonical tool. |
| Manifest validation | Ad-hoc `if [[ $type == ... ]]` chains as the *only* gate | JSON-Schema (`jsonschema` in CI; jq enum gate at boot) | A schema is declarative, shared between CI and boot, and catches shape/enum/required-key drift in one place. |
| Boot-failure plumbing | A new endpoint + worker→CP callback | The existing create-saga ttyd-health timeout → `boot.error` (`WorkspaceService`) | Already shipped, redaction-tested (`_safe()`), and avoids a new internal attack surface. |
| Secret redaction in logs | A new redaction routine on the worker | The boot path's structural guarantee (token only ever in a subshell) + the existing `_safe()` precedent on the CP side | Two redaction layers already exist; the worker's job is to *never put the token where it could leak*. |

**Key insight:** Almost everything risky here already has a shipped, tested precedent in this repo
(the `err_trap`/strict-mode idiom in `common.sh`, the `_safe()` redaction + no-cred-in-logs test in
Plan 01-05, the loopback-fake test substrate in `tests/integration/conftest.py`). The phase is
mostly *wiring* those precedents into `burrow-boot.sh`, not inventing new mechanisms.

## Runtime State Inventory

> This is a script-replacement phase (the Phase-0 `burrow-boot.sh` stub → live flow) plus new
> artifacts. It is **not** a rename/rebrand. There is no stored-data migration. The categories below
> are answered for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — the worker is ephemeral; nothing persists a renamed key. The control-plane DB is untouched (the endpoint contract is frozen). | None — verified by reading `api/routers/internal.py` (no schema change) and ADR-0002 (frozen contract). |
| Live service config | The golden template is built by `host-prime/20-create-template.sh`, which pushes `burrow-boot.sh` into the template CT. The live template image carries the OLD stub until rebuilt. | **Template rebuild is a dev-homelab action**, not CI: after `burrow-boot.sh` changes, the operator re-runs `20-create-template.sh` so new clones get the live script. Note this in the ADR/SUMMARY as a smoke-gate step. |
| OS-registered state | `burrow-worker.service` (systemd unit) runs the script; the unit itself is unchanged (it just `ExecStart`s `/opt/burrow-boot.sh`). | None to the unit. The `EnvironmentFile=-/etc/burrow/worker.env` channel stays (now carries only non-secret `CONTROL_PLANE`). |
| Secrets / env vars | `/etc/burrow/worker.env` currently a placeholder; the Phase-0 stub flips `CONTROL_PLANE` to a warn-and-skip. Phase 3 makes `CONTROL_PLANE` required (the stub's `:?` guard "returns in Phase 3"). The git credential is **never** written here. | Boot script: make `CONTROL_PLANE` required (fail if unset, since the live fetch depends on it). No new secret lands in the env file. |
| Build artifacts | `jq` (and optionally `python3-jsonschema`) must be added to `provision-template.sh`'s `apt-get install` so the live boot script's dependencies exist in the template. | Add `jq` to the bake; rebuild the template (dev-homelab). |

**The canonical question — after the repo is updated, what still has the old behavior?** The
**golden template image** in the homelab still runs the old stub until `20-create-template.sh` is
re-run. That re-build + a create→boot smoke is the acceptance authority; CI cannot prove it.

## Common Pitfalls

### Pitfall 1: Non-idempotent plugin install → two boots differ
**What goes wrong:** A second boot `git pull`s a moving branch, or appends to a plugin dir that
already has files, so the plugin tree drifts between boots (violates SC-2).
**Why it happens:** Cloning a branch (`main`) instead of a pinned ref, or not wiping the dest before
re-clone.
**How to avoid:** Pin every `claude-plugin` `ref` to a tag/SHA in the manifest; `rm -rf` the dest
then `git clone --depth=1 --branch <ref>` (Pattern 4). Test: two runs over the same manifest produce
identical trees.
**Warning signs:** A manifest entry with `ref: "main"` (mutable) for a `claude-plugin` type — the
schema/CI test should flag non-immutable refs, or at least the ADR must document that `main` means
"latest" and is intentionally non-reproducible.

### Pitfall 2: Relying on `claude plugin install` at boot (network/marketplace fragility)
**What goes wrong:** `claude plugin install <name>@<marketplace>` needs a registered marketplace,
talks to the network, and historically lacked strong non-interactive guarantees (the closed
not-planned feature request #19522 asked for exactly this). A boot that depends on it can hang or
fail opaquely.
**Why it happens:** Treating the marketplace CLI as the install API when the requirement is a
hermetic, pinned, offline-reproducible copy.
**How to avoid:** Use the pinned-`git clone` + `enabledPlugins` write (Pattern 4). Confirm the
enablement key against the installed `claude-code@2.1.170` at the dev-homelab smoke.
**Warning signs:** Any boot step that calls `claude plugin ...` and depends on its exit code/timing.

### Pitfall 3: `git clone` hangs on a credential prompt instead of failing
**What goes wrong:** A bad/expired token makes `git` prompt on the terminal; under systemd there is
no TTY, so it hangs — the boot never finishes and the only signal is the saga timeout (slow).
**Why it happens:** `GIT_TERMINAL_PROMPT` defaults to allowing prompts; askpass not wired.
**How to avoid:** `GIT_TERMINAL_PROMPT=0` (fail fast) + `GIT_ASKPASS` set (Pattern 1). A bad token
then exits non-zero quickly → ERR trap → non-zero → fast `boot.error`.
**Warning signs:** Boots that time out at exactly the saga health-poll budget rather than failing
fast.

### Pitfall 4: VMID self-resolution mismatch → 404 from the endpoint
**What goes wrong:** The worker resolves the wrong VMID (e.g. parses the hostname wrong), the
endpoint 404s (out-of-pool or no-workspace), and the boot fails confusingly.
**Why it happens:** The static-IP/hostname → VMID scheme (ADR-0004, `30-network-notes.md`) is the
single source of truth and must be parsed exactly.
**How to avoid:** Resolve VMID from the same scheme the control plane uses to *assign* the static IP
(ADR-0004). Document the resolution in the script + test it against known hostname/IP fixtures.
**Warning signs:** A 404 from `/internal/bootconfig` on a freshly-created workspace whose row exists.

### Pitfall 5: Manifest schema drift not caught until boot
**What goes wrong:** Someone edits `manifest.json` with a typo'd `type` or a missing key; it only
fails on a real worker boot in the homelab, late.
**Why it happens:** No CI gate validating the committed manifest against the schema.
**How to avoid:** The in-repo `pytest` test (`test_manifest_schema.py`) validates the committed
`manifest.json` against `manifest.schema.json` on every CI run — the locked "schema unit test
in-repo so manifest drift is caught in CI."
**Warning signs:** Manifest edits landing without a corresponding green schema test.

### Pitfall 6: Secret leaking into a log line via an error message
**What goes wrong:** A `git` error echoes the URL (with an embedded token) or the failing command
includes the token, and it lands in journald / the `boot.error` reason.
**Why it happens:** Token embedded in URL (anti-pattern), or `set -x` left on, or an un-redacted
trap.
**How to avoid:** Never put the token in the URL (Pattern 1); never `set -x` on the boot path; the
ERR trap redacts `$BASH_COMMAND` (Pattern 3); the CP-side `_safe()` already scrubs the `boot.error`
reason. The scrub-proof test asserts the sentinel token is absent from every captured line and from
`worker.env`.
**Warning signs:** `set -x` anywhere in `burrow-boot.sh`; a token-in-URL clone; an un-redacted trap.

## Code Examples

### VMID self-resolution from hostname (ADR-0004 scheme)
```bash
# The control plane assigns a static IP derived from VMID (ADR-0004); the worker
# resolves its VMID from its hostname or its static IP. EXACT scheme is per
# 30-network-notes.md — this illustrates a hostname-suffix convention; confirm the
# real scheme against the network notes before finalizing.
resolve_vmid() {
  local host; host="$(hostname -s)"      # e.g. "burrow-w-241"
  local vmid="${host##*-}"               # → "241"
  [[ "$vmid" =~ ^[0-9]+$ ]] || { log "cannot resolve VMID from hostname '$host'"; return 1; }
  printf '%s\n' "$vmid"
}
```

### Manifest iteration with a boot-time jq type gate (fail-closed)
```bash
# Validate + iterate. Unknown type ⇒ non-zero (ERR trap fires). claude-plugin only.
process_manifest() {
  local manifest="$1"
  # structural gate: every entry has name/type/source/ref and a known type.
  jq -e '
    .plugins
    | to_entries
    | all(.value | (.type|type=="string") and (.source|type=="string") and (.ref|type=="string")
                   and (.type | IN("claude-plugin","binary","npm-global")))
  ' "$manifest" >/dev/null || { log "manifest failed structural validation"; return 1; }

  # install only claude-plugin types (binary/npm-global are baked).
  while IFS=$'\t' read -r name source ref; do
    install_claude_plugin "$name" "$source" "$ref"
  done < <(jq -r '.plugins | to_entries[]
                  | select(.value.type=="claude-plugin")
                  | [.key, .value.source, .value.ref] | @tsv' "$manifest")
}
```

### Manifest JSON-Schema (the shared source of truth)
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

### CI schema test (pytest, reuses the repo's runner)
```python
# api/tests/integration/test_manifest_schema.py  (illustrative)
import json, pathlib
import jsonschema   # add to api/pyproject.toml dev group (4.26.0, verified on PyPI)

_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root
_MANIFEST = _ROOT / "cc-worker-config" / "plugins" / "manifest.json"
_SCHEMA = _ROOT / "cc-worker-config" / "plugins" / "manifest.schema.json"

def test_committed_manifest_matches_schema() -> None:
    schema = json.loads(_SCHEMA.read_text())
    manifest = json.loads(_MANIFEST.read_text())
    jsonschema.validate(manifest, schema)  # raises ValidationError on drift (Pitfall 5)

def test_unknown_type_is_rejected() -> None:
    schema = json.loads(_SCHEMA.read_text())
    bad = {"schemaVersion": "1.0.0",
           "plugins": {"x": {"source": "s", "ref": "r", "type": "wat"}}}
    with __import__("pytest").raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pct push` / cloud-init env injection of `worker.env` | Pull-at-boot HTTP fetch (ADR-0002) | Phase 0 | The boot script *pulls* config; no secret is pushed/persisted. |
| Token in clone URL | `GIT_ASKPASS` one-shot in subshell | this phase | No token on a command line / in `.git/config`. |
| ttyd `--once` + `--interface lo` (tech-spec §9.3 snippet) | Persistent + `--interface 0.0.0.0` (ADR-0006/0007) | Phase 0 | The `exec ttyd` line is FROZEN — do not re-introduce the spec snippet's flags. |
| `claude plugin install` via marketplace | Pinned `git clone` into `~/.claude/plugins/` + `enabledPlugins` | this phase | Hermetic, byte-reproducible, offline-capable. |

**Deprecated/outdated:**
- The tech-spec §9.3 `burrow-boot.sh` snippet (`--once`, `--interface lo`, env-injected config) is
  SC-reversed — do **not** follow it. The frozen script in `cc-worker-config/lxc/worker-template/`
  is authoritative.
- Non-interactive `claude --not-interactive /plugin install` was requested and **closed as not
  planned** (`anthropics/claude-code#19522`). Do not depend on it; use clone+enable.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `enabledPlugins` in `~/.claude/settings.json` (user scope) is the correct key to enable a directory-installed `claude-plugin` for `claude-code@2.1.170` | Pattern 4 | Plugins clone but don't load; the master CLAUDE.md still lands, so the worker boots — degraded, not broken. **Confirm at dev-homelab smoke.** |
| A2 | The short-lived credential authenticates as `x-access-token:<token>` (GitHub App installation token / fine-grained PAT convention) | Pattern 1 | If the operator's A3 mechanism uses a different username (e.g. a deploy-key or a GitLab job token), the askpass helper's `Username` branch must change. The `mint_repo_credential` seam returns the token; the **username convention is operator-config to confirm (A3, still pending per STATE.md)**. |
| A3 | VMID is resolvable from the worker hostname suffix | Code Examples (resolve_vmid) | If the homelab hostname scheme differs, resolution fails → 404. **Confirm against `30-network-notes.md` / ADR-0004 before finalizing.** |
| A4 | `jq` is sufficient for the boot-time structural gate (vs a full `jsonschema` validator on the worker) | Manifest patterns | If a richer constraint is needed (e.g. ref-immutability), the jq gate must grow or be replaced by the baked Python validator. Low risk — the jq gate covers required-keys + enum. |
| A5 | The CONFIG repo (`cc-worker-config`) is reachable by the worker with the same credential as the project repo (or is public) | Boot flow | If `cc-worker-config` needs a *separate* credential, the endpoint contract (which mints one credential for `project_repo`) would need extension — but the contract is **frozen**. Likely `cc-worker-config` is operator-owned and reachable (public or same-org token). **Confirm the config-repo auth model.** |

## Open Questions

1. **Config-repo credential vs project-repo credential.**
   - What we know: `/internal/bootconfig` mints one credential scoped to `ws.project_repo`. The
     config repo (`cc-worker-config`) is fetched too.
   - What's unclear: whether the config repo is public/operator-reachable without a credential, or
     needs its own. The frozen endpoint mints only for the project repo.
   - Recommendation: Assume `cc-worker-config` is reachable (public or same-org). If it needs auth,
     that is a **contract question for the operator**, not a code change in this phase (the endpoint
     is frozen) — flag in discuss/plan, default to "config repo reachable."

2. **Exact `enabledPlugins` schema for `claude-code@2.1.170`.**
   - What we know: the plugins-reference documents `enabledPlugins` + `~/.claude/plugins/` + the
     `claude plugin install/enable` CLI.
   - What's unclear: the precise on-disk shape a *directory* install (not a marketplace install)
     must write to be enabled, on this exact version.
   - Recommendation: Implement clone+`enabledPlugins[name]=true`; verify (and adjust) at the
     dev-homelab smoke with `claude --debug` and `claude plugin list`. The master CLAUDE.md path is
     independent and must work regardless.

3. **Test harness: `bats-core` vs Python `subprocess`.**
   - What we know: both satisfy the locked decision; the repo's CI already runs `pytest`.
   - What's unclear: whether to add a second CI tool.
   - Recommendation: Default to a **Python `subprocess` harness in `pytest`** (zero new CI tooling,
     reuses the loopback-fake idiom from `tests/integration/conftest.py`). Use `bats-core` only if
     shell-native assertions are strongly preferred. (Claude's discretion.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `bash` 5.x | boot script | ✓ (target = Ubuntu 24.04 worker) | distro | — |
| `git` | clones | ✓ (baked in `provision-template.sh`) | distro | — |
| `curl` | bootconfig GET | ✓ (baked) | distro | — |
| `jq` | JSON parse + manifest gate | ✗ **(not in the bake list)** | — | **Add to `provision-template.sh` apt install** (no viable fallback — hand-rolled JSON parsing is a forbidden footgun) |
| `ttyd` | terminal | ✓ (baked, frozen invocation) | distro | — |
| `@anthropic-ai/claude-code` | the agent | ✓ (baked, pinned 2.1.170) | 2.1.170 | — |
| `jsonschema` (PyPI) | CI schema test | ✓ importable (4.26.0) | 4.26.0 | Add to `api/pyproject.toml` dev group |
| `bats-core` | boot harness (if chosen) | ✗ on dev host; ✓ via CI action | 1.x | Python `subprocess` harness in existing `pytest` |
| Real Proxmox | live boot acceptance | ✗ (by design) | — | **dev-homelab smoke gate** (CI cannot prove; the acceptance authority per REQUIREMENTS Definition of Done) |

**Missing dependencies with no fallback:**
- Real Proxmox boot — by design, this is the dev-homelab smoke, not CI. The CI surface is
  lint/unit/integration only.

**Missing dependencies with fallback:**
- `jq` — add to the template bake (the only correct action; no real fallback, just "add it").
- `bats-core` — Python `subprocess` harness is the fallback (and arguably the default).

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).
> This phase is **CI-lint/unit-testable only**; the real-boot acceptance is the dev-homelab smoke.

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | `pytest` 9.0.3 + `pytest-asyncio` 1.4.0 (already configured, `asyncio_mode=auto`) |
| Framework (boot script) | `bats-core` 1.x **OR** Python `subprocess` harness in `pytest` (Claude's discretion; default Python) |
| Schema validator | `jsonschema` 4.26.0 (add to `api/` dev group) |
| Config file | `api/pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths=["tests"]`) |
| Quick run command | `cd api && uv run pytest tests/integration/test_manifest_schema.py -x` |
| Boot-harness run | `cd api && uv run pytest tests/boot -x` (Python) **or** `bats cc-worker-config/.../test_burrow_boot.bats` |
| Full suite command | `cd api && uv run pytest` (+ the static gates: ruff/mypy/reuse) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WORK-05 | Committed `manifest.json` validates against `manifest.schema.json` | unit | `uv run pytest tests/integration/test_manifest_schema.py::test_committed_manifest_matches_schema -x` | ❌ Wave 0 |
| WORK-05 | Unknown plugin `type` is rejected by the schema | unit | `uv run pytest .../test_manifest_schema.py::test_unknown_type_is_rejected -x` | ❌ Wave 0 |
| WORK-05 | Boot installs only `claude-plugin` types; `binary`/`npm-global` skipped | integration (boot harness) | `uv run pytest tests/boot/test_burrow_boot.py::test_only_claude_plugins_installed -x` | ❌ Wave 0 |
| WORK-05 | Two boots of the same manifest produce an identical plugin tree (SC-2 idempotence) | integration (boot harness) | `...::test_two_boots_identical_plugin_tree -x` | ❌ Wave 0 |
| WORK-02 | Boot fetches bootconfig, then clones config + project (over loopback fake CP + fake git remotes) | integration (boot harness) | `...::test_fetch_then_clone_happy_path -x` | ❌ Wave 0 |
| WORK-02 | Bootconfig GET retries (~5×) then fails non-zero on a down control plane | integration (boot harness) | `...::test_bootconfig_retry_then_fail -x` | ❌ Wave 0 |
| WORK-02 | A bad manifest / unknown type fails the boot non-zero (fail-closed, ERR trap) | integration (boot harness) | `...::test_bad_manifest_fails_boot -x` | ❌ Wave 0 |
| WORK-02 (SC-3) | **Scrub-proof:** no token in `/etc/burrow/worker.env` post-boot; the sentinel token + repo URL appear in NO logged line | integration (boot harness) | `...::test_no_credential_leak -x` | ❌ Wave 0 |
| WORK-02 | `bash -n` parse + (CI) `shellcheck` clean on `burrow-boot.sh` | static | `bash -n cc-worker-config/lxc/worker-template/burrow-boot.sh` (+ `shellcheck` in CI) | ❌ Wave 0 |
| WORK-02 | The frozen ttyd line is unchanged (persistent, `--interface 0.0.0.0`, no `--once`) | static/assertion | a test that greps the script for `--once` (must be absent) and `--interface 0.0.0.0` (must be present) | ❌ Wave 0 |

### Hermetic Boot-Harness Strategy (the load-bearing design)

The boot script must be driven **without** real Proxmox, a real control plane, or a real git host:

1. **Fake control plane:** a loopback HTTP server (Python `http.server` in the harness, or a `bats`
   background `nc`/`python -m http.server` stub) that serves the standard envelope at
   `/api/v1/internal/bootconfig/<vmid>` with a **sentinel** `gitCredential`. A "down" variant
   (refuse connections / 503) drives the retry-then-fail test. This mirrors the existing
   `tests/integration/conftest.py` loopback-fake idiom (stub ttyd on an ephemeral port).
2. **Fake git remotes:** create bare repos on disk (`git init --bare`) for the config repo (with a
   `claude/CLAUDE.md`, `plugins/manifest.json`, a tag for ref-pinning) and the project repo. Point
   the manifest `source`/`ref` and the bootconfig `configRepo`/`projectRepo` at `file://` paths or a
   loopback `git daemon`. This makes clones real but hermetic and lets the idempotence test compare
   two cloned trees byte-for-byte.
3. **Override seams via env:** the script reads `CONTROL_PLANE` from the environment; the harness
   sets it to the loopback server. The ttyd `exec` is replaced in test by a stub `ttyd` on `PATH`
   (a script that records its argv and exits 0) so the boot completes without a real terminal — the
   same "fake binary on PATH" trick used for the stub ttyd elsewhere.
4. **Assert non-zero on failure paths** (`set -euo pipefail` + ERR trap): a bad manifest, an
   exhausted retry budget, and an unknown `type` must each yield a non-zero exit and a redacted log.
5. **Scrub-proof assertions:** after a successful run, grep the captured stdout/stderr and the
   written `/etc/burrow/worker.env` (in a temp HOME) for the sentinel credential and the repo URL —
   both must be absent. This is the worker-side analogue of the Plan 01-05 `_SENTINEL_CREDENTIAL`
   test (`test_bootconfig.py`), which already proves the *server* side never logs the credential.

### Sampling Rate
- **Per task commit:** `cd api && uv run pytest tests/integration/test_manifest_schema.py -x` (and
  the boot-harness subset touching the changed function).
- **Per wave merge:** `cd api && uv run pytest` (full) + `bash -n` + ruff/mypy/reuse static gates.
- **Phase gate:** full `pytest` green + the boot harness green + (CI) `shellcheck` clean, before
  `/gsd:verify-work`. The **real boot** is the dev-homelab smoke (human-verify, end-of-phase per
  config `human_verify_mode`).

### Wave 0 Gaps
- [ ] `cc-worker-config/plugins/manifest.schema.json` — the shared JSON-Schema
- [ ] `cc-worker-config/plugins/manifest.json` — the committed manifest (replaces the implicit one)
- [ ] `api/tests/integration/test_manifest_schema.py` — CI schema gate (covers WORK-05 drift)
- [ ] `api/tests/boot/` (or `tests/e2e/`) — the boot harness + loopback fake CP + fake git remotes
- [ ] `jsonschema` added to `api/pyproject.toml` dev group (`uv lock` refreshed — CI lockfile gate)
- [ ] `jq` added to `provision-template.sh` apt-install (bake) — needed by the live script
- [ ] (if `bats-core` chosen) `bats-core/bats-action@<sha>` added to `.github/workflows/ci.yml`
- [ ] (CI) a `shellcheck` step on `burrow-boot.sh` (the repo notes shellcheck was unavailable on the
      Windows dev host in Plan 00-06; CI is where it runs)

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: high`.
> This phase's security weight is **credential hygiene on the worker** (the endpoint's own threat
> model is already shipped + tested in Plan 01-05).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 is LAN-only, no auth (REQUIREMENTS Out of Scope; ADR-0007). |
| V3 Session Management | no | No sessions in the boot path. |
| V4 Access Control | partial | The bootconfig endpoint's vmid-in-pool gate + optional source-IP check are **already shipped** (Plan 01-05); the worker only consumes. |
| V5 Input Validation | yes | Manifest JSON-Schema validation (fail-closed); VMID is an int the endpoint already validates. |
| V6 Cryptography | no | No crypto is hand-rolled; the credential is opaque, minted server-side. |
| **V7 Secret/Log hygiene** | **yes (block_on=high)** | Token only in a subshell-local env → `GIT_ASKPASS`; never in URL, env file, or any log. Scrub-proof test (sentinel token absent from logs + `worker.env`). Mirrors the shipped `_safe()` + `test_bootconfig.py` no-leak gate. |

### Known Threat Patterns for {bash boot + git clone}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token in clone URL → `ps`/reflog/.git/config leak | Information Disclosure | `GIT_ASKPASS` in subshell; `credential.helper=` empty; never embed in URL (Pattern 1). |
| Token persisted to `/etc/burrow/worker.env` | Information Disclosure | Pull-at-boot never writes secrets to the env file (ADR-0002); scrub-proof test asserts absence. |
| Token echoed in an error/`boot.error` reason | Information Disclosure | Structural (token never on a command line) + ERR-trap redaction + CP-side `_safe()`; no `set -x`. |
| Malicious/typo'd manifest entry runs at boot | Tampering | Fail-closed JSON-Schema/jq gate; unknown `type` ⇒ non-zero exit (never skip-and-continue). |
| Cloning an unpinned (mutable) plugin ref | Tampering / Reproducibility | Pin `ref` to a tag/SHA; idempotent `rm -rf`+clone; CI can flag mutable refs. |
| `git clone` credential prompt hang (no TTY) | Denial of Service | `GIT_TERMINAL_PROMPT=0` → fail fast → fast `boot.error` (Pitfall 3). |
| SSRF via attacker-controlled `CONTROL_PLANE` | (low — operator-set env) | `CONTROL_PLANE` is operator config in `worker.env`, never client input; document it as trusted. |

## Sources

### Primary (HIGH confidence)
- `api/routers/internal.py`, `api/tests/integration/test_bootconfig.py`,
  `api/tests/integration/conftest.py`, `api/services/workspaceService.py` (`_safe()` + patterns),
  `cc-worker-config/lxc/worker-template/{burrow-boot.sh,provision-template.sh}`,
  `cc-worker-config/lxc/host-prime/lib/common.sh` (the `err_trap` idiom),
  `cc-worker-config/systemd/burrow-worker.service` — the live, shipped substrate this phase wires.
- `docs/adr/ADR-0002-boot-config-pull-at-boot.md` (frozen fetch contract);
  `docs/adr/ADR-0006/0007` (frozen ttyd posture); `docs/tech-spec.md` §11.1 (manifest), §988
  (cadence). `[VERIFIED: codebase]`
- `code.claude.com/docs/en/plugins-reference` — plugin dir (`~/.claude/plugins/`), `enabledPlugins`,
  `~/.claude/settings.json` scopes, `plugin.json` schema, `claude plugin install/enable` CLI.
  `[CITED]`
- `git-scm.com/docs/gitcredentials` + GitHub App installation-token clone convention
  (`x-access-token:<token>`). `[CITED]`
- `jsonschema` 4.26.0 verified on PyPI (`pip index versions jsonschema`) + importable. `[VERIFIED]`

### Secondary (MEDIUM confidence)
- `github.com/bats-core/bats-action` (the official setup action) + bats-core docs — the shell-test
  harness option. `[CITED]`
- `anthropics/claude-code#19522` — non-interactive `/plugin install` "closed as not planned"
  (motivates clone+enable over the CLI). `[CITED]`

### Tertiary (LOW confidence)
- Exact `enabledPlugins` on-disk shape for a *directory* install on `claude-code@2.1.170` — confirm
  at dev-homelab smoke (A1, Open Question 2). The credential username convention (`x-access-token`)
  depends on the operator's A3 minting mechanism (A2).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all worker tools are already baked; the only additions (`jq`, `jsonschema`)
  are verified and canonical.
- Architecture / boot flow: HIGH — the endpoint contract is frozen + shipped; the `err_trap` /
  loopback-fake / no-leak-test precedents already exist in-repo.
- Credential hygiene: HIGH on the mechanism (`GIT_ASKPASS`), MEDIUM on the username convention
  (depends on the pending A3 operator decision).
- Plugin install internals: MEDIUM — `enabledPlugins`/`~/.claude/plugins/` are documented, but the
  exact directory-install enablement shape on 2.1.170 is an [ASSUMED] to confirm at smoke.
- Pitfalls / validation: HIGH — derived from the shipped Plan 01-05 no-leak test + the repo's
  hermetic-fake idioms.

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 for the stable internal substrate; ~2026-06-25 for the Claude Code
plugin-install details (fast-moving CLI — re-verify the `enabledPlugins` shape against the installed
version at implementation time).
