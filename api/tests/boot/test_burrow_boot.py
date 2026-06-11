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
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.boot.conftest import (
    SENTINEL_CREDENTIAL,
    FakeControlPlane,
    ManifestConfigRepo,
    make_boot_env,
    serve_bootconfig,
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


# --- Plan 02: manifest processing (process_manifest + install_claude_plugin) --


def _plugins_dir(home: Path) -> Path:
    """``~/.claude/plugins`` under the temp HOME."""
    return home / ".claude" / "plugins"


def test_only_claude_plugins_installed(
    boot_script: Path,
    manifest_config_repo: Callable[..., ManifestConfigRepo],
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """A claude-plugin + a binary entry → only the claude-plugin is cloned; binary is skipped."""
    repo = manifest_config_repo(include_binary=True)
    with serve_bootconfig(repo) as cp:
        proc, home, _etc = _run_boot(
            boot_script, control_plane=cp.url, tmp_path=tmp_path, stub_bin=stub_ttyd_path
        )
    assert proc.returncode == 0, f"boot failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    plugins = _plugins_dir(home)
    for name in repo.claude_plugin_names:
        assert (plugins / name / "plugin.json").is_file(), (
            f"claude-plugin {name!r} not cloned into ~/.claude/plugins/{name}"
        )
    for name in repo.skipped_names:
        assert not (plugins / name).exists(), (
            f"non-claude-plugin {name!r} must be SKIPPED at boot (baked at provision time)"
        )

    # The plugin was enabled in the user settings (enabledPlugins write).
    settings = home / ".claude" / "settings.json"
    assert settings.is_file(), "settings.json not written by install_claude_plugin"


def test_two_boots_identical_plugin_tree(
    boot_script: Path,
    manifest_config_repo: Callable[..., ManifestConfigRepo],
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """Two boots over the same manifest produce a byte-identical plugin tree (SC-2)."""
    repo = manifest_config_repo(include_binary=True)

    def _digest(plugins: Path) -> list[tuple[str, str]]:
        import hashlib

        out: list[tuple[str, str]] = []
        for path in sorted(plugins.rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                rel = path.relative_to(plugins).as_posix()
                out.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))
        return out

    boot1 = tmp_path / "boot1"
    boot1.mkdir()
    boot2 = tmp_path / "boot2"
    boot2.mkdir()
    with serve_bootconfig(repo) as cp:
        proc1, home1, _e1 = _run_boot(
            boot_script, control_plane=cp.url, tmp_path=boot1, stub_bin=stub_ttyd_path
        )
        proc2, home2, _e2 = _run_boot(
            boot_script, control_plane=cp.url, tmp_path=boot2, stub_bin=stub_ttyd_path
        )
    assert proc1.returncode == 0, f"boot1 failed:\n{proc1.stdout}\n{proc1.stderr}"
    assert proc2.returncode == 0, f"boot2 failed:\n{proc2.stdout}\n{proc2.stderr}"

    tree1 = _digest(_plugins_dir(home1))
    tree2 = _digest(_plugins_dir(home2))
    assert tree1, "no plugin files were installed — nothing to compare"
    assert tree1 == tree2, "two boots of the same manifest produced different plugin trees (SC-2)"


def test_bad_manifest_fails_boot(
    boot_script: Path,
    manifest_config_repo: Callable[..., ManifestConfigRepo],
    stub_ttyd_path: Path,
    tmp_path: Path,
) -> None:
    """An unknown plugin ``type`` → the boot-time jq gate fails the boot non-zero (fail-closed)."""
    repo = manifest_config_repo(include_binary=True, bad_type=True)
    with serve_bootconfig(repo) as cp:
        proc, _home, _etc = _run_boot(
            boot_script, control_plane=cp.url, tmp_path=tmp_path, stub_bin=stub_ttyd_path
        )
    assert proc.returncode != 0, (
        "an unknown plugin type must FAIL the boot non-zero (fail-closed jq gate, ERR trap)"
    )
    # ttyd must never be reached on the fail-closed path.
    assert not (tmp_path / "home" / "ttyd-argv.txt").exists(), "ttyd reached despite a bad manifest"


# --- Code-review fixes (Phase 3 REVIEW.md WR-01..05) --------------------------


def _redact(boot_script: Path, text: str, git_cred: str | None) -> str:
    """Call the boot script's own ``redact_secrets`` helper on ``text`` (WR-01 backstop)."""
    setcred = f"GIT_CRED={git_cred!r}\n" if git_cred is not None else ""
    script = (
        f"{setcred}"
        f"eval \"$(sed -n '/^redact_secrets() {{/,/^}}/p' '{boot_script}')\"\n"
        f"redact_secrets {text!r}\n"
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=30, check=True
    ).stdout


def test_err_trap_redacts_real_token_shapes(boot_script: Path) -> None:
    """WR-01: the redaction backstop covers the live cred + x-access-token/ghs_/github_pat_.

    The legacy ``ghp_*`` glob matched NONE of the credential shapes this design mints
    (x-access-token / ghs_ / github_pat_) and was over-greedy (``*`` swallowed the rest of
    the line). The replacement must redact each shape — including the live ``$GIT_CRED``
    value exactly — and preserve trailing text.
    """
    sentinel = "SENTINEL-bootcred-9f2c4e7a1b6d8054-DO-NOT-LOG"
    bad = (
        "clone x-access-token:ghs_AbC123DEF456 mid "
        f"{sentinel} end github_pat_11ABCDE_xyz999 TAILKEEP"
    )
    out = _redact(boot_script, bad, git_cred=sentinel)
    assert sentinel not in out, f"live credential not redacted: {out!r}"
    assert "ghs_AbC123DEF456" not in out, f"ghs_ token not redacted: {out!r}"
    assert "github_pat_11ABCDE_xyz999" not in out, f"github_pat_ token not redacted: {out!r}"
    assert "[redacted]" in out, f"expected a [redacted] marker: {out!r}"
    # The over-greedy ghp_* glob would have eaten everything after the first token; the
    # bounded patterns must preserve trailing text.
    assert "TAILKEEP" in out, f"redaction swallowed trailing text (over-greedy): {out!r}"


def test_redaction_backstop_works_without_live_cred(boot_script: Path) -> None:
    """WR-01: even with $GIT_CRED unset, the format-aware layer still redacts token shapes.

    Models a future refactor that puts a token on a command line BEFORE $GIT_CRED is set —
    the format-aware net must still catch the legacy/ghs_/github_pat_ shapes.
    """
    out = _redact(
        boot_script,
        "url https://x-access-token:ghs_ZZZ999@h/r and ghp_classic123 KEEPTAIL",
        git_cred=None,
    )
    assert "ghs_ZZZ999" not in out, f"ghs_ not redacted without live cred: {out!r}"
    assert "ghp_classic123" not in out, f"ghp_ not redacted without live cred: {out!r}"
    assert "KEEPTAIL" in out, f"redaction swallowed trailing text: {out!r}"


