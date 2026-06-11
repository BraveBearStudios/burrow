<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0009: Plugin cadence is boot-time-latest, reproducibility via manifest ref-pinning

## Status

Accepted

## Context

A booted worker assembles its plugin set fresh from `cc-worker-config` so workspaces
are reproducible and plugin drift is impossible (WORK-02, SC-2). Two questions had to
be settled before `burrow-boot.sh` could pull plugins:

1. **When does a worker pick up a plugin-set change?** (the *cadence*)
2. **What guarantees that two boots produce the *same* plugin tree?** (*reproducibility*)

The tech-spec (§988) recommends the worker pull the `cc-worker-config` branch HEAD on
each boot. That makes the cadence **boot-time-latest**: a change merged to the config
branch is live on the next boot of any worker, with no per-workspace pin to bump.

Plugins are not homogeneous. The manifest (`cc-worker-config/plugins/manifest.json`,
ADR/§11.1) tags each entry with a `type`, and the type drives *where* it is materialized:

- **`binary`** and **`npm-global`** types are **baked into the golden template** at
  provision time (`provision-template.sh`). They do not change at boot; a new version
  ships only when the template is rebuilt.
- **`claude-plugin`** types are **pulled fresh at boot** — these are the only entries the
  boot-time-latest cadence applies to.

That left the reproducibility question. Two ways to make repeated boots identical were
considered:

- **A. Snapshot-at-create** — at workspace-create time the control plane snapshots the
  config repo (a commit SHA) and pins the workspace to it, so every boot of *that*
  workspace replays the exact same tree. Strong per-workspace reproducibility, but it
  introduces per-workspace config state the control plane must persist, version, and
  garbage-collect, and it couples the create saga to config-repo internals — none of
  which v1 needs while the manifest is still churning.
- **B. Manifest ref-pinning (chosen)** — the cadence stays boot-time-latest (always pull
  HEAD), and reproducibility comes from the **manifest itself pinning each `claude-plugin`
  entry to an immutable ref** (a git tag or commit SHA). Two boots that resolve the *same*
  manifest clone the *same* pinned refs and therefore produce a byte-identical plugin
  tree. No per-workspace snapshot state is required; the manifest is the single,
  version-controlled source of truth.

This is the B4 decision from the Phase-3 context. Recording it as an ADR makes the
reproducibility semantics explicit (SC-4) so a future reader does not mistake
boot-time-latest for "non-reproducible".

## Decision

Adopt **boot-time-latest cadence with manifest ref-pinning for reproducibility
(Option B).**

- **Cadence = boot-time-latest.** `burrow-boot.sh` pulls the `cc-worker-config` branch
  HEAD on every boot (tech-spec §988). A merged config change is live on the next boot;
  there is no per-workspace plugin pin to bump.
- **Reproducibility = manifest ref-pinning, not config-repo snapshotting.** Each
  `claude-plugin` entry in `manifest.json` pins an **immutable ref** (a git tag or commit
  SHA). The boot install (`install_claude_plugin`) does `rm -rf` the destination then
  `git clone --depth=1 --branch <ref>`, so two boots of the same manifest produce an
  identical plugin tree (SC-2). The config repo is **not** snapshotted per workspace.
- **Plugin-type split is load-bearing.** `binary` / `npm-global` are baked at provision
  time and skipped at boot; only `claude-plugin` types are pulled fresh. The boot-time-latest
  cadence applies solely to `claude-plugin` entries.

Scope of this ADR: the **cadence and reproducibility model** are frozen here. The boot-time
implementation (`process_manifest` + `install_claude_plugin`) and the manifest schema land
in Plans 03-01/03-02; the CI gates that catch manifest drift land in Plan 03-03.

## Consequences

- **Two boots of the same manifest → identical plugin tree (SC-2).** Reproducibility is a
  property of the *manifest*, not of any persisted per-workspace snapshot. A workspace that
  is destroyed and recreated against the same manifest gets the same plugins.
- **A `ref: "main"` (or any mutable branch) on a `claude-plugin` is intentionally
  non-reproducible "latest"** (Pitfall 1). Boot-time-latest cadence means a mutable ref
  resolves to whatever HEAD is at boot, so "two boots are identical" only holds for an
  immutable tag/SHA. The committed manifest and its schema/CI gate exist to keep
  `claude-plugin` refs immutable; the operator owns the discipline of pinning tags.
- **No per-workspace config state.** The control plane persists boot *intent* (ADR-0002),
  not a config-repo snapshot, so there is nothing extra to version or garbage-collect. The
  manifest stays the single, version-controlled source of truth for the plugin set.
- **Config changes are repo-driven and global.** A plugin change ships by editing the
  manifest in `cc-worker-config` and merging; the next boot of every worker picks it up.
  This keeps the change surface in one reviewed, version-controlled place at the cost of
  per-workspace divergence — which is exactly the v1 goal (no drift).
- **Snapshot-at-create (Option A) is reserved as a documented fallback** if a future
  requirement needs a single workspace pinned to a config-repo state independent of the
  manifest (see Revisit trigger).

## Revisit trigger

A requirement for **per-workspace plugin version pinning / snapshot-at-create** — e.g. a
workspace that must replay an exact config-repo state independent of the live manifest, or
the need to roll a single workspace back to an older plugin set without touching the shared
manifest. Deferred until the manifest stabilizes (Phase-3 context, Deferred Ideas); revisit
when that stability makes per-workspace pinning worth the per-workspace config state it adds.
