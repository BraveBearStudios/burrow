# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Boot harness: drive burrow-boot.sh against a hermetic substrate (WORK-02, SC-3).

The worker-side analogue of ``tests/integration/test_bootconfig.py``. Runs the live
``burrow-boot.sh`` as a subprocess over a loopback fake control plane + ``file://``
bare git remotes + a stub ``ttyd`` on ``PATH`` (fixtures in ``conftest.py``) and
proves:

- ``test_fetch_then_clone_happy_path`` — fake CP up → boot exits 0, the project repo
  is cloned to ``~/project``, ``CLAUDE.md`` is copied to ``~/CLAUDE.md``, and the stub
  ttyd was invoked with the FROZEN ``--interface 0.0.0.0`` and NO ``--once``.
- ``test_bootconfig_retry_then_fail`` — a down control plane → ~5 bounded retries
  (log-line count) then a non-zero boot (ERR-trapped), never an infinite hang.
- ``test_no_credential_leak`` — after a green boot the sentinel credential and the
  project repo URL appear in NO captured stdout/stderr line and NOT in worker.env
  (scrub-proof, T-03-01..03, block_on=high).
- ``test_frozen_ttyd_line`` — a static grep of the script: ``--once`` absent,
  ``--interface 0.0.0.0`` present (ADR-0006/0007 frozen tail).

Real worker boot stays the dev-homelab smoke (human-verify), NOT a CI command.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.boot.conftest import (
    SENTINEL_CREDENTIAL,
    FakeControlPlane,
    make_boot_env,
)


def _run_boot(
    boot_script: Path,
    *,
    control_plane: str,
    tmp_path: Path,
    stub_bin: Path,
    timeout: float = 60.0,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run burrow-boot.sh under a temp HOME + temp /etc/burrow; return proc + the paths."""
    home = tmp_path / "home"
    home.mkdir()
    etc_burrow = tmp_path / "etc-burrow"
    etc_burrow.mkdir()
    # The provision step touches a non-secret worker.env placeholder; mirror that so
    # the no-leak test can assert the credential never lands in it.
    (etc_burrow / "worker.env").write_text(f"CONTROL_PLANE={control_plane}\n")
    env = make_boot_env(
        control_plane=control_plane, home=home, etc_burrow=etc_burrow, stub_bin=stub_bin
    )
    proc = subprocess.run(
        ["bash", str(boot_script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc, home, etc_burrow


def test_fetch_then_clone_happy_path(
    boot_script: Path,
    fake_control_plane: FakeControlPlane,
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """Fake CP up + file:// bare repos → boot exits 0, clones, copies CLAUDE.md, execs ttyd."""
    proc, home, _etc = _run_boot(
        boot_script,
        control_plane=fake_control_plane.url,
        tmp_path=tmp_path,
        stub_bin=stub_ttyd_path,
    )
    assert proc.returncode == 0, f"boot failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # The project repo was cloned to ~/project and the seeded README came down.
    assert (home / "project" / "README.md").is_file(), "project repo not cloned to ~/project"
    # The master CLAUDE.md was copied from the config repo to ~/CLAUDE.md.
    assert (home / "CLAUDE.md").is_file(), "CLAUDE.md not copied to ~"

    # The stub ttyd recorded the FROZEN argv (persistent + LAN-bound).
    argv = (home / "ttyd-argv.txt").read_text()
    assert "--interface 0.0.0.0" in argv.replace("\n", " "), f"ttyd argv: {argv!r}"
    assert "--once" not in argv, f"ttyd must be persistent (no --once): {argv!r}"


def test_bootconfig_retry_then_fail(
    boot_script: Path,
    down_control_plane: str,
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """A down control plane → bounded retries (~5) then a non-zero boot, never a hang."""
    proc, _home, _etc = _run_boot(
        boot_script,
        control_plane=down_control_plane,
        tmp_path=tmp_path,
        stub_bin=stub_ttyd_path,
        timeout=60.0,  # capped backoff keeps the total well under this; a hang would trip it
    )
    assert proc.returncode != 0, "a down control plane must fail the boot non-zero (ERR trap)"

    # The retry budget is bounded (~5 attempts) — count the per-attempt log lines.
    output = proc.stdout + proc.stderr
    attempts = output.count("bootconfig attempt")
    assert 1 <= attempts <= 8, f"expected ~5 bounded attempts, saw {attempts}:\n{output}"
    # ttyd was never reached on the failure path.
    assert not (tmp_path / "home" / "ttyd-argv.txt").exists()


def test_no_credential_leak(
    boot_script: Path,
    fake_control_plane: FakeControlPlane,
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """Scrub-proof: the sentinel credential + project URL are absent from output + worker.env."""
    proc, _home, etc_burrow = _run_boot(
        boot_script,
        control_plane=fake_control_plane.url,
        tmp_path=tmp_path,
        stub_bin=stub_ttyd_path,
    )
    assert proc.returncode == 0, f"boot failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    captured = proc.stdout + proc.stderr
    assert SENTINEL_CREDENTIAL not in captured, "credential leaked into a boot log line"
    assert fake_control_plane.project_repo not in captured, "project repo URL leaked into output"

    # The short-lived credential must NEVER be persisted to the worker env file.
    worker_env = (etc_burrow / "worker.env").read_text()
    assert SENTINEL_CREDENTIAL not in worker_env, "credential persisted to worker.env (SC-3)"


def test_frozen_ttyd_line(boot_script: Path) -> None:
    """Static assertion: the frozen ttyd tail is intact (no --once, --interface 0.0.0.0)."""
    source = boot_script.read_text()
    # Ignore comment lines so a mention of --once in prose can't pass/fail spuriously.
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert "--once" not in code, "ttyd must stay PERSISTENT — no --once (ADR-0006)"
    assert "--interface 0.0.0.0" in code, (
        "ttyd must stay LAN-bound — --interface 0.0.0.0 (ADR-0007)"
    )


@pytest.mark.parametrize("flag", ["set -x"])
def test_no_set_x_on_boot_path(boot_script: Path, flag: str) -> None:
    """Pitfall 6: `set -x` would echo every command (incl. a token) — it must be absent."""
    code = "\n".join(
        line for line in boot_script.read_text().splitlines() if not line.lstrip().startswith("#")
    )
    assert flag not in code, "no `set -x` on the boot path (Pitfall 6 — would echo secrets)"
