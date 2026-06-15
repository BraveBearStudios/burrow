<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow — UI design prompt

Paste this into the design app to generate the Burrow interface. It is self-contained: product context, the
Burrow design system, every screen, and component states. Build in the **dark (hero) theme** first;
support all four theme modes.

---

## Product

Burrow is a browser-accessible manager for multiple concurrent Claude Code sessions. Each "workspace" is an
ephemeral Linux container running a Claude Code terminal (via ttyd), proxied to the browser over WebSocket. The
UI is a developer tool (auth-gated) — think "tmux for cloud workspaces" with a tiling terminal
grid. It uses the Burrow design system.

**Primary user job:** spin up a workspace from a git repo, watch several Claude sessions run side by side in a
draggable grid, and tear them down when done.

---

## Design system — the Burrow design system

Forest-tinted surfaces, warm neutrals, hairline borders, prestige gold accents. Default to the dark hero theme.

### Themes (provide a 4-swatch switcher in the top bar)

| Theme | Page bg | Use |
|---|---|---|
| `dark` (default, hero) | `#1a1c1a` near-black forest | primary |
| `dark-soft` | `#3a4740` pine/moss | low-light |
| `medium` | `#6a8170` mid-sage | marketing/hero |
| `light` | `#f0f2f0` warm off-white | day |

### Color tokens (dark → light)

```
--bg            #1a1c1a → #f0f2f0      page background (level 0)
--bg-surf       #212321 → #ffffff      cards / bars (level 1)
--bg-panel      #272927 → #ffffff      panel headers (level 2)
--bg-panel-alt  #2e302e → #f0f2f0      inputs / raised (level 3)
--text          #ccd8cc → #1a221a
--text-sub      #7a8e7a → #4a5a4a
--text-muted    #546654 → #8a9a8a
--accent        #344734 (both)         green-500 — the ONLY primary interactive color
--accent-bg     rgba(52,71,52,.22) → .07
--gold          #f0a737 → #c8841a      PRESTIGE ONLY
--gold-bg       rgba(240,167,55,.12) → .09
--border        rgba(255,255,255,.08) → rgba(52,71,52,.10)
--border-mid    rgba(255,255,255,.14) → rgba(52,71,52,.18)
--ok #4ade80   --warn #fbbf24   --err #e05050
```

### Core rules (override everything)

- Green `#344734` is the **only** primary interactive color — buttons, active states, focus rings, panel-active border.
- Gold `#f0a737` is **prestige-only**: model labels, token-savings stats, session uptime, status dots, the wordmark descriptor label. Never a button, body text, or full border.
- All borders are **0.5px hairlines**. Only exception: the active/selected panel ring (`1px`/accent).
- **No gradients, no shadows, no glow.** Depth comes from the four background levels only.
- **Font-weight max 500.** Never 600/700 in UI.
- **Sentence case** everywhere. Uppercase only for 11px overlines (letter-spacing 1.3px).
- Never use pure grays (`#111`, `#1a1a1a`, `#222`) — always the forest-tinted neutral scale.
- Icons: inline outline SVG, 1.5px stroke (1.8px active), `currentColor`.

### Type

- Display / brand titles: **Space Grotesk** 500.
- UI / body: **Inter** 400–500.
- Terminals, stats, repo paths, branch chips: **JetBrains Mono** 400.
- Scale: page title 28–36 · section 16 · body 13–14 · small 11–12 · overline 11 (uppercase, tracked).

### Other

- Radius: cards `12px`, buttons/inputs `8px`, nav rows `8px`, badges `6px`, dots `9999px`.
- Spacing on a 4px base (8/12/16/20/24…). No arbitrary values.
- Motion: `cubic-bezier(0.16,1,0.3,1)`, 120ms on hover, `scale(0.98)` on press.

---

## Layout — single full-screen app shell

```
┌───────────────────────────────────────────────────────────────────────┐
│ TOP BAR (52px)                                                          │
│ [hex mark] Burrow   [node1 chip][node2 chip]   [themes][+ New]  │
├──────────────┬────────────────────────────────────────────────────────┤
│ SIDEBAR      │ MAIN — tiling terminal grid (react-mosaic)              │
│ (228px)      │  ┌───────────────┬───────────────┐                      │
│ Workspaces   │  │ ProjectAlpha  │ ProjectBeta   │  ← draggable,        │
│  • rows w/   │  │ [terminal]    │ [terminal]    │     splittable,      │
│    status    │  ├───────────────┴───────────────┤     resizable panels │
│    dots      │  │ ProjectGamma (spans 2 cols)   │                      │
│  ─────────   │  │ [terminal]                    │                      │
│  user row    │  └───────────────────────────────┘                      │
├──────────────┴────────────────────────────────────────────────────────┤
│ STATUS BAR (32px)  3 running · 1 stopped · 1 error   rtk 69% · 2h 14m   │
└───────────────────────────────────────────────────────────────────────┘
```

All columns `overflow: hidden` with inner scroll. Top bar and status bar never grow.

### Top bar
- Left: hexagonal brand mark — **gold** hex stroke (`#f4bb62`) on a green-500 rounded square (`rx 7`). Beside it,
  "Burrow" in Space Grotesk 500, optionally with a small gold descriptor overline underneath.
- Center: one capacity chip per Proxmox node — status dot + `node1 · 3 running · 11 GB free`, with the **numbers in
  gold mono**. Surface `--bg-panel`, hairline border.
- Right: four circular theme swatches, then the primary **`+ New workspace`** button (green, text `#bdd4bd`).

### Sidebar (top → bottom)
1. "Workspaces" overline + overflow-menu dot.
2. Scrollable workspace list. Each row: a **status dot**, the name (Inter 500), and `repo · branch` in muted mono
   below. Inline state overline for non-running states (`creating`/`error`/`stopped`) in the matching status color.
   Active row: `--accent-bg` fill + a 2px green left-edge bar.
3. Pinned user row (border-top): initials avatar in an accent-tinted circle, username, a descriptor label, gear.

### Main — terminal grid
A react-mosaic tiling area. Each panel:
- **Header (36px, `--bg-panel`):** drag grip · workspace name · branch chip (mono) · **model label in gold**
  (`claude-opus-4 · rtk`) · spacer · icon buttons: split, detach (plug icon), terminate (×).
- **Body:** a real terminal (xterm.js). For the mockup, monospace Claude Code output — `✻` banner with gold
  token-savings note, a `›` prompt line, green `●` action bullets, and a blinking green block cursor.
- Active panel gets the `1px` green ring; others keep the `0.5px` hairline.

### Status bar
Left: running / stopped / error counts with **gold numbers** and matching status dots. Right: `rtk · 69% tokens
saved` (gold) and `session uptime 2h 14m` (gold), each with a small icon.

---

## Component states to render

**Workspace row / status dot:** `running` green · `creating` amber · `error` red · `stopped` muted.
**Terminal panel:**
- normal (live cursor),
- **active** (green ring),
- **detached / reconnecting** — translucent overlay over the body: spinner + "reconnecting… attempt 1 / 5" +
  a "Reattach" button (the session survives a tab close; this is detach, not terminate),
- **terminated** — dimmed panel.

**New workspace modal** (centered, `--bg-surf`, hairline, radius 12):
- *Form state:* fields — Name, Git repo, Branch (default `main`), Node (`node1`/`node2`). Footer: secondary
  Cancel + primary green Create.
- *Creating state:* the same modal swaps to a checklist that animates through the real create saga —
  `✓ Reserving VMID 207 · writing row` → `✓ Cloning template (9000 → 207)` → `⟳ Starting LXC · waiting for IP`
  → `○ Waiting for Claude (ttyd health)`, with a mono footnote `POST /api/v1/workspaces → 202 · polling status…`.
  Steps flip from muted to full-contrast as they complete; the active step shows a gold-topped spinner.

---

## Interactions

- Theme swatch → swap the whole app theme.
- Click a sidebar row → focus its panel (sync active state both ways).
- Detach button → show the reconnecting overlay; Reattach dismisses it.
- Terminate button → dim the panel.
- `+ New workspace` → open the modal; Create → run the animated saga, then close.
- Panels are draggable / splittable / resizable (react-mosaic behavior).

---

## What to produce

High-fidelity screens for: (1) the full app shell in the **dark** theme populated as above; (2) the same shell in
`light`, `dark-soft`, and `medium`; (3) the New workspace modal in both form and creating states; (4) the panel
detached/reconnecting and terminated states. Keep every surface flat, every border a hairline, gold strictly on
stats/labels/dots, and green as the only action color.

> Reference implementation: `docs/design/burrow-ui-mockup.html` (interactive, all states wired).
> Tokens: the design system's `tokens.css` (the color/type values above are the source of truth). Component contracts: tech-spec §8.
