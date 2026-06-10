# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Server-side workspace state machine (WS-09, SC-12).

A single explicit ``{(from_state, action) -> to_state}`` table is the policy
authority for which lifecycle mutations are legal. ``WorkspaceService`` calls
:func:`assert_transition` BEFORE every stop/start/destroy mutation so an illegal
request is rejected at the boundary with a typed :class:`IllegalTransitionError`
(the router maps it to a 409 envelope) instead of reaching a provider.

Design pins (RESEARCH Pattern 4 / Assumption A4):

- ``creating`` is *internal-only*: it is reached by the create saga, never as an
  action target, so it never appears on the left of a legal pair. A stop/start on
  a still-booting workspace is therefore illegal.
- ``error`` is a *defined* state whose ONLY legal exit is ``destroy`` (no in-place
  retry in v1) — pinned so the UI gates correctly.
- ``destroyed`` is terminal: every action from it (including ``destroy`` again —
  the double-destroy guard) is illegal.
"""

from lib.errors import IllegalTransitionError

# Legal lifecycle transitions. Any (state, action) absent here is illegal.
TRANSITIONS: dict[tuple[str, str], str] = {
    ("running", "stop"): "stopped",
    ("stopped", "start"): "running",
    ("running", "destroy"): "destroyed",
    ("stopped", "destroy"): "destroyed",
    ("error", "destroy"): "destroyed",  # error's only legal exit (A4)
}


def assert_transition(state: str, action: str) -> str:
    """Return the resulting state for a legal ``(state, action)``; raise otherwise.

    Raises :class:`IllegalTransitionError` (carrying the offending pair and the
    stable ``illegal_transition`` code) when the pair is not in :data:`TRANSITIONS`.
    """
    to_state = TRANSITIONS.get((state, action))
    if to_state is None:
        raise IllegalTransitionError(state, action)
    return to_state
