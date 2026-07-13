-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/004_credentials_and_audit.sql
-- ADR-0015: GUI-managed encrypted credential store + audit log.
--
-- (1) settings credential columns. Fernet ciphertext for the Proxmox API token and
--     the GitHub PAT, the argon2id hash for the local credential-surface admin gate,
--     and NON-secret metadata (last4 + updatedAt) for the status-only read. All
--     nullable: an unconfigured deployment has no stored credentials and no admin
--     secret yet. The ciphertext is a BLOB (Fernet token bytes); the last4 and the
--     hash are TEXT. NO plaintext secret is ever stored here -- encryption at rest is
--     the whole point, and the extended setup-token-leak test locks that plaintext
--     appears in no cell while permitting exactly these encrypted cells.
--
--     Each ADD COLUMN is its own statement. migrate()'s duplicate-column recovery
--     is for the realistic re-run (the whole script applied but the schema_migrations
--     ledger row was not yet written): the re-run dup's on the first ALTER, recovery
--     strips the already-applied ALTER lines and replays the idempotent remainder
--     (the CREATE TABLE IF NOT EXISTS below), then the caller ledgers the version
--     (WR-03). All columns are nullable metadata-only ADDs, so a partial-sequence
--     failure is not a realistic mode (same accepted risk as 003's single ALTER).
ALTER TABLE settings ADD COLUMN proxmoxTokenEnc BLOB;
ALTER TABLE settings ADD COLUMN proxmoxTokenLast4 TEXT;
ALTER TABLE settings ADD COLUMN gitTokenEnc BLOB;
ALTER TABLE settings ADD COLUMN gitTokenLast4 TEXT;
ALTER TABLE settings ADD COLUMN adminSecretHash TEXT;
ALTER TABLE settings ADD COLUMN credentialsUpdatedAt TEXT;

-- (2) audit_log -- append-only SOC 2 audit trail (CC7.2/CC7.3) for credential
--     lifecycle and admin-gate decisions. It is NEVER soft-deleted and NEVER stores a
--     secret value: action + which credential + outcome + source IP + non-secret
--     detail (e.g. a last4) + timestamp only. createdAt reuses the same
--     strftime('%Y-%m-%dT%H:%M:%fZ', 'now') shape every other timestamp column writes
--     (no new format). IF NOT EXISTS keeps this re-runnable (executescript is
--     non-atomic, WR-03).
CREATE TABLE IF NOT EXISTS audit_log (
  id        TEXT PRIMARY KEY,
  action    TEXT NOT NULL,   -- e.g. credentials.update, admin.verify
  target    TEXT,            -- which credential / subject; never a secret value
  outcome   TEXT NOT NULL,   -- success | failure
  sourceIp  TEXT,            -- caller IP; NULL when unavailable
  detail    TEXT,            -- non-secret context (e.g. a last4); never a value
  createdAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
