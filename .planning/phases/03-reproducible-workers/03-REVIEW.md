<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 03-reproducible-workers
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - cc-worker-config/lxc/worker-template/burrow-boot.sh
  - cc-worker-config/lxc/worker-template/provision-template.sh
  - cc-worker-config/plugins/manifest.json
  - cc-worker-config/plugins/manifest.schema.json
  - api/tests/boot/__init__.py
  - api/tests/boot/conftest.py
  - api/tests/boot/test_burrow_boot.py
  - api/tests/boot/stub_ttyd_bin
  - api/tests/integration/test_manifest_schema.py
  - api/pyproject.toml
  - .github/workflows/ci.yml
  - REUSE.toml
  - docs/adr/ADR-0009-plugin-cadence-boot-time-latest.md
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-11
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 3 ships the worker pull-at-boot orchestration (`burrow-boot.sh`), the golden-template provisioner, the plugin manifest + JSON-Schema, a hermetic boot-harness test tier, and the CI/REUSE wiring. The credential-hygiene design is structurally sound: the short-lived git token is fed to `git clone` via an in-memory `GIT_ASKPASS` helper inside a subshell, never embedded in a clone URL, never written to `worker.env`, and unset after the clones. `$BASH_COMMAND` never contains the expanded token, so the structural guarantee holds and the `test_no_credential_leak` scrub-proof test confirms it. The FROZEN ttyd tail is intact (`--interface 0.0.0.0` present, `--once` absent), `set -x` is absent on the boot path, and the manifest fail-closed gate rejects an unknown `type`. SPDX/REUSE coverage is complete (inline headers on comment-capable files; the two JSON files covered by `REUSE.toml`).

No BLOCKER-tier issues found. However, several defects degrade robustness and contradict the script's own documented guarantees:

- The ERR-trap secret-redaction backstop matches only the legacy `ghp_` token prefix and is both over-greedy and ineffective for the actual credential formats this design uses (`x-access-token` / `ghs_` / `github_pat_`).
- The boot-time jq gate does **not** enforce the same constraints as the JSON-Schema it claims to mirror (no `schemaVersion` check, no `additionalProperties` rejection, no `minLength`), so CI and boot can diverge.
- The `install_claude_plugin` clone runs unauthenticated and without `GIT_TERMINAL_PROMPT=0`; the test env masks this by setting the variable globally.
- The manifest-iteration `while`-loop reads from a process substitution, so a `jq` failure during iteration is not caught by `pipefail`.

## Warnings

### WR-01: ERR-trap redaction matches the wrong token prefix and is over-greedy

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:44`
**Issue:** The redaction backstop is `local cmd="${BASH_COMMAND//ghp_*/[redacted]}"`. Two problems:
1. **Wrong/incomplete prefix.** The design mints an `x-access-token`-style credential — a GitHub App installation token (`ghs_…`) or fine-grained PAT (`github_pat_…`), per the script's own comment at lines 100-101. None of those start with `ghp_` (the legacy classic-PAT prefix). The test sentinel is `SENTINEL-bootcred-…`. So if a token ever did reach `$BASH_COMMAND`, this pattern would not redact it.
2. **Over-greedy glob.** In `${var//ghp_*/…}`, `*` is a greedy glob, so a match starting at `ghp_` consumes the rest of the string in one replacement — it does not stop at a token boundary.

The redaction is correctly labeled defense-in-depth and the real guarantee is structural (the token only ever lives in a subshell-local env var and never appears in `$BASH_COMMAND`), so this is not a live leak. But a "backstop" that cannot match the credential format it guards is false assurance: a future refactor that moved the token onto a command line would silently bypass it.
**Fix:** Either drop the redaction entirely (rely on the documented structural guarantee) or make it match the formats actually in use and bound the glob, e.g. redact word-shaped secrets generically:
```bash
local cmd="${BASH_COMMAND}"
cmd="${cmd//${GIT_CRED:-__never__}/[redacted]}"   # redact the live value if set
```
Redacting the live `$GIT_CRED` value (when in scope) is exact and format-agnostic; the static `ghp_*` glob is neither.

### WR-02: Boot-time jq gate does not mirror the JSON-Schema it claims to enforce

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:175-181`
**Issue:** The function comment (lines 159-165) states the jq gate "MUST enforce the SAME required-keys + type enum as `manifest.schema.json` (the single source of truth) so CI and boot never diverge." It does not:
- The schema requires top-level `schemaVersion` (`manifest.schema.json:5`); the jq gate never checks it.
- The schema sets `additionalProperties: false` on each plugin entry and at top level (`manifest.schema.json:19,23`), rejecting unknown keys; the jq gate ignores extra keys.
- The schema enforces `minLength: 1` on `source`/`ref` (`manifest.schema.json:14-15`); the jq gate only checks `type == "string"`, so an empty-string `source` or `ref` passes the boot gate and would be handed to `git clone`.

A manifest that passes CI but adds a stray key, or one with an empty `ref`, behaves differently at boot than the schema implies. The type-enum (the security-critical fail-closed check) does match, which is why this is a Warning and not a Blocker.
**Fix:** Bring the jq gate to parity with the schema (or, better, validate against the schema itself at boot if a validator is available in the image). Minimal jq tightening:
```bash
jq -e '
  has("schemaVersion") and (.schemaVersion | type == "string")
  and (.plugins | to_entries | all(.value
        | (.source | type == "string" and (. | length) > 0)
        and (.ref    | type == "string" and (. | length) > 0)
        and (.type   | IN("claude-plugin","binary","npm-global"))))
' "$manifest" >/dev/null || { log "manifest failed structural validation"; return 1; }
```

### WR-03: claude-plugin clone is unauthenticated and lacks `GIT_TERMINAL_PROMPT=0`; tests mask it

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:148`
**Issue:** `install_claude_plugin` runs a bare `git clone --depth=1 --branch "$ref" "$url" "$dest"` with no credential helper and, critically, without the `GIT_TERMINAL_PROMPT=0` guard that `clone_with_token` uses (lines 116-120). If a `claude-plugin` source ever requires auth (a private repo, or a transient 401/redirect-to-login), git's behavior depends on the inherited environment. The hermetic harness sets `GIT_TERMINAL_PROMPT=0` globally in `make_boot_env` (`api/tests/boot/conftest.py:405`), so the tests never exercise the real production environment, where that variable is unset. Under systemd with no controlling TTY git will fail fast rather than hang, but the test/production divergence means the "fails fast, no hang" property is asserted only under conditions that don't match the deployed boot.
**Fix:** Apply the same hardening as the credentialled clone path:
```bash
GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
  clone --depth=1 --branch "$ref" "$url" "$dest"
```
This makes the plugin clone fail-fast independent of the ambient environment and removes reliance on the test harness setting the variable.

### WR-04: Manifest-iteration loop reads a process substitution, so a jq failure there is not caught by `pipefail`

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:186-191`
**Issue:** The install loop is `while IFS=… read -r … ; do … ; done < <(jq -r … "$manifest")`. With process substitution (`< <(…)`), the `jq` exit status is **not** part of any pipeline, so `set -o pipefail` does not propagate it. If `jq` failed mid-stream (e.g. a manifest that parsed for the gate but produced a runtime error during the `to_entries[]` extraction), the `while` loop would simply see EOF and exit 0, silently installing a partial/empty plugin set instead of failing the boot. The upstream `jq -e` gate (lines 175-181) makes this unlikely in practice, which is why it is a Warning, but the fail-closed contract for manifest processing is not actually enforced on the iteration leg.
**Fix:** Capture the tsv into a variable first so the `jq` exit status is visible to `set -e`, then iterate it:
```bash
local rows
rows="$(jq -r '.plugins | to_entries[]
        | select(.value.type == "claude-plugin")
        | [.key, .value.source, .value.ref] | @tsv' "$manifest")"
while IFS=$'\t\r' read -r name source ref; do
  [[ -n "$name" ]] || continue
  install_claude_plugin "$name" "$source" "$ref"
done <<<"$rows"
```

### WR-05: `projectRepo`/branch fields are consumed without validation; a null/empty value mis-routes the boot

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:206,231,246-248`
**Issue:** `PROJECT_REPO="$(jq -r '.projectRepo' <<<"$BOOTCONFIG")"` uses `jq -r`, which emits the literal string `null` when the field is absent/null. The `START_DIR` guard at line 246 (`[[ -n "$PROJECT_REPO" ]]`) then treats `"null"` as a real repo and sets `START_DIR=$PROJECT_DIR`, while the clone at line 231 attempts `git clone … null …`, which fails and ERR-traps the boot. The same `jq -r` "null" footgun applies to `configRepo`/`configBranch`/`projectBranch`/`gitCredential`: a malformed bootconfig that the gate does not catch yields stringly-typed `"null"` values fed into `git`/`cp` rather than a clear "missing field" failure. None of these are validated after extraction.
**Fix:** Validate the required bootconfig fields immediately after extraction, failing closed with a clear message and treating jq's `null` as missing:
```bash
for var in CONFIG_REPO CONFIG_BRANCH PROJECT_REPO PROJECT_BRANCH GIT_CRED; do
  val="${!var}"
  [[ -n "$val" && "$val" != "null" ]] || { log "bootconfig missing required field for ${var}"; exit 1; }
done
```
Use `jq -e` per field, or a single object-shape `jq -e` gate on `$BOOTCONFIG`, so a bad envelope fails before any `git`/`cp` runs.

## Info

### IN-01: `/tmp/cc-worker-config` is a fixed, predictable path with `rm -rf` before clone

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:217-218`
**Issue:** The config repo is cloned to the hardcoded `/tmp/cc-worker-config` after `rm -rf` of the same path. In the v1 single-tenant worker LXC this is safe (one workspace per container, no untrusted local users), but a fixed world-readable `/tmp` path with a pre-clone `rm -rf` is a symlink/TOCTOU-shaped pattern that becomes a real concern if the worker ever shares a host user namespace.
**Fix:** Clone into a `mktemp -d` directory (or under `${WORKER_HOME}`) instead of a fixed `/tmp` path, and remove the explicit `rm -rf` of a predictable location.

### IN-02: `stub_ttyd_bin` is a bash script but is not covered by the shellcheck gate

**File:** `.github/workflows/ci.yml:86-87`
**Issue:** The shellcheck step lints only `burrow-boot.sh` and `provision-template.sh`. `api/tests/boot/stub_ttyd_bin` is a `#!/usr/bin/env bash` script with `set -euo pipefail`; a regression in the stub (which gates whether the boot-harness tests are meaningful) would not be caught by lint.
**Fix:** Add `api/tests/boot/stub_ttyd_bin` to the shellcheck invocation, or glob the worker/test shell scripts.

### IN-03: `process_manifest` accepts an empty `.plugins` object silently

**File:** `cc-worker-config/lxc/worker-template/burrow-boot.sh:175-191`
**Issue:** jq's `all(...)` over an empty array returns `true`, so a manifest with `"plugins": {}` passes the gate and installs nothing. This is reasonable behavior, but it is undocumented and untested — there is no test asserting an empty plugin set is a valid no-op vs. a misconfiguration. If "a manifest must declare at least one plugin" is ever a requirement, this path silently violates it.
**Fix:** Either document the empty-manifest no-op explicitly, or add an assertion if a non-empty plugin set is required. No code change needed if the no-op is intended.

### IN-04: Worker.env placeholder created at provision time but never sourced by the boot script

**File:** `cc-worker-config/lxc/worker-template/provision-template.sh:73-74` / `cc-worker-config/lxc/worker-template/burrow-boot.sh:55,198`
**Issue:** `provision-template.sh` creates `/etc/burrow/worker.env` as a placeholder "populated at boot," and the boot script reads `CONTROL_PLANE` via `: "${CONTROL_PLANE:?…}"` (line 198) — i.e. from the process environment, not by sourcing `worker.env`. The systemd unit (`burrow-worker.service`, not in this review set) presumably injects `CONTROL_PLANE`, but the relationship between the `worker.env` file and where `CONTROL_PLANE` actually comes from is not visible in the reviewed files. The boot-harness test injects `CONTROL_PLANE` directly via env (`conftest.py:400`), so the `worker.env` → environment wiring is untested here.
**Fix:** Confirm `burrow-worker.service` sources `worker.env` (`EnvironmentFile=`) and document the `worker.env` → `CONTROL_PLANE` path, or have the boot script source it explicitly. Track against the dev-homelab smoke if the unit is out of this phase's scope.

---

_Reviewed: 2026-06-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
