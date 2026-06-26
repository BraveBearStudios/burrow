---
phase: 12-setup-wizard-backend
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - api/compute/provider.py
  - api/compute/proxmoxProvider.py
  - api/compute/fakeProvider.py
  - api/config.py
  - api/db/provider.py
  - api/db/sqliteProvider.py
  - api/lib/logging.py
  - api/main.py
  - api/models/compute.py
  - api/routers/setup.py
  - api/tests/integration/mock_proxmox.py
  - api/tests/integration/test_mock_proxmox.py
  - api/tests/integration/test_proxmox_provider.py
  - api/tests/integration/test_setup_api.py
  - api/tests/integration/test_setup_token_leak.py
  - api/tests/unit/test_seam_leakage.py
  - api/tests/unit/test_setup_caps.py
  - docs/adr/ADR-0012-compute-provider-setup-caps.md
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

This is the setup-wizard backend (SETUP-01/02/03/07): two read-only
ComputeProvider capabilities (`testConnection`, `verifyTemplate`), their Proxmox
and Fake implementations, the `/api/v1/setup/*` router, the envelope/error
handlers in `main.py`, the JSON-logging whitelist, and the supporting test
tiers. I reviewed it adversarially against the SETUP-07 hard gate (the PVE token
must never persist, never enter an envelope, never reach a log line).

**The hard gate holds.** Every token-leak surface I traced is closed:

- `.get_secret_value()` appears at exactly three boundaries — the runtime
  proxmoxer client (`proxmoxProvider.__init__:89`), the router call site
  (`routers/setup.py:77`), and the ephemeral validation client receives the raw
  value as a method parameter (`proxmoxProvider.testConnection:375`), never from
  settings. No fourth call site exists.
- `testConnection` builds a throwaway `eph` client and never assigns to or reads
  `self._api`; the token is never stored.
- The 422 `RequestValidationError` handler (`main.py:243`) reshapes errors to
  `loc`/`msg`/`type` only, dropping the raw `input`/`ctx`, so a token sent
  alongside a bad field cannot echo back. The body field is `SecretStr` as a
  second layer.
- Every setup error path raises a FIXED token-free message and uses
  `raise ... from None` to drop the proxmoxer cause; the envelope codes pull from
  `_SAFE_ERROR_MESSAGES`, never `str(exc)`.
- The JSON formatter whitelists `extra` keys, and `setup_logging` pins
  `proxmoxer`/`urllib3`/`requests` to WARNING.
- The sentinel test (`test_setup_token_leak.py`) is genuinely RED-if-regressed:
  it sweeps both envelopes, every table enumerated from `sqlite_master`, and a
  DEBUG-level captured log stream, and proves non-vacuity by asserting the
  `settings` table was actually scanned.
- Seam discipline holds: `ConnectionResult`/`TemplateResult` are `CamelModel`,
  no `proxmoxer`/`ProxmoxAPI`/`ResourceException` symbol crosses into
  `routers/` or `models/`, and exceptions are inspected by attribute/message,
  never by importing the driver type. The seam-leakage guard backs this in CI.
- ADR-0012 is em-dash-free, correctly formatted, and honest about scope.

No CRITICAL issues. The findings below are correctness/triage/test-quality
defects that should be addressed but do not breach the token gate.

## Warnings

### WR-01: `verifyTemplate` misclassifies every non-404 error as "host unreachable"

**File:** `api/compute/proxmoxProvider.py:393-408`
**Issue:** On any non-404 exception the template config GET raises
`SetupUnreachableError("proxmox host was unreachable")`. Unlike `testConnection`,
it does **not** consult `_is_auth_error`. A 401/403 (the operator's runtime
token is wrong or lost its template-read rights) or a 500 therefore surfaces to
the wizard as "Could not reach the Proxmox host" — the wrong diagnostic, which
will send an operator chasing a network problem when the real cause is auth.
This is a triage/correctness defect, not a leak (the message is fixed). It also
diverges from the `testConnection` contract, which carefully distinguishes auth
from connect failures.
**Fix:** Mirror `testConnection`'s branching:
```python
except Exception as exc:
    if _is_not_found(exc):
        return TemplateResult(exists=False, usable=False, vmid=template_vmid, node=node)
    if _is_auth_error(exc):
        raise SetupAuthError("proxmox token was rejected (auth failed)") from None
    raise SetupUnreachableError("proxmox host was unreachable") from None
```

### WR-02: `getNodeMemory` lets a raw `KeyError` escape the compute seam

**File:** `api/compute/proxmoxProvider.py:348-351`
**Issue:** `mem, maxmem = status["mem"], status["maxmem"]` indexes the proxmoxer
status dict directly. If the node status response omits either key (a Proxmox
version/permission quirk, or a node returning a partial body), a bare `KeyError`
is raised. `KeyError` is **not** a `ComputeError`, so it bypasses the typed seam
and the saga/router compensation that expects only `ComputeError` subclasses,
landing as an opaque generic 500. Every other read method in this file uses
`.get(...)` with a default (see `getStatus:336-342`) precisely to avoid this; this
method is the lone inconsistency. The capacity guard (CAP-01) depends on it.
**Fix:** Use defensive access consistent with `getStatus`:
```python
mem = float(status.get("mem", 0))
maxmem = float(status.get("maxmem", 0))
return mem / maxmem if maxmem else 1.0
```

### WR-03: Tautological assertion in the auth-fail leak test

**File:** `api/tests/integration/test_setup_api.py:274`
**Issue:** `assert "t" not in str(exc_info.value) or "token" in str(exc_info.value)`
is always True and can never fail. The fixed message is `"proxmox token was
rejected (auth failed)"`, which contains `"token"`, so the right operand is
permanently satisfied regardless of what the left operand evaluates to. The token
in this test is the single char `"t"`, which is additionally present in the
message. This assertion provides **zero** leak protection on this path — it would
pass even if the rejected token were interpolated into the error. (The dedicated
`test_setup_token_leak.py` sentinel still covers the real gate, so this is a
test-quality defect, not a gap in the gate itself.)
**Fix:** Assert against a real multi-char sentinel that is not a substring of the
fixed message, as the sibling unit test does:
```python
SENTINEL = "SENTINEL-TOKEN-DO-NOT-LEAK"
...
result = ... token_value=SENTINEL
assert SENTINEL not in str(exc_info.value)
```

### WR-04: `_is_running_or_locked` `"lock"` substring is over-broad

**File:** `api/compute/proxmoxProvider.py:471-478`
**Issue:** The discriminator matches the bare substring `"lock"`, which also
matches `"unlock"`, `"deadlock"`, `"clock"`, `"blocked"`, etc. A destroy failure
whose message merely contains one of those words (and is not actually a
running/locked CT) would be misclassified as running/locked, triggering an
unnecessary stop-then-retry-DELETE cycle against a CT that may be in a genuinely
unrecoverable state — masking the real failure as a second, different error.
The adjacent `"is locked"` and `"can't lock"` clauses already cover the real
Proxmox phrasings, so the bare `"lock"` is redundant and only adds false
positives.
**Fix:** Drop the bare `"lock"` clause (keep `"is locked"` / `"can't lock"` /
`"running"` / `"not stopped"`), or anchor it to the real message tokens Proxmox
emits.

### WR-05: 422 leak protection depends on Pydantic `msg` never embedding input

**File:** `api/main.py:243-261`
**Issue:** The handler correctly drops `input` and `ctx` and keeps only
`loc`/`msg`/`type`. This is safe for the token field today because Pydantic v2's
`missing` and `string_type` errors use fixed message templates that do not
interpolate the submitted value. However, some Pydantic error types **do** embed
the offending input in `msg` (e.g. `value_error`, enum/literal mismatches, custom
validators that f-string the value). If a future setup-body field gains a
validator of that kind, the token-bearing body could re-enter the 422 `msg`. The
current defense is correct but rests on an undocumented Pydantic invariant.
**Fix:** Either keep the `SecretStr` field as the load-bearing guarantee (it
already masks the token even inside a `msg`, which is the real backstop) and add
a comment making that the documented invariant, or drop `msg` to a fixed
per-`type` string for setup routes. Lowest-risk: add a regression test that posts
a malformed `tokenValue` (e.g. wrong JSON type) with a sentinel and asserts the
sentinel is absent from the 422 body, locking the `SecretStr` backstop
RED-if-regressed.

## Info

### IN-01: `injectBootConfig` parameter unused; no-op is intentional but unmarked

**File:** `api/compute/proxmoxProvider.py:259-266`, `api/compute/fakeProvider.py:157-160`
**Issue:** Both implementations accept `config: BootConfig` and discard it. The
docstrings explain this is a deliberate seam stub (pull-at-boot; the v1 saga
persists via the DbProvider). That is fine, but `config` is a genuinely unused
parameter that lint tooling (ruff `ARG002`) may flag, and the Fake additionally
omits even the docstring's promised no-op rationale on the `vmid` parameter.
**Fix:** No behavior change needed. If ruff flags it, name the parameter `_config`
or add a `# noqa: ARG002` with the seam rationale already in the docstring.

### IN-02: `test_real_provider_auth_fail_raises_setup_auth_error` uses a 1-char token

**File:** `api/tests/integration/test_setup_api.py:271`
**Issue:** `token_value="t"` is too short to be a meaningful leak probe — a single
common letter will appear in almost any message by chance, which is exactly what
makes WR-03's assertion vacuous. Even after WR-03 is fixed, a 1-char token is a
weak sentinel.
**Fix:** Use a distinctive multi-char sentinel string for `token_value` in this
and the sibling `test_real_provider_*` setup tests.

### IN-03: `verifyTemplate` does not validate `template_vmid` is in the worker/template range

**File:** `api/compute/proxmoxProvider.py:393-408`, `api/routers/setup.py:82-91`
**Issue:** `verify-template` accepts an arbitrary `templateVmid` from the request
body and issues `nodes(node).lxc(template_vmid).config.get()` against it. Because
it is strictly read-only (GET only, no mutation) this is not a security issue in
v1 (LAN-only, no auth by design), and enumeration is bounded by the read-only
contract. Noting it only so a future hardening pass (Phase 13/hosted path) is
aware the endpoint will resolve any caller-supplied VMID's config, not just the
configured template range.
**Fix:** None required for v1. If/when auth lands, constrain `template_vmid` to
the configured template/pool range and return the generic not-found shape for
out-of-range values (the same enumeration-resistance pattern `IllegalVmidError`
already uses for bootconfig).

### IN-04: `_node_fractions or {}` discards a falsy-but-distinct empty dict intent

**File:** `api/compute/fakeProvider.py:99`
**Issue:** `self._node_fractions = node_fractions or {}` is harmless (an empty
dict and `None` both fall back to the single-float behavior, which the docstring
documents), but the `or` idiom conflates "explicitly passed `{}`" with "passed
`None`". Pure code-quality nit; no behavioral defect because both intended
outcomes are identical here.
**Fix:** Optional: `node_fractions if node_fractions is not None else {}` to make
the intent explicit. Not worth changing on its own.

---

_Reviewed: 2026-06-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
