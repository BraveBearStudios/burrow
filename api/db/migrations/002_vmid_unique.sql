-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/002_vmid_unique.sql
-- SC-3/SC-4 / WS-10: race-safe VMID reservation that survives destroy-then-recreate.
--
-- Partial unique index: a duplicate active (non-soft-deleted) vmid INSERT collides
-- (the reservation arbiter), while soft-deleted tombstones and not-yet-assigned NULL
-- vmids stay OUT of the index so a recycled vmid can be reused after destroy.
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_vmid_active
  ON workspaces(vmid)
  WHERE deletedAt IS NULL AND vmid IS NOT NULL;
