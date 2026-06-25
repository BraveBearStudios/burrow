# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Seam-leakage guard (PLAT-06, PLAT-07).

Driver symbols must stay confined to their owning provider file. This test scans
every first-party ``api/`` source file (excluding ``tests/``, ``.venv/``,
``__pycache__/``) and asserts each forbidden symbol appears *as code* ONLY in its
allowed file(s):

- ``proxmoxer`` / ``ProxmoxAPI``  -> only ``api/compute/proxmoxProvider.py``
- ``aiosqlite`` + raw SQL          -> only ``api/db/sqliteProvider.py`` (+ migrations)

It would FAIL if, say, ``main.py`` imported ``aiosqlite`` or a model referenced
``proxmoxer`` — proving the provider boundary in CI.

Why ``tokenize`` instead of a plain grep: the seam contract is *documented* in
docstrings of non-owning files (e.g. ``compute/provider.py`` says "no
``proxmoxer`` type ever leaks"). Those prose mentions are legitimate and must not
trip the guard. Stripping comments AND string literals (docstrings are string
tokens) leaves only executable code tokens, so a count never gates on unfiltered
prose. The ``.sql`` migrations are scanned with a comment-stripped line check.
"""

import io
import tokenize
from collections.abc import Iterator
from pathlib import Path

# api/ root (this file is api/tests/unit/test_seam_leakage.py).
_API_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {"tests", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache"}

# Forbidden Python symbols -> the ONLY file(s) (relative to api/) allowed to use
# them as executable code.
_PYTHON_SEAMS: dict[str, set[str]] = {
    "proxmoxer": {"compute/proxmoxProvider.py"},
    "ProxmoxAPI": {"compute/proxmoxProvider.py"},
    "aiosqlite": {"db/sqliteProvider.py"},
}

# Raw-SQL keyword fragments -> the ONLY file(s) allowed to hold them. Migrations
# (.sql) are the schema's home; the SQLite provider holds the query strings.
_SQL_KEYWORDS = ("CREATE TABLE", "INSERT INTO", "DELETE FROM", "SELECT ")
_SQL_ALLOWED = {"db/sqliteProvider.py"}


def _python_sources() -> Iterator[Path]:
    """Yield every first-party ``api/`` ``.py`` file, skipping vendored/test dirs."""
    for path in _API_ROOT.rglob("*.py"):
        rel_parts = path.relative_to(_API_ROOT).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        yield path


def _code_tokens(source: str) -> set[str]:
    """Return the set of NAME tokens in ``source``, excluding comments/strings.

    Docstrings and string literals are STRING tokens (dropped); ``#`` lines are
    COMMENT tokens (dropped). What remains is executable identifiers, so prose
    mentions of a driver symbol cannot trip the guard.
    """
    names: set[str] = set()
    readline = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_proxmox_and_aiosqlite_symbols_are_confined() -> None:
    for path in _python_sources():
        rel = path.relative_to(_API_ROOT).as_posix()
        names = _code_tokens(path.read_text(encoding="utf-8"))
        for symbol, allowed in _PYTHON_SEAMS.items():
            if symbol in names and rel not in allowed:
                raise AssertionError(
                    f"seam leak: '{symbol}' used as code in {rel}; "
                    f"allowed only in {sorted(allowed)}"
                )


def _non_docstring_string_literals(source: str) -> list[str]:
    """Return the upper-cased contents of every non-docstring STRING literal.

    Raw SQL only ever lives *inside* string literals (``conn.execute("SELECT
    ...")``), so the guard must scan string contents — the previous version
    stripped exactly the tokens it claimed to inspect and so passed vacuously.

    Module/class/function docstrings are STRING tokens too, but they hold prose
    (e.g. a method doc reading "a cheap SELECT 1 healthcheck") that must not trip
    the guard. A docstring is the FIRST statement of a module or suite, so its
    STRING token is immediately preceded by a statement boundary: ENCODING/NEWLINE
    /NL (module top), INDENT (start of a class/function body), or a COMMENT on
    that boundary. Any other STRING (preceded by ``=``, ``(``, ``,``, a NAME …)
    is executable — that is where raw SQL would appear, so those are kept.
    """
    literals: list[str] = []
    readline = io.StringIO(source).readline
    _docstring_predecessors = {
        tokenize.ENCODING,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.COMMENT,
    }
    prev_type: int | None = None
    for tok in tokenize.generate_tokens(readline):
        if tok.type == tokenize.STRING:
            is_docstring = prev_type is None or prev_type in _docstring_predecessors
            if not is_docstring:
                literals.append(tok.string.upper())
        prev_type = tok.type
    return literals


def _has_sql_keyword(source: str) -> bool:
    """True if any SQL keyword fragment appears in a non-docstring string literal."""
    return any(
        keyword in literal
        for literal in _non_docstring_string_literals(source)
        for keyword in _SQL_KEYWORDS
    )


def test_raw_sql_is_confined() -> None:
    for path in _python_sources():
        rel = path.relative_to(_API_ROOT).as_posix()
        if rel in _SQL_ALLOWED:
            continue
        if _has_sql_keyword(path.read_text(encoding="utf-8")):
            raise AssertionError(
                f"seam leak: raw SQL fragment found in {rel}; "
                f"raw SQL is allowed only in {sorted(_SQL_ALLOWED)} + db/migrations/"
            )


def test_sql_guard_actually_bites() -> None:
    """Prove the guard is not vacuous: a non-owning file with SQL must be caught.

    The previous guard stripped string literals before scanning, so embedding
    ``conn.execute("SELECT * FROM workspaces")`` outside the provider passed
    silently. This fixture asserts the corrected guard FAILS on exactly that.
    """
    leaky = 'def go(conn):\n    return conn.execute("SELECT * FROM workspaces")\n'
    assert _has_sql_keyword(leaky), "guard must detect SQL embedded in a string literal"

    clean = '"""Module that merely mentions SELECT in prose."""\nx = 1\n'
    assert not _has_sql_keyword(clean), "guard must not trip on docstring prose"


def test_setup_caps_keep_no_proxmox_specifics_past_the_abc() -> None:
    """SETUP-07 / criterion 4: the two new caps leak no Proxmox type into routers/models.

    The global guard above already scans every ``api/`` file, so ``routers/setup.py``
    is covered automatically. This is the explicit, self-documenting anchor for the
    two new methods (``testConnection``/``verifyTemplate``): the wizard router and the
    setup DTOs (``ConnectionResult``/``TemplateResult`` in ``models/compute.py``) must
    name NO ``proxmoxer``/``ProxmoxAPI``/``ResourceException`` symbol as code — the
    caps stay provider-neutral so a Proxmox specific cannot ride the seam to the UI.
    """
    forbidden = {"proxmoxer", "ProxmoxAPI", "ResourceException"}
    for rel in ("routers/setup.py", "models/compute.py"):
        path = _API_ROOT / rel
        assert path.exists(), f"expected {rel} to exist"
        names = _code_tokens(path.read_text(encoding="utf-8"))
        leaked = forbidden & names
        assert not leaked, (
            f"seam leak: {sorted(leaked)} used as code in {rel}; the two new setup "
            "caps must stay provider-neutral (no Proxmox specifics past the ABC)"
        )

    # The neutral DTOs the two methods return are CamelModel (provider-agnostic),
    # not a driver type — assert the contract holds at the model layer.
    from models.base import CamelModel
    from models.compute import ConnectionResult, TemplateResult

    assert issubclass(ConnectionResult, CamelModel)
    assert issubclass(TemplateResult, CamelModel)


def test_migrations_dir_is_the_schema_home() -> None:
    """Sanity anchor: the SQL the guard exempts actually lives where we claim."""
    migrations = _API_ROOT / "db" / "migrations"
    sql_files = list(migrations.glob("*.sql"))
    assert sql_files, "expected at least one migration .sql under db/migrations/"
    combined = "\n".join(f.read_text(encoding="utf-8") for f in sql_files).upper()
    assert "CREATE TABLE" in combined  # the schema genuinely lives here
