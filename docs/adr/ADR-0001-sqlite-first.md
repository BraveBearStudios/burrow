<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0001: SQLite-first persistence behind `DbProvider`

## Status

Accepted

## Context

Burrow v1 targets a single-user, LAN-only self-host deployment (one operator, one
control-plane host). The persisted state is small and low-contention: workspace rows,
an append-only event log, and template metadata. Introducing an external database
service (Postgres + a connection pool + a separate process to operate, back up, and
patch) would add operational weight that a single-user self-host does not warrant,
and would make the "clone the repo and run it" story heavier than it needs to be.

A hosted, multi-tenant path is a deliberate future direction, not a v1 concern. The
architecture keeps that path open through the `DbProvider` seam rather than by adopting
its database now (CLAUDE.md: "a hosted path must be additive, never a rewrite").

This ADR records the choice that tech-spec Appendix A names; the file makes it a
first-class, revisitable decision under `docs/adr/`.

## Decision

Use **SQLite** via `aiosqlite` as the v1 persistence store, accessed **only** through
the abstract `DbProvider` interface (`api/db/provider.py`). The SQLite implementation
(`api/db/sqliteProvider.py`) is the one wired in v1; a `PostgresProvider`
(`api/db/postgresProvider.py`) exists as a stub behind the same interface so the
hosted path is additive.

- No `aiosqlite` types, connection objects, or raw SQL leak past the seam. Services,
  routers, and models depend on the `DbProvider` ABC and on Pydantic models, never on
  the SQLite driver (enforced by the seam-leakage check).
- The control plane selects the implementation once, by env (`BURROW_DB=sqlite`), in
  the app factory. Swapping to Postgres is an env/wiring change, not a service edit.
- SQLite runs in WAL mode on the control-plane host's disk; the database directory
  (e.g. a dedicated `/data`) is the backup target and survives an app redeploy.

## Consequences

- State lives on the single control-plane host's local disk. There is no replication
  and no high-availability story in v1. This is acceptable for single-user self-host
  and unacceptable for a multi-tenant deployment.
- The `DbProvider` ABC must stay free of SQLite-specific assumptions (e.g. no leaking
  of SQLite's type affinity or its concurrency model) so the Postgres implementation
  is a genuine drop-in. The cost is the discipline of returning Pydantic models, not
  driver rows, from every method.
- Concurrency is bounded by SQLite's single-writer model. For one operator this is a
  non-issue; a second concurrent writer (the hosted path) is exactly the revisit
  trigger.
- Backups are a file/directory copy of the WAL-mode database, which is operationally
  simple but is the operator's responsibility.

## Revisit trigger

A hosted / multi-tenant deployment path, a second concurrent operator/user
requirement, or a need for replication or high availability. Any of these flips the
selection behind the `DbProvider` seam to the Postgres implementation.
