# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Service tier — the orchestration core.

Services depend ONLY on the provider ABCs (``DbProvider`` + ``ComputeProvider``)
and never on a concrete driver (``aiosqlite`` / ``proxmoxer``). The
seam-leakage guard (``tests/unit/test_seam_leakage.py``) enforces this.
"""
