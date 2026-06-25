-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/003_persistent_and_settings.sql
-- WSX-02 / ADR-0013 / ADR-0011: persistence data model + setup-state store.
--
-- (1) workspaces.persistent — opt-in Tier-1 durability (default ephemeral). The
--     non-NULL DEFAULT 0 is mandatory: SQLite rejects ADD COLUMN ... NOT NULL
--     without one on a non-empty table, and 0 is the backfill for existing v1.2
--     rows (they become explicitly ephemeral). Bool is stored as INTEGER 0/1;
--     Pydantic coerces it back to bool on read.
ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0;

-- (2) settings — a singleton config row (ADR-0011). CHECK (id = 1) enforces the
--     single-row invariant: a second INSERT with any id collides rather than
--     creating a divergent config. setupCompletedAt is an ISO-8601 timestamp
--     (NULL = unconfigured), consumed by the Phase 12 setup wizard. It is a
--     NON-sensitive timestamp only; no secret is stored here.
--
--     IF NOT EXISTS + INSERT OR IGNORE keep (2)/(3) re-runnable: executescript is
--     non-atomic (an implicit COMMIT precedes the script and the statements are NOT
--     wrapped in one transaction), so a mid-script failure after (1) commits would
--     re-run this file from the top without these guards (WR-03). The ALTER in (1)
--     is recovered separately in migrate() (it catches "duplicate column name").
CREATE TABLE IF NOT EXISTS settings (
  id               INTEGER PRIMARY KEY CHECK (id = 1),
  setupCompletedAt TEXT          -- ISO-8601 when setup finished; NULL = unconfigured
);
INSERT OR IGNORE INTO settings (id, setupCompletedAt) VALUES (1, NULL);
