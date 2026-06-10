-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/001_init.sql

CREATE TABLE workspaces (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name          TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'creating',
  -- status values: creating | running | stopped | error | destroyed
  vmid          INTEGER,
  node          TEXT NOT NULL DEFAULT 'node1',
  lxcIp         TEXT,
  projectRepo   TEXT NOT NULL,
  projectBranch TEXT NOT NULL DEFAULT 'main',
  pluginSet     TEXT NOT NULL DEFAULT 'default',
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  stoppedAt     TEXT,
  destroyedAt   TEXT,
  deletedAt     TEXT    -- soft delete
);

CREATE TABLE events (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  workspaceId   TEXT NOT NULL REFERENCES workspaces(id),
  type          TEXT NOT NULL,
  -- type values: workspace.created|started|stopped|destroyed|terminal.connected|terminal.disconnected|boot.error
  data          TEXT DEFAULT '{}',  -- JSON blob
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE templates (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name          TEXT NOT NULL UNIQUE,  -- 'default'
  proxmoxTid    INTEGER NOT NULL,      -- Template VMID (9000)
  pluginManifest TEXT DEFAULT '{}',   -- JSON: plugin set definition
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed default template
INSERT INTO templates (name, proxmoxTid) VALUES ('default', 9000);

CREATE INDEX idx_workspaces_status   ON workspaces(status);
CREATE INDEX idx_events_workspaceId  ON events(workspaceId);
