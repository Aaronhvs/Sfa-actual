# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev       # Start dev server on port 5173 (proxies /api/* → localhost:8000)
npm run build     # TypeScript type-check + Vite production build
npm run preview   # Serve the production build locally
```

No lint or test scripts are configured.

## Architecture

**Stack:** React 18 + TypeScript 5 (strict) + React Router v6 + Vite 5. No CSS framework — pure CSS with custom design tokens. No global state management; each page owns its local state.

### Routing (`src/App.tsx`)

```
/            → redirect to /ranking
/ranking     → RankingPage
/player/:id  → PlayerPage
/teams       → TeamsPage (coming soon placeholder)
/compare     → ComparePage (coming soon placeholder)
```

### API layer (`src/api/client.ts`)

Single `fetch`-based client. All calls go to `/api/v1`, which Vite proxies to `http://localhost:8000` in dev. Four typed exports:

- `fetchRanking({ season, position, competition_id, limit })`
- `fetchPlayer(id, season?)`
- `fetchPlayerEvents(id, season?)`
- `fetchPlayerFixtures(id, season?)`

All TypeScript interfaces live in `src/types/index.ts`.

### Data fetching pattern

Pages call the API directly in `useEffect` with `useState` for loading/error states — no SWR, React Query, or caching. `RankingPage` uses `Promise.allSettled` to load the top-3 player details in parallel alongside the ranking list. `PlayerPage` uses `Promise.all` for player detail, events, and fixtures simultaneously.

The season is currently hardcoded as `'2024'` in both `RankingPage` and `PlayerPage`.

### Component organization

```
src/components/
  layout/      # Navbar (fixed top)
  ranking/     # FilterBar, RankingRow, ShowcaseCard
  player/      # PlayerHeader, StatBar, ActionValues, ScoringExplainer, FixtureList, FixtureRow
```

Pages in `src/pages/` are container components that fetch data and pass it down. Components in `src/components/` are purely presentational.

## Design system

All UI must follow `BRAND.md`. Key rules:

- **Dark-only** — background `#111111`, deep surfaces `#0a0a0a`, cards `#1e1e1e`
- **Text** — always `#ffffff` (primary), `#aaaaaa` (secondary), `#555555` (labels/faint)
- **Gold `#C9A84C`** — reserved exclusively for SFA points, rankings, and position numbers. Not for decorative use.
- **Forbidden colors** — never use `#222831`, `#393E46`, `#2e333b`, `#1a2028`, `#DFD0B8`, `#948979`
- **Typography** — Barlow Condensed UPPERCASE 700–800 for titles/numbers, Space Mono for technical labels/dates, Barlow Condensed 400 for body text
- **Borders** — max `4–6px` border-radius; no large rounded corners
- **No emojis** in the UI
- Section titles: Barlow Condensed uppercase, 11–12px, `letter-spacing: 0.15em`, color `#aaaaaa`, with `border-left: 2px solid #C9A84C; padding-left: 8px`

CSS variables are defined in `:root` in `src/index.css`. Always use the variables (e.g., `var(--gold)`) rather than hardcoding hex values in component CSS.

## Language

All UI text and code comments are in Spanish.

---

## Skills installed

The following skills are active. Use them proactively — they are not optional extras, they are the development standard for this project.

### Cuándo invocar cada skill

| Situación | Skill |
|---|---|
| Página nueva o rediseño grande | `/high-end-visual-design` primero, luego `/impeccable craft` |
| Componente nuevo | `/impeccable craft [componente]` |
| Revisar si algo se ve bien | `/impeccable critique [página]` |
| Pulir animaciones / transitions | `/emil-design-eng` |
| Duda de colores, tipografía, marca | `/brand` |
| UX, accesibilidad, responsive | `/ui-ux-pro-max` |
| Ejecutar fixes de un spec de diseño | Leer `specs/NNNN-*.md` y ejecutar en orden |

### Skills disponibles

**En `.agents/skills/` (instaladas por taste-skill):**

| Skill | Para qué |
|---|---|
| `design-taste-frontend` | Anti-slop baseline — activo en todo trabajo de UI |
| `redesign-existing-projects` | Audit + rediseño de UI existente (protocolo de 7 pasos) |
| `high-end-visual-design` | Diseño nivel agencia, Double-Bezel, hover physics |
| `stitch-design-taste` | Variante de taste orientada a composición de bloques |
| `gpt-taste` | Taste alternativo con sesgo hacia layouts experimentales |
| `industrial-brutalist-ui` | Estilo industrial/brutalista |
| `minimalist-ui` | UI minimalista, whitespace agresivo |
| `image-to-code` | Convierte screenshot o mockup a código |
| `brandkit` | Extrae y aplica sistema de marca existente |
| `full-output-enforcement` | Fuerza código completo sin truncar (útil para Codex) |

**En `.claude/skills/` (registradas como skill):**

| Skill | Para qué |
|---|---|
| `ui-ux-pro-max` | Accesibilidad, UX, responsive, 161 paletas, 57 font pairings |
| `emil-design-eng` | Animaciones al estilo Emil Kowalski — easing, stagger, physics |
| `brand` | Consistencia de marca, tokens, copy voice |
| `design` | Logos, slides, iconos, identidad corporativa |

---

## Prompt estándar para pedir cambios con Codex

Usar este formato cada vez que se quiera ejecutar un spec o cambio de diseño:

```
Lee CLAUDE.md y ejecuta el plan en specs/NNNN-nombre.md.

Reglas:
- Sigue el checklist en orden, marca cada ítem al completarlo
- No reescribas componentes completos — cambios quirúrgicos
- Usa solo pure CSS (sin Tailwind), variables var(--token)
- No instales dependencias nuevas sin verificar package.json primero
- Al terminar: npm run build debe pasar sin errores de tipo
```

Para un cambio de diseño sin spec previo:

```
Lee CLAUDE.md (especialmente la sección de Skills y Design system).
Tarea: [descripción del cambio]
Página/componente: [archivo]
Aplica las guías de /design-taste-frontend con los dials del proyecto (VARIANCE=6, MOTION=4, DENSITY=7).
Restricciones: pure CSS, var(--token), sin librerías nuevas, sin emojis, sin em-dashes.
```

### `/impeccable` — production-grade UI design (23 commands)

The primary design skill. Covers UX review, visual hierarchy, accessibility, performance, responsive behavior, theming, anti-patterns, and motion.

**Required setup** — before first use, run the context loader:
```bash
node .agents/skills/impeccable/scripts/load-context.mjs
```
This reads `PRODUCT.md` and `DESIGN.md` (both exist at project root). Without this step, impeccable generates generic output that ignores the project.

Key commands:
- `/impeccable craft [feature]` — shape + build a feature end-to-end
- `/impeccable critique [page]` — UX heuristic review with scoring
- `/impeccable audit [component]` — a11y, performance, responsive checks
- `/impeccable polish [target]` — final quality pass before shipping
- `/impeccable animate [target]` — purposeful motion design

### `/design-taste-frontend` — anti-slop frontend baseline

**Active dial settings for SFA** (override the skill's defaults):
- `DESIGN_VARIANCE: 6` — offset layouts, not full asymmetric chaos (data app)
- `MOTION_INTENSITY: 4` — fluid CSS transitions only, no Framer Motion (not installed)
- `VISUAL_DENSITY: 7` — compact data rows, data breathes without cards

**Critical project-specific overrides** (these override taste-skill defaults):
- **Fonts:** Barlow Condensed + Inter + Space Mono are the brand fonts. The taste-skill ban on "Inter" does NOT apply here — Inter is the official body font.
- **CSS:** This project uses **pure CSS**, not Tailwind. Translate all Tailwind directives to CSS equivalents using the existing `var(--token)` system.
- **Colors:** Use SFA tokens (`var(--bg)`, `var(--gold)`, etc.) — not Zinc/Slate/generic neutrals.
- **Animations:** No Framer Motion or GSAP in this project. Use CSS `transition` and `@keyframes` only.
- **h-screen rule** still applies: always use `min-height: 100dvh` instead of `height: 100vh`.

What the skill enforces that does apply:
- No 3-column equal-card layouts — use table rows or asymmetric grids
- No neon outer glows — use inner borders or subtle tinted shadows
- No generic placeholder names or fake numbers — use real-looking football data
- Full interaction cycles: loading skeletons, empty states, error states
- Staggered entry animations on lists with `animation-delay`

### `/high-end-visual-design` — agency-level UI

Use when building a new page or doing a major visual overhaul. Enforces the "Double-Bezel" nested card architecture, magnetic button hover physics, and scroll-triggered entry animations. Translate all Tailwind to pure CSS as above.

### `/brand` — brand consistency

Use when adding new UI patterns, reviewing copy, or updating the design token system. Run `node .claude/skills/brand/scripts/inject-brand-context.cjs` to extract brand context before making brand decisions.

### `/ui-ux-pro-max` — UX intelligence

Use for accessibility review, responsive layout decisions, and UX pattern validation. Run the search script for detailed guidance:
```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "sports ranking dark dashboard" --design-system
```

### `/emil-design-eng` — animation & polish (Emil Kowalski)

Use when reviewing or writing animations, deciding on easing curves, adding interaction feedback, or doing a final polish pass on transitions. Encodes Emil Kowalski's design engineering philosophy (creator of Sonner and Vaul).

Key principles enforced:
- Custom easing curves over built-in CSS easings (`cubic-bezier(0.23, 1, 0.32, 1)` not `ease-out`)
- Never `scale(0)` — start from `scale(0.95) + opacity: 0`
- Buttons always have `scale(0.97)` on `:active`
- UI animations under 300ms; keyboard actions never animate
- Stagger delays 30-80ms between list items
- Only animate `transform` and `opacity` (GPU-accelerated)
