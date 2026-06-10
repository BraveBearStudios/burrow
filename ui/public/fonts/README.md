<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Self-hosted fonts

Burrow self-hosts its three faces; it never loads a font from an external font
or icon CDN. That CDN-free posture is a hard CSP/security requirement (CLAUDE.md,
PLAT-05, 02-UI-SPEC Security Reconciliation) — the design mockup's external font
`<link>` is a prototype shortcut that must not ship.

## Faces

| Role | Family | Weight | File to drop here |
|------|--------|--------|-------------------|
| Display / brand | Space Grotesk | 500 | `SpaceGrotesk-Medium.woff2` |
| UI / body | Inter | 400, 500 | `Inter-Regular.woff2`, `Inter-Medium.woff2` |
| Mono / terminal | JetBrains Mono | 400 | `JetBrainsMono-Regular.woff2` |

## How it works

`src/index.css` declares an `@font-face` for each face (`font-display: swap`)
pointing at `/fonts/<file>.woff2`. The faces are **not vendored in this commit**
(no upstream package or design-bundle woff2 was available to copy at build time),
so the `@font-face` blocks are commented out and the `--font-display` / `--font-sans`
/ `--font-mono` tokens resolve to the `_ds` **system stacks** as a CDN-free fallback:

- sans/display → `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, …`
- mono → `ui-monospace, 'SF Mono', Menlo, Consolas, …`

The UI renders correctly today on the system stack. To activate the Burrow faces:

1. Drop the woff2 files listed above into this directory (AGPL/OFL-compatible
   licensing only — record provenance in this README).
2. Uncomment the matching `@font-face` blocks in `src/index.css`.
3. Prepend the family name to the relevant `--font-*` token, e.g.
   `--font-mono: "JetBrains Mono", ui-monospace, …`.

No network font request is ever introduced by any of these steps.
