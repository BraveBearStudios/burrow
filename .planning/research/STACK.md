# Stack Research

**Domain:** Self-hosted browser control-plane for ephemeral Claude Code worker LXCs (FastAPI control plane + Vite/React tiling terminal UI + Proxmox compute)
**Researched:** 2026-06-09
**Confidence:** HIGH (all versions verified live against npm registry and PyPI JSON API on the research date; friction points verified against official docs)

> **Mandate:** The stack is fixed by `docs/tech-spec.md`. This file does **not** propose a new stack — it pins exact current-stable versions, confirms mutual compatibility, and flags where the spec's loose ranges are now behind reality. Every version below was read from `npm view <pkg> version` / `pip`/PyPI `…/json` on 2026-06-09, not from training data.

## Headline Findings (read first)

1. **react-mosaic-component + React 19: RESOLVED, no fork/override needed.** Latest **stable** `react-mosaic-component@6.2.0` (published 2026-04-16) declares peer `react: ">=16"`, which React 19 satisfies. Its drag backbone `react-dnd@16.0.1` requires `react >= 16.14` — also satisfied. **Use 6.2.0 stable. Do NOT chase `7.0.0-beta0`** (the npm `latest` tag points at a beta; the newer-dated stable is 6.2.0). No peer-dep override, no fork. Confidence: HIGH.
2. **Tailwind v4 uses the `@tailwindcss/vite` plugin, not PostCSS, and has NO `tailwind.config.ts`.** v4 is CSS-first config (`@import "tailwindcss"` + `@theme {}` in CSS). The spec's `ui/tailwind.config.ts` (repo tree §4.1) is the **v3 pattern and should be dropped**. Confidence: HIGH (official docs).
3. **`@xterm/*` scoped packages are correct; legacy `xterm`/`xterm-addon-*` are deprecated.** npm marks `xterm@5.3.0` as "now deprecated. Move to @xterm/xterm instead." Confidence: HIGH.
4. **WS proxy: keep FastAPI/Starlette native WebSocket for the *browser* side, and the `websockets` library for the *upstream ttyd* side.** FastAPI only gives you the server endpoint; it has no WS *client*, so you need a client lib to dial ttyd. `uvicorn[standard]` already pulls `websockets`, so it adds no new top-level dependency. **Do NOT** reach for `aiohttp` or `socket.io`. Confidence: HIGH.
5. **The spec's loose ranges are now a major version behind in several places** (Vite, TypeScript, Biome, Vitest, xterm, mypy). See "Spec-vs-reality deltas." None are blockers; they are pin decisions.

## Recommended Stack

### Backend — Core (`api/`, Python 3.12)

| Technology | Version (pin) | Purpose | Why Recommended |
|------------|---------------|---------|-----------------|
| Python | 3.12.x | Runtime | Fixed by spec; 3.12 is current stable-LTS-grade, broad lib support. (3.13 exists but spec says 3.12; stay on spec.) |
| FastAPI | 0.136.3 | HTTP + native WebSocket framework | Spec mandate. Native `@router.websocket` for the browser side; Pydantic v2 integration; ASGI. |
| uvicorn[standard] | 0.49.0 | ASGI server | Spec mandate (systemd `ExecStart`). `[standard]` extra bundles `websockets>=10.4`, `httptools`, `uvloop`, `watchfiles`. |
| pydantic | 2.13.4 | Models / envelope shaping | snake_case DB → camelCase JSON via `alias`/`populate_by_name` (CLAUDE.md convention). |
| pydantic-settings | 2.14.1 | Env config (`api/config.py`) | Spec mandate; reads `.env` per §10.3. |
| proxmoxer | 2.3.0 | Proxmox API client | Spec mandate (`ProxmoxService`). v2.x is the current line; pairs with `requests` (HTTPS backend). |
| websockets | 16.0 | Upstream WS **client** to ttyd | The WS proxy's upstream leg (`§6.4`). Already transitively present via `uvicorn[standard]`. Pin it explicitly as a direct dep since code imports it. |
| aiosqlite | 0.22.1 | Async SQLite driver (`DbProvider`) | Spec mandate / ADR-0001. v1 store behind the provider seam. |
| httpx | 0.28.1 | Async HTTP (ttyd health poll) **and** ASGI test transport | Used in `_waitForTtyd` (§6.2) and integration tests (`httpx.ASGITransport`, ci-cd §4.3). |

### Backend — Dev / Test / Lint

| Tool | Version (pin) | Purpose | Notes |
|------|---------------|---------|-------|
| uv | 0.11.19 | Package + venv manager, lockfile | Spec mandate. `uv sync --frozen` in Dockerfile; `uv lock --check` is a CI gate (ci-cd §4.1). |
| ruff | 0.15.16 | Lint + format | Spec mandate. `ruff check` + `ruff format --check` are Tier-0 gates. |
| mypy | **2.1.0** | Strict type-check | Spec mandate (strict). **NOTE: mypy is now 2.x** — major bump from the 1.x era. Pin exactly and enable per-rule config; do not float. |
| pytest | 9.0.3 | Test runner | Spec mandate. Config in `api/pyproject.toml` (ci-cd §8). |
| pytest-asyncio | 1.4.0 | Async test support | Required for async services / WS proxy / `aiosqlite` tests. Set `asyncio_mode = "auto"`. |
| respx | 0.23.1 | Mock httpx (Proxmox HTTP + ttyd health) | Spec mandate (ci-cd §4.3). Use **respx** since the code path is httpx-based; prefer it over `responses`. |
| responses | 0.26.1 | Mock `requests` (proxmoxer's transport) | Use **only** where proxmoxer's underlying `requests` calls need mocking and respx can't reach them. Otherwise respx covers httpx. |
| playwright (Python) | 1.60.0 | e2e driver (Tier 3) | Pin to the **same** version as the JS `@playwright/test` (both 1.60.0) so the browser binaries match. Pick one language for specs — see "What NOT to use." |
| pip-audit | 2.10.0 | Dependency CVE audit | ci-cd §5.1 required job. |
| asyncpg | 0.31.0 | Postgres driver (**stub only**) | Hosted path (`postgresProvider.py`). NOT installed in v1 runtime image; behind the seam. Listed for completeness. |

### Frontend — Core (`ui/`)

| Technology | Version (pin) | Purpose | Why Recommended |
|------------|---------------|---------|-----------------|
| Vite | **8.0.16** | Build tool / dev server | Spec says `^6`; current stable is **8**. Recommend Vite 8 (Rolldown-era). If risk-averse, Vite 6.4.3 is still on the `previous` tag — but the plugin ecosystem (below) has moved to v8. Decide at scaffold. |
| React | 19.2.7 | UI framework | Spec mandate. |
| react-dom | 19.2.7 | DOM renderer | Must match React exactly. |
| TypeScript | **6.0.3** | Types | Spec says `^5`; current stable is **6**. Recommend TS 6; if a dep lags, TS 5.9.x is the fallback. |
| @vitejs/plugin-react | 6.0.2 | React Fast Refresh / JSX | **Peer `vite: ^8.0.0`** — this is why Vite 8 is the coherent choice. On Vite 6 you must hold this plugin at its v4 line. |
| @xterm/xterm | **6.0.0** | Terminal emulator | Scoped package. Spec says `^5.x`; current is **6**. API is stable across 5→6 for this use; pin 6. |
| @xterm/addon-fit | **0.11.0** | Fit terminal to container | Spec says `^0.10.x`; current is **0.11.0**. |
| @xterm/addon-web-links | **0.12.0** | Clickable URLs in terminal | Spec says `^0.11.x`; current is **0.12.0**. |
| react-mosaic-component | **6.2.0** | Tiling/split/drag panel manager | **Stable**, React-19-compatible (`peer react >=16`). See headline #1. Pin `6.2.0`, NOT `7.0.0-beta0`. |
| @tanstack/react-query | 5.101.0 | Server-state (workspace polling, mutations) | Spec mandate. Peer `react: ^18 || ^19` — React 19 OK. |
| zustand | 5.0.14 | Client state (Mosaic tree, active workspace) | Spec mandate. Peer `react: >=18` — React 19 OK. |
| tailwindcss | **4.3.0** | Styling | Spec mandate (`^4`). **v4 = CSS-first config, no JS config file.** |
| @tailwindcss/vite | **4.3.0** | Tailwind's Vite integration | **Required for v4 + Vite** (replaces PostCSS plugin). Peer `vite: ^5.2 \|\| ^6 \|\| ^7 \|\| ^8` — works on both Vite 6 and 8. |

### Frontend — Dev / Test / Lint

| Tool | Version (pin) | Purpose | Notes |
|------|---------------|---------|-------|
| @biomejs/biome | **2.4.16** | Lint + format (replaces ESLint+Prettier) | Spec says `^1.x`; current is **2.x**. Biome 2 is the current line; **pin 2.4.16**. `biome.json` schema differs from 1.x — write it fresh, don't port a 1.x config. |
| vitest | **4.1.8** | Unit/integration test runner | Spec implies Vitest; current is **4.x**. Pairs with Vite 8. Config in `ui/vitest.config.ts`. |
| @testing-library/react | 16.3.2 | Component testing | Peer supports React 19 (`react ^18 || ^19`). |
| @testing-library/jest-dom | 6.9.1 | DOM matchers | Standard companion. |
| msw | 2.14.6 | API mocking (Tier-2 UI integration) | ci-cd §4.3. v2 is the current line (`http`/`HttpResponse` API), not legacy `rest`. |
| @playwright/test | 1.60.0 | e2e (Tier 3) | Drives the full-stack compose. Keep version-locked with the Python playwright if both are present. |

### Worker LXC tooling (golden template — lives in `cc-worker-config`)

| Technology | Version (pin) | Purpose | Why Recommended |
|------------|---------------|---------|-----------------|
| Ubuntu | 24.04 LTS | Worker base OS | Spec mandate (CT template `ubuntu-24.04-standard`). Supported to 2029. |
| Node.js | 22.x (LTS "Jod") | Runtime for Claude Code | Spec mandate. **22 is Active LTS until 2027-04-30** (verified vs nodejs Release schedule). Sound choice; Node 24 is the newer LTS but 22 is the safe pin and what the spec targets. |
| @anthropic-ai/claude-code | 2.1.170 (track latest at provision) | The agent CLI | Engines `node >=18` (Node 22 fine). Installed `-g` at provision; this is the product's whole point — pin at provision time, refresh on reprovision. |
| ttyd | distro package (Ubuntu 24.04 `apt`) | Terminal-over-HTTP/WS server in worker | Spec mandate. Binds `:7681` on `lo`; the control plane's WS proxy bridges to it. |

## Installation

### Backend (`api/`, via uv)

```bash
# Runtime deps (uv add → pyproject + uv.lock)
uv add "fastapi==0.136.3" "uvicorn[standard]==0.49.0" \
       "pydantic==2.13.4" "pydantic-settings==2.14.1" \
       "proxmoxer==2.3.0" "websockets==16.0" \
       "aiosqlite==0.22.1" "httpx==0.28.1"

# Dev / test / lint
uv add --dev "ruff==0.15.16" "mypy==2.1.0" \
       "pytest==9.0.3" "pytest-asyncio==1.4.0" \
       "respx==0.23.1" "responses==0.26.1" \
       "playwright==1.60.0" "pip-audit==2.10.0"
# asyncpg is hosted-path only — do NOT add to v1 runtime.
```

### Frontend (`ui/`)

```bash
# Runtime
npm install react@19.2.7 react-dom@19.2.7 \
  @xterm/xterm@6.0.0 @xterm/addon-fit@0.11.0 @xterm/addon-web-links@0.12.0 \
  react-mosaic-component@6.2.0 \
  @tanstack/react-query@5.101.0 zustand@5.0.14

# Build + styling (Tailwind v4 = plugin, not PostCSS)
npm install -D vite@8.0.16 @vitejs/plugin-react@6.0.2 typescript@6.0.3 \
  tailwindcss@4.3.0 @tailwindcss/vite@4.3.0 \
  @biomejs/biome@2.4.16

# Test
npm install -D vitest@4.1.8 \
  @testing-library/react@16.3.2 @testing-library/jest-dom@6.9.1 \
  msw@2.14.6 @playwright/test@1.60.0
```

### Tailwind v4 wiring (replaces the spec's `tailwind.config.ts`)

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

```css
/* src/index.css — v4 CSS-first config */
@import "tailwindcss";

@theme {
  /* design-system tokens from design/ go here, NOT in a JS config */
}
```

## Spec-vs-reality deltas (flag for roadmap)

The spec's `^x` ranges were written against an earlier snapshot. Current stable has moved on. None block the build; each is a pin decision to make at scaffold:

| Item | Spec says | Current stable (2026-06-09) | Action |
|------|-----------|------------------------------|--------|
| Vite | `^6.x` | **8.0.16** | Recommend Vite 8 (plugins moved to it). Spec range is satisfiable at 6.4.3 only if you also hold `@vitejs/plugin-react` at v4. |
| TypeScript | `^5.x` | **6.0.3** | Recommend TS 6; fall back to 5.9.x only if a dep breaks. |
| @biomejs/biome | `^1.x` | **2.4.16** | Use Biome 2. **Config schema changed** — write `biome.json` fresh. |
| @xterm/xterm | `^5.x` | **6.0.0** | Use 6. Addons: fit `0.11.0`, web-links `0.12.0` (spec said 0.10/0.11). |
| react-mosaic-component | `^7.x` | stable is **6.2.0** (7 is `beta0`) | **Use 6.2.0 stable.** Spec's `^7` would pull a beta — override the spec here. |
| mypy | (implied 1.x era) | **2.1.0** | Pin mypy 2.x explicitly; strict config keys may differ from 1.x. |
| Vitest | (implied) | **4.1.8** | Use Vitest 4 (matches Vite 8). |
| Tailwind config file | `ui/tailwind.config.ts` in tree | v4 has **no JS config** | Drop `tailwind.config.ts`; use `@tailwindcss/vite` + CSS `@theme`. |
| WS proxy imports (§6.4) | `import websockets; websockets.connect(...)`; `websockets.ConnectionClosed` | new asyncio API | Use `from websockets.asyncio.client import connect` and `from websockets.exceptions import ConnectionClosed`. `import websockets` still works but the legacy attribute paths are deprecated. |

## WebSocket proxy: library decision (explicit)

The terminal proxy has **two legs**, and they use **different** mechanisms — this is the right design, keep it:

- **Browser ↔ control plane (downstream): FastAPI/Starlette native WebSocket.** `@router.websocket(...)`, `await ws.accept()`, `ws.iter_bytes()`, `ws.send_bytes()`. No extra library. This is the server side and FastAPI does it natively.
- **Control plane ↔ ttyd (upstream): the `websockets` library client.** FastAPI/Starlette ships **no WebSocket client**, so dialing `ws://{lxcIp}:7681/ws` needs `websockets.asyncio.client.connect`. It is already in the dependency tree via `uvicorn[standard]`, so this adds **zero** new top-level runtime deps once pinned.

**Do NOT** introduce `aiohttp` (second HTTP stack alongside httpx — redundant), `python-socketio`/`socket.io` (ttyd speaks raw WebSocket, not Socket.IO), or `wsproto` directly (lower-level than needed). One small correctness note for the spec code: ttyd uses a `tty`/`stdout` **subprotocol** and base64/byte framing depending on flags — when bridging, forward frames verbatim and set the WS subprotocol ttyd expects rather than assuming plain bytes.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| react-mosaic-component 6.2.0 | react-mosaic-component 7.0.0-beta0 | Only if a 6.2.0 bug forces it; 7 is beta (uuid 11, rdndmb 9) — wait for `7.0.0` stable. |
| Vite 8 | Vite 6.4.3 (`previous` tag) | If a critical plugin you need has no Vite 8 build. Then also hold `@vitejs/plugin-react`@4 and `vitest`@2/3. |
| TypeScript 6 | TypeScript 5.9.x | If a `@types/*` or tool lags TS 6. |
| `websockets` (client) | `httpx-ws` 0.9.0 | If you want one library for both WS and HTTP; `httpx-ws` rides on httpx. Adds a dep `websockets` doesn't. Stick with `websockets` (already present). |
| respx | responses 0.26.1 | When mocking proxmoxer's underlying `requests` calls that respx (httpx-only) can't intercept. |
| Biome 2 | ESLint + Prettier | Never for this repo — spec mandates Biome; Biome 2 covers lint+format in one tool. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `xterm`, `xterm-addon-fit`, `xterm-addon-web-links` (unscoped) | npm-deprecated: "Move to @xterm/xterm instead." | `@xterm/xterm`, `@xterm/addon-fit`, `@xterm/addon-web-links` |
| `react-mosaic-component@^7` / `7.0.0-beta0` | Pre-release; npm `latest` tag is misleading (stable 6.2.0 is newer-dated) | `react-mosaic-component@6.2.0` (stable, React-19 peer) |
| `tailwind.config.ts` + `postcss.config.js` + `autoprefixer` | v3 pattern; not how Tailwind v4 + Vite works | `@tailwindcss/vite` plugin + CSS `@import "tailwindcss"` + `@theme {}` |
| `websockets.legacy.client` / `websockets.client` legacy attrs | Deprecated in websockets 14+ | `from websockets.asyncio.client import connect` |
| `aiohttp` / `requests` (as a 2nd async HTTP stack) | Duplicates httpx already in use | `httpx` (async) for app, `requests` only as proxmoxer's transport |
| `python-socketio` / `socket.io-client` | ttyd is raw WebSocket, not Socket.IO | native FastAPI WS + `websockets` client |
| ESLint + Prettier | Two tools, slower, not the mandated stack | `@biomejs/biome` v2 |
| Postgres / `asyncpg` in the v1 runtime image | Hosted-path scope; ADR-0001 keeps v1 on SQLite | `aiosqlite` behind `DbProvider`; `asyncpg` only as the stubbed seam |
| `xterm-addon-attach` for the WS wiring | Couples xterm directly to a socket; the spec wants custom reconnect/overlay control | Hand-rolled WS in `useTerminal.ts` writing to `term.write()` |

## Version Compatibility (verified)

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| react-mosaic-component@6.2.0 | react@19.2.7 | peer `react: ">=16"` ✓; drag dep `react-dnd@16` needs `react >= 16.14` ✓. No override. |
| @vitejs/plugin-react@6.0.2 | vite@8.0.16 | peer `vite: "^8.0.0"` ✓. (Forces Vite 8 if you want plugin v6.) |
| @tailwindcss/vite@4.3.0 | vite@6 **and** vite@8 | peer `vite: "^5.2 \|\| ^6 \|\| ^7 \|\| ^8"` ✓ — Tailwind doesn't force the Vite major. |
| @tanstack/react-query@5.101.0 | react@19.2.7 | peer `react: "^18 \|\| ^19"` ✓. |
| zustand@5.0.14 | react@19.2.7 | peer `react: ">=18"` ✓. |
| @testing-library/react@16.3.2 | react@19.2.7 | peer `react: "^18 \|\| ^19"` ✓. |
| uvicorn[standard]@0.49.0 | websockets@16.0 | `[standard]` requires `websockets>=10.4`; 16.0 satisfies — same lib server + upstream-client. |
| websockets@16.0 | Python 3.12 | `requires_python >=3.10` ✓. |
| @anthropic-ai/claude-code@2.x | Node 22 LTS | engines `node >=18` ✓. |
| playwright(py)@1.60.0 | @playwright/test@1.60.0 | Keep equal so browser binaries match if both languages are present. |

## Stack Patterns by Variant

**If you want maximum currency (recommended):**
- Vite 8 + TS 6 + Vitest 4 + `@vitejs/plugin-react`@6 + Biome 2 + xterm 6.
- Because the plugin/test ecosystem has already moved here; staying current avoids a forced migration in a phase or two.

**If a dependency forces conservatism:**
- Drop to Vite 6.4.3 (`previous` tag) + `@vitejs/plugin-react`@4 + Vitest 2/3 + TS 5.9.
- Because `@tailwindcss/vite` and `react-mosaic-component` both still work on Vite 6 — only the React/test plugins pin you to a Vite major.
- This is the literal reading of the spec's `^6`/`^5` ranges; choose it only with a concrete blocker.

## Open pins to confirm at scaffold (surface, don't silently pick)

1. **Vite 6 vs 8 / TS 5 vs 6:** Spec text says 6/5; reality is 8/6. Recommend 8/6 but this is a deliberate spec deviation — log an ADR if you take it (CLAUDE.md: deviations need an ADR).
2. **react-mosaic 6.2.0 over spec's `^7`:** Stable beats the spec's range; trivial to justify, but note it.
3. **Tailwind config file removal:** Deleting the planned `ui/tailwind.config.ts` from the §4.1 tree is a (minor) spec deviation driven by v4.
4. **Playwright language:** Pick **one** of Python `playwright` or JS `@playwright/test` for e2e specs to avoid double browser-binary management; ci-cd §8 places specs under `ui/tests/e2e/` (JS-leaning). Recommend `@playwright/test`.

## Sources

- npm registry via `npm view <pkg> version|dist-tags|peerDependencies|time` (2026-06-09) — react 19.2.7, react-dom 19.2.7, react-mosaic-component 6.2.0/7.0.0-beta0 (peer `react >=16`), vite 8.0.16 (prev 6.4.3), typescript 6.0.3, tailwindcss 4.3.0, @tailwindcss/vite 4.3.0 (peer vite ^5.2||^6||^7||^8), @xterm/xterm 6.0.0, @xterm/addon-fit 0.11.0, @xterm/addon-web-links 0.12.0, @tanstack/react-query 5.101.0, zustand 5.0.14, @biomejs/biome 2.4.16, vitest 4.1.8, @vitejs/plugin-react 6.0.2 (peer vite ^8), @testing-library/react 16.3.2, msw 2.14.6, @playwright/test 1.60.0, @anthropic-ai/claude-code 2.1.170 (engines node >=18), react-dnd@16.0.1 (peer react >=16.14). HIGH.
- npm deprecation flag: `xterm@5.3.0` "now deprecated. Move to @xterm/xterm instead." HIGH.
- PyPI JSON API (`pypi.org/pypi/<pkg>/json`, 2026-06-09) — fastapi 0.136.3, uvicorn 0.49.0 (`[standard]` → websockets>=10.4), uv 0.11.19, ruff 0.15.16, mypy 2.1.0, proxmoxer 2.3.0, aiosqlite 0.22.1, httpx 0.28.1, pydantic 2.13.4, pydantic-settings 2.14.1, websockets 16.0 (requires_python >=3.10), pytest 9.0.3, pytest-asyncio 1.4.0, respx 0.23.1, responses 0.26.1, playwright 1.60.0, pip-audit 2.10.0, asyncpg 0.31.0, httpx-ws 0.9.0. HIGH.
- tailwindcss.com/docs/installation/using-vite — v4 official setup uses `@tailwindcss/vite` plugin (not PostCSS); CSS-first config, no `tailwind.config.js`. HIGH.
- websockets.readthedocs.io (asyncio client reference) — `websockets.asyncio.client.connect` is the current stable API; `websockets.legacy.*` deprecated. HIGH.
- nodejs Release schedule.json — Node 22 Active LTS, end-of-life 2027-04-30; Node 24 newer LTS. HIGH.

---
*Stack research for: self-hosted Claude Code workspace manager (FastAPI control plane + React tiling terminal UI + Proxmox LXC workers)*
*Researched: 2026-06-09*
