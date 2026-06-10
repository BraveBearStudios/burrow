<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0008: Stack version bumps over the spec's `^` ranges

## Status

Accepted

## Context

`docs/tech-spec.md` pins several dependencies with loose `^x` ranges that were written
against an earlier snapshot of the ecosystem. Live registry reads on **2026-06-09**
(npm `npm view <pkg> version|dist-tags|peerDependencies` and the PyPI JSON API),
recorded in `.planning/research/STACK.md`, show current stable is a **major version
ahead** of the spec's ranges in several places. CLAUDE.md and CONTRIBUTING.md require
that any deviation from the baseline architecture be recorded as an ADR before merge.

The deviations share **one rationale** (the spec's ranges are a major version behind
current stable) and **one evidence base** (the STACK.md live reads on 2026-06-09), so
they are recorded as a single consolidated ADR rather than eight near-identical ones.
None of these bumps is a build blocker; each is a pin decision made at scaffold.

## Decision

Pin the current-stable versions below, overriding the spec's `^` ranges. Evidence for
every pin is STACK.md's live registry read on 2026-06-09.

| Dependency | Spec range | Pinned | Note |
|---|---|---|---|
| Vite | `^6` | **8.0.16** | Plugin ecosystem moved to v8; `@vitejs/plugin-react@6` peers `vite ^8`. |
| TypeScript | `^5` | **6.0.3** | Current stable major; fall back to 5.9.x only if a dep lags. |
| @biomejs/biome | `^1` | **2.4.16** | Biome **2.x**; the `biome.json` schema was rewritten — write the config fresh, do not port a 1.x config. |
| Vitest | (implied 1.x era) | **4.1.8** | Matches Vite 8. |
| @xterm/xterm (+ addons) | `^5` | **6.0.0** (fit `0.11.0`, web-links `0.12.0`) | Scoped `@xterm/*` packages; the legacy unscoped `xterm` / `xterm-addon-*` are npm-deprecated ("Move to @xterm/xterm instead"). |
| mypy | (implied 1.x era) | **2.1.0** | mypy is now **2.x** — a major bump from 1.x; pin exactly and use a strict config (some `[tool.mypy]` keys differ from 1.x). Do not float. |
| react-mosaic-component | `^7` | **6.2.0** | Stable **6.2.0** (published 2026-04-16) peers `react >=16` (React 19 OK). The npm `latest` tag points at `7.0.0-beta0`; do **NOT** chase the beta — the newer-dated stable is 6.2.0. |
| Tailwind | `^4` (with `ui/tailwind.config.ts`) | **4.3.0** via `@tailwindcss/vite`, **no `tailwind.config.ts`** | Tailwind v4 is CSS-first (`@import "tailwindcss"` + `@theme {}` in CSS) and uses the `@tailwindcss/vite` plugin, not PostCSS. The spec's `ui/tailwind.config.ts` is the v3 pattern and is dropped. |

Two of these are not just version bumps but **config-shape** changes that callers must
honor:

- **Biome 2** ships a different `biome.json` schema than 1.x — author it fresh.
- **Tailwind v4** has **no JS config file**: the planned `ui/tailwind.config.ts`
  (spec §4.1 tree) is removed; configuration moves into CSS `@theme` plus the
  `@tailwindcss/vite` plugin.

## Consequences

- The Biome configuration is written against the 2.x schema; a 1.x `biome.json` would
  not validate.
- `ui/tailwind.config.ts` is **not** created (and the spec §4.1 tree entry for it is
  superseded). Styling configuration lives in CSS (`@theme`) with `@tailwindcss/vite`;
  no PostCSS / `autoprefixer` / JS config.
- mypy 2.x strict config keys may differ from the 1.x era; the `[tool.mypy]` block is
  authored for 2.x and pinned exactly so CI does not float onto a future major.
- `react-mosaic-component` is held at stable **6.2.0**; the spec's `^7` would have
  pulled `7.0.0-beta0` (a pre-release with `uuid 11` / `react-dnd 9` churn). A `^7`
  range must not be reintroduced until `7.0.0` ships stable.
- Only the `@xterm/*` scoped packages are used; the deprecated unscoped names are
  forbidden.
- These pins are exact (no floating ranges) so the lockfile gates (`uv lock --check`,
  `npm ci`) stay deterministic. Most UI runtime installs land in Phase 2; this ADR fixes
  the versions now so the static gates and Phase 2 scaffold agree.

## Revisit trigger

`react-mosaic-component 7.0.0` going stable (drop the 6.2.0 hold), a transitive
dependency that lags a pinned major (e.g. a `@types/*` or plugin not yet supporting
TS 6 / Vite 8, forcing a documented fall-back), or the next routine version-bump review
against fresh registry reads.
