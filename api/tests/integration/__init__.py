# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration test package (Phase 1).

Every later integration test imports through this package. Integration tests run
against a real migrated SQLite DB (and, later, a mocked Proxmox HTTP API + a stub
ttyd) — they are exempt from the seam-leakage guard, so a test may open its own
``aiosqlite`` connection to assert on schema artifacts directly.
"""
