# OSS Design System

> A neutral, unbranded foundation for open-source software. Warm-tinted surfaces, hairline borders, a flexible neutral accent, and conventional status colors. Light and dark modes out of the box — built to be overridden.

This is the open-source variant of an internal design system, stripped of all brand color and identity. It ships generic light/dark defaults so any project can adopt it and point one token (`--accent`) at its own brand.

---

## VISUAL FOUNDATIONS

**Colors.** One raw scale — `neutral` (14 stops, subtly warm, never pure gray). Semantic tokens (`--bg`, `--bg-surf`, `--text`, `--accent`, `--accent-fg`, `--border`) resolve per theme. The accent defaults to a near-black neutral in light and a near-white neutral in dark, so you get a real "primary" for free; swap it for a brand hue and the whole system follows.

**Two theme modes:**
- **Light** (`:root`) — warm off-white surfaces, near-black neutral accent.
- **Dark** (`.dark` / `[data-theme="dark"]`) — warm near-black surfaces, near-white neutral accent.

**Status.** Conventional signal hues — `--status-ok` (green), `--status-warn` (amber), `--status-err` (red), `--status-info` (blue) — each with a matching `--signal-*-bg` tint, tuned per theme.

**Typography.** System font stacks — `--font-display`, `--font-ui`, `--font-mono`. No web-font dependency, fast and unbranded; override the variables to bring in a brand face.

**Borders.** Hairline (0.5px) system in three weights. No drop shadows.

**Radius.** 3 / 6 / 8 / 10 / 12 / 16px scale, plus `--radius-full`.

## CONTENT FUNDAMENTALS

**Casing.** Sentence case across the board. The only uppercase is overlines (9–10px, tracked 1.3px) — `RECENT`, `ACTIVE CONNECTORS`, `SESSION STATS`.

**Voice.** Second-person, technical, unhedged. Middle-dot `·` as the universal separator.

## ICONOGRAPHY

Minimalist custom stroke icons, inline-SVG, 1.5px default stroke weight (1.8px when active). No icon font, no library dependency, no PNG icons.

## LOGO

The mark and wordmark are neutral placeholders (`assets/`) — a rounded square with a dot, paired with a system-sans wordmark. Drop in your own.

## FILES

- `colors_and_type.css` — all tokens + base type
- `preview/` — token and component cards
- `ui_kits/web/` — reference app (three-column layout)
- `assets/` — placeholder mark + wordmarks
