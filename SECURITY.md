<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Security Policy

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Report them privately to **security@bravebearstudios.com**. Include, where you can:

- a description of the issue and its impact,
- steps to reproduce (proof-of-concept if available),
- affected version, commit, or deployment, and
- any suggested remediation.

You can expect an acknowledgement within a few business days. We will work with
you on a fix and a coordinated disclosure timeline, and we are happy to credit
reporters who wish to be named.

## Scope

Burrow is, in its v1/self-host form, **LAN-only with no authentication by design**
(see the tech spec's security posture). On that deployment, anyone who can reach
the control plane has an unauthenticated terminal in every workspace. That is an
accepted operational model, not a vulnerability — do not report it as one.
Reports that assume an internet-exposed v1 deployment are out of scope.

In scope, for example:

- Issues that let a workspace escape its container or reach the control plane in
  ways the architecture does not intend.
- Credential, token, or secret leakage beyond the documented threat model.
- Flaws in the (v2) auth, JWT validation, tenancy isolation, or RLS layers.
- Injection, SSRF, or path-traversal in the control-plane API or terminal proxy.

## Supported versions

Burrow is pre-release (no tagged versions yet). Until a first release, security
fixes land on `main`. This policy will list supported version ranges once
releases begin.

## Handling secrets

Never include real secrets, tokens, or private hostnames in an issue, PR, or
test fixture. `.env` is gitignored; use `.env.example` for templates.
