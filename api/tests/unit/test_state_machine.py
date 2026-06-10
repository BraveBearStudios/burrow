# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""State-machine transition guard tests (WS-09).

The server-side transition table is the policy authority for which lifecycle
mutations are legal. These tests pin the five legal transitions and the four
illegal ones called out in CONTEXT/VALIDATION (stop-on-creating,
start-on-destroyed, double-destroy, running->start). Service-level enforcement
(stop/start/destroy raising at the service boundary) is added in Task 3.
"""

import pytest

from lib.errors import IllegalTransitionError
from lib.statemachine import TRANSITIONS, assert_transition


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        ("running", "stop", "stopped"),
        ("stopped", "start", "running"),
        ("running", "destroy", "destroyed"),
        ("stopped", "destroy", "destroyed"),
        ("error", "destroy", "destroyed"),  # error's only legal exit (A4)
    ],
)
def test_legal_transitions_resolve(state: str, action: str, expected: str) -> None:
    assert assert_transition(state, action) == expected


@pytest.mark.parametrize(
    ("state", "action"),
    [
        ("creating", "stop"),  # WS-09: stop while still booting
        ("destroyed", "start"),  # WS-09: start a destroyed workspace
        ("destroyed", "destroy"),  # WS-09: double-destroy
        ("running", "start"),  # already running
        ("creating", "start"),  # creating is internal-only, never an action target
        ("error", "start"),  # error's only exit is destroy, not retry
        ("error", "stop"),  # ditto
    ],
)
def test_illegal_transitions_raise(state: str, action: str) -> None:
    with pytest.raises(IllegalTransitionError) as exc_info:
        assert_transition(state, action)
    # The raised error carries the offending pair and a stable envelope code.
    assert exc_info.value.code == "illegal_transition"
    assert state in str(exc_info.value)
    assert action in str(exc_info.value)


def test_transitions_table_is_exactly_the_five_legal_pairs() -> None:
    """`creating` is internal-only and `error` exits only via destroy (A4)."""
    assert set(TRANSITIONS) == {
        ("running", "stop"),
        ("stopped", "start"),
        ("running", "destroy"),
        ("stopped", "destroy"),
        ("error", "destroy"),
    }
