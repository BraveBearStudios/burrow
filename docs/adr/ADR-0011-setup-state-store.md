<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0011: Setup-state store as a singleton settings table

## Status

Accepted

## Context

The v1.3 setup wizard (Phase 12 backend, Phase 13 UI) needs to record one piece of
durable, host-level state: whether first-run setup has completed, so the first-run
gate can decide whether to route the operator into the wizard or straight to the
app. This is control-plane state about the deployment, not about any one workspace,
so it does not belong on the `workspaces` row.

Phase 10 owns the data-model foundation that Phase 12 builds on, so the storage
shape is decided here even though the wizard logic lands later. Two shapes were
considered for "a small bag of host-level config":

- **A. Key/value table:** `settings(key TEXT PRIMARY KEY, value TEXT)`. Flexible
  for arbitrary future keys, but every read is a lookup-by-key with a nullable
  `value` and no column typing, and it invites schema-free sprawl (every new
  setting is a string blob with its own ad-hoc parsing). For a single deployment
  with a handful of known fields that is more machinery than the problem needs.
- **B. Singleton-column table (chosen):** `settings(id INTEGER PRIMARY KEY CHECK
  (id = 1), setupCompletedAt TEXT, ...)`. One typed column per setting, exactly one
  row enforced by `CHECK (id = 1)`. New settings are explicit migrations (a new
  column), which is the same discipline the rest of the schema already follows
  (RESEARCH A1).

The `setupCompletedAt` value is an ISO-8601 timestamp (NULL = unconfigured). It is
a **non-sensitive** marker only: the Proxmox API token is validated in memory and
lives in `.env` exclusively (CLAUDE.md security posture, milestone decision), so no
secret is stored in `settings` and no token-at-rest ADR is needed.

## Decision

Store host-level setup state in a **singleton `settings` table** added by migration
`003_persistent_and_settings.sql` through the existing `schema_migrations` ledger.

- **Shape:** `settings(id INTEGER PRIMARY KEY CHECK (id = 1), setupCompletedAt TEXT)`.
  The `CHECK (id = 1)` plus a single seeded row (`INSERT ... VALUES (1, NULL)`)
  enforces the singleton invariant: a second insert with any id collides, so the
  config can never silently fork into two divergent rows.
- **`setupCompletedAt`** is an ISO-8601 timestamp; `NULL` means setup has not
  completed. It is the first-run gate's authority and carries no secret.
- **Behind the DbProvider seam.** The `settings` row is read and written only
  through `DbProvider` (the SQLite path here, a Postgres path later), so the hosted
  path stays additive. Phase 12 adds the `DbProvider` methods that read and stamp
  `setupCompletedAt`; this ADR fixes only the table shape and the singleton rule.
- **New settings are columns, not keys.** Any future host-level setting is a new
  typed column added by a later migration, not an untyped key/value row.

## Consequences

- The setup-state store is one typed row reached by `WHERE id = 1`, with the
  single-row guarantee enforced in the schema rather than in application code.
- Adding a host-level setting later costs a migration (a new column) rather than a
  free-form key, which keeps the store typed and self-documenting at the cost of a
  schema change per setting. For a deployment with a small, known field set that is
  the intended trade.
- No secret enters the database: the token stays `.env`-only, so the store needs no
  encryption-at-rest and introduces no new sensitive surface.
- Phase 12 consumes this table for the wizard backend and the first-run gate; the
  table shape is frozen here so Phase 12 can assume it.

## Revisit trigger

A genuine need for arbitrary, operator-defined, frequently-changing settings (where
each new key would otherwise force a migration), or a hosted multi-tenant path where
setup state is per-tenant rather than per-deployment and the singleton row no longer
models the domain.
