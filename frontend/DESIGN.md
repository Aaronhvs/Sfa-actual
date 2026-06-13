# SFA — Design System

## Color Tokens (CSS variables defined in `src/index.css`)

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#111111` | Main background |
| `--bg-deep` | `#0a0a0a` | Navbar, deep surfaces |
| `--surface` | `#1e1e1e` | Cards, surface elements |
| `--surface2` | `#181818` | Alternate surfaces |
| `--gold` | `#C9A84C` | SFA points, rank, position — ONLY |
| `--gold-light` | `#D4AF55` | Gold hover / emphasis |
| `--text` | `#ffffff` | Primary text — ALWAYS white |
| `--text-dim` | `#aaaaaa` | Secondary text |
| `--text-faint` | `#555555` | Labels, weak text |
| `--border` | `rgba(201,168,76,0.2)` | Gold accent borders |
| `--border-sub` | `rgba(255,255,255,0.06)` | Subtle dividers |

**Forbidden colors:** `#222831`, `#393E46`, `#2e333b`, `#1a2028`, `#DFD0B8`, `#948979`
**Never use pure black `#000000` or pure white substitutes for text — always use the tokens.**

## Typography

| Role | Font | Weight | Style |
|---|---|---|---|
| Display / Numbers | Barlow Condensed | 700–800 | UPPERCASE |
| Body / Labels | Inter | 400 | Normal |
| Technical / Dates / Codes | Space Mono | 400 | Normal |

Fonts loaded via Google Fonts in `index.html`. Use CSS font-family variables, not raw strings.

## Section Titles

Every section title must follow this pattern exactly:
```css
font-family: 'Barlow Condensed', sans-serif;
font-size: 11px;
font-weight: 600;
letter-spacing: 0.15em;
text-transform: uppercase;
color: #aaaaaa;
border-left: 2px solid #C9A84C;
padding-left: 8px;
```

## Layout

- Max content width: `1200px`, centered
- Desktop padding: `48px` lateral
- Mobile padding: `24px` lateral
- Navbar: fixed top, `background: #0a0a0a`

## Component Patterns

### Ranking Table Row
- Background: `#111111`
- Hover: `#1e1e1e`
- Rank number: `#ffffff`, Barlow Condensed 700
- Player name: `#ffffff`
- Club: `#aaaaaa`
- SFA Points: `#C9A84C`, Barlow Condensed 700

### Top-3 Showcase Cards (Hero)
- Full player photo with dark gradient overlay at bottom
- Name: `#ffffff` uppercase Barlow Condensed
- "SFA RANK" label: Space Mono small, gold
- SFA Score: gold, large, Barlow Condensed
- Rank as watermark: gold, very low opacity, large

### Player Profile Header
- Background: `#0a0a0a`
- Circular photo with subtle gold border
- Name: `#ffffff` Barlow Condensed 700 UPPERCASE
- SFA Score badge: background `#C9A84C`, text `#000000`

### Quick Stats Bar
- Background: `#111111`
- Numbers: `#ffffff`, Barlow Condensed 700
- SFA Total: `#C9A84C`
- Labels: `#555555`

### Action/Event Cards
- Background: `#1e1e1e`
- Border: `rgba(255,255,255,0.06)`
- Action name: `#ffffff`
- Points: `#C9A84C`

### Fixture Rows
- Background: `#111111`
- Hover: `#1e1e1e`
- Separator: `rgba(255,255,255,0.06)`
- Match name: `#ffffff`
- Meta (date, competition): `#555555`
- Points: `#C9A84C`

## Elevation & Borders

- Border-radius: **4–6px maximum**. No pill shapes, no large roundings.
- Cards don't use heavy shadows. Use `--border-sub` (`rgba(255,255,255,0.06)`) borders to separate surfaces.
- Gold borders (`--border`) reserved for focus states or intentional accent.

## Motion

The project currently uses CSS transitions only (no animation libraries). When adding motion:
- Use `transform` and `opacity` exclusively — never animate `top`, `left`, `width`, `height`.
- Timing: `200–300ms` for micro-interactions, `cubic-bezier(0.16, 1, 0.3, 1)` preferred.
- Hover: `background-color` transition on rows, subtle `transform: translateX` or `scale(0.98)` on active states.
- No infinite loops or perpetual animations — this is a data product, not a marketing page.

## Icons

No icon library currently installed. Use SVG inline or `<img>` for logos. If adding icons, use Phosphor or Radix — never Lucide or emoji.
