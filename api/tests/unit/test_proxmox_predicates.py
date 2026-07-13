# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the ProxmoxProvider CT running/locked destroy-retry predicate (ROB-01).

``_is_running_or_locked`` gates ``destroyCt``'s retry: a destroy that failed because the CT
is still running or transiently locked must be retried, not surfaced as a hard failure that
leaks the VMID (CR-03). The predicate inspects the error MESSAGE defensively, so it must be
PRECISE. The bare ``"lock"`` substring it used to carry wrongly matched benign text that
merely contains those letters (``"unlock"``, ``"locked out"``, ``"clock"``). This test locks
the precise contract: only genuine running / locked / not-stopped errors match.
"""

import pytest

from compute.proxmoxProvider import _is_running_or_locked


@pytest.mark.parametrize(
    "message",
    [
        "failed to unlock the account",
        "user is locked out",
        "clock skew detected",
    ],
)
def test_benign_lock_lookalikes_do_not_match(message: str) -> None:
    """A string that merely CONTAINS "lock" (unlock / locked out / clock) is NOT a CT error."""
    assert _is_running_or_locked(Exception(message)) is False


@pytest.mark.parametrize(
    "message",
    [
        "CT 123 is locked (clone)",
        "container is running",
        "can't lock file '/var/...'",
        "CT is not stopped",
    ],
)
def test_real_running_or_locked_errors_match(message: str) -> None:
    """A genuine running / locked / not-stopped destroy error IS a retry-worthy CT state."""
    assert _is_running_or_locked(Exception(message)) is True
