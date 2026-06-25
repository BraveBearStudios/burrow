<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0012: New ComputeProvider capabilities, testConnection and verifyTemplate

## Status

Accepted

## Context

The v1.3 setup wizard (Phase 12 backend, Phase 13 UI) needs to validate two
things before an operator can run the control plane: that the Proxmox host plus
the operator-typed API token authenticate and carry the required privileges, and
that the golden worker template exists and is usable on the target node. Both
checks must happen without leaking Proxmox specifics past the ComputeProvider
seam (PLAT-06/07, the seam-leakage guard is the boundary authority), and without
persisting the powerful PVE token.

The token is the one HIGH-value asset of the whole flow: the privsep
`burrow@pve` token can clone, start, stop, and destroy containers. Two
properties of that token shaped this decision:

1. The token the wizard validates is the one the operator just typed into the
   browser. It is NOT yet in `.env`, so the runtime provider client (built from
   `.env` at init) cannot be the validation path: a fresh, throwaway client must
   be built from the request-body credentials instead.
2. The token must never come to rest. The deployment keeps it in the gitignored
   `.env` exclusively (CLAUDE.md security posture, milestone decision), so no
   secret enters the database and no token-at-rest store is introduced.

Two shapes for "where does the wizard validation logic live" were considered:

- **A. A setup-specific module that talks to Proxmox directly.** Fast to write,
  but it would put a `proxmoxer` import outside `compute/proxmoxProvider.py`,
  breaking the seam discipline the rest of the codebase holds, and it would have
  no Fake counterpart, so the wizard could not be proven in hermetic CI.
- **B. Two new provider-neutral capabilities on the ComputeProvider ABC
  (chosen).** The validation logic lives behind the same seam every other
  compute operation uses, with a real Proxmox implementation and a Fake parity
  implementation, so the wizard is CI-provable over the Fake and the
  mocked-proxmoxer tier with zero real infrastructure.

## Decision

Add two provider-neutral, read-only async capabilities to the `ComputeProvider`
ABC, implemented on BOTH the Proxmox and the Fake providers.

- **`testConnection(host, user, token_name, token_value) -> ConnectionResult`.**
  The Proxmox implementation validates the request-body token in memory via an
  EPHEMERAL throwaway `proxmoxer` client built from those exact credentials,
  never `self._api`. It issues exactly one read-only `GET /access/permissions`,
  asserts the documented BurrowProvisioner nine-privilege set is present in the
  token's effective permissions, and creates zero resources (SETUP-01). The
  ephemeral client goes out of scope when the method returns. Auth and connect
  failures surface as the typed `SetupAuthError` and `SetupUnreachableError`,
  each carrying a FIXED token-free message, so the raw driver exception string
  (which can embed auth context) is never interpolated.
- **`verifyTemplate(template_vmid, node) -> TemplateResult`.** Read-only: it
  issues template config GETs only and mutates nothing (SETUP-02). `exists` is
  whether the VMID resolved on the node; `usable` is `exists` AND the `template`
  flag being set.
- **Fake parity is mandatory.** The Fake implements both capabilities
  deterministically (success by default) with declarative negative toggles
  (`setup_missing_privileges`, `setup_auth_fails`, `setup_template_missing`), so
  every wizard path, success, missing privileges, auth failure, and template not
  found, is reachable in hermetic tests without real Proxmox.
- **Provider-neutral return types.** `ConnectionResult { success,
  missingPrivileges }` and `TemplateResult { exists, usable, vmid, node }` are
  `CamelModel` DTOs in `models/compute.py`. No `proxmoxer`, `ProxmoxAPI`, or
  `ResourceException` symbol crosses the ABC into `routers/` or `models/`.
- **Token in memory only, no token at rest.** The token is `SecretStr`-wrapped
  at both the config field and the request body, read via `.get_secret_value()`
  only at the proxmoxer boundary, and is `.env`-only at runtime. It is never
  persisted, returned in any envelope, or written to a log line (SETUP-07). A
  token-at-rest ADR is deliberately NOT written: there is no secret-at-rest
  surface this milestone, and recording that absence is the point. The setup
  errors map to fixed token-free envelope codes (`setup_unreachable`,
  `setup_auth_failed`, `setup_missing_privileges`, `setup_template_not_found`).

## Consequences

- The wizard backend stays behind the provider seam, so the seam-leakage guard
  remains the single boundary authority and a future hosted or alternative
  compute path is additive rather than a rewrite.
- The Fake must track the two capability behaviors, including the negative
  toggles, so a change to the validation contract has to update the Fake too.
  That is the cost of keeping the wizard hermetically testable, and it is the
  same parity discipline the rest of the compute contract already follows.
- Validation creates zero resources and reads only, so running the wizard
  repeatedly is safe and leaves no orphan containers or clones (SETUP-01).
- No secret enters the database or a log line, so the store needs no
  encryption-at-rest and the wizard adds no new sensitive surface. The
  sentinel-token leak test locks this RED-if-regressed.
- The setup endpoints do not stamp `setupCompletedAt`: Phase 12 reads setup
  state only, and the setter plus the first-run gate and the UI are Phase 13.

## Revisit trigger

A future need to persist or rotate the token (which would force a secret-at-rest
store and the encryption and key-management work it needs), or a compute backend
that cannot express a read-only capability probe and so cannot satisfy the
zero-resource validation contract.
