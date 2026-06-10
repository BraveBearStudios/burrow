# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""HTTP routers for the ``/api/v1`` surface (Plan 04).

Each router is THIN (RESEARCH Architectural Responsibility Map): it parses and
validates the request (Pydantic), calls :class:`services.workspaceService.WorkspaceService`
via the ``get_service`` DI seam, and wraps the result in the standard envelope
(:func:`lib.envelope.respond`) with ``model_dump(by_alias=True)`` so JSON stays
camelCase (PLAT-09). Routers touch no provider impl, no ``aiosqlite``/``proxmoxer``,
and no SQL — the seam-leakage guard enforces this. Service-tier typed errors are
mapped to envelope error codes + HTTP statuses by the handler registered in
``main.py``.
"""
