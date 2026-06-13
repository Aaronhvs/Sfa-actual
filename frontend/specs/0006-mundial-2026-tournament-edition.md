# Spec 0006 — SFA Global Tournament Edition

## Skills activos para este spec

| Componente | Skills |
|---|---|
| Tokens / Variables CSS | `brand` + `design-taste-frontend` (COLOR_CONSISTENCY_LOCK — un acento dominante por modo) |
| `WorldCupHeader.tsx` (nuevo) | `high-end-visual-design` (Double-Bezel, eyebrow pill), `emit-design-eng` (entry animation) |
| `SeasonDropdown.tsx` / `SeasonSelector.tsx` | `emit-design-eng` (track slide, scale on active), `ui-ux-pro-max` (keyboard nav ARIA) |
| `RankingRow` / `RankingCard` / `ShowcaseCard` | `emit-design-eng` (touch target, scale active), `design-taste-frontend` (no 3 cols iguales) |
| `RankingPage.tsx` | `design-taste-frontend` (layout asimétrico para WC), `brand` (header contextual) |
| `PlayerPage.tsx` | `ui-ux-pro-max` (contexto cambio temporada), `design-taste-frontend` |
| Todo código | `full-output-enforcement` — código completo, sin `// ...`, sin truncar |

**NO aplican:** `minimalist-ui` (tema claro, incompatible), `brandkit` (generación de imágenes)

---

## Contexto

El Mundial 2026 es un **evento aislado** dentro de SFA. Su ranking empieza desde 0 y no mezcla puntos con los campeonatos de club. Este spec crea:

1. La identidad visual "SFA Global Tournament Edition" — nueva capa de tokens de color que se activan cuando el usuario navega al torneo
2. Los componentes nuevos y modificados que usan esa identidad
3. El soporte técnico de temporada: pasar contexto al perfil del jugador, detectar temporada WC

El spec es **solo frontend**. El backend debe devolver `is_world_cup: true` en el campo correspondiente del endpoint `/api/v1/seasons` antes de que los nuevos componentes tengan efecto visual.

---

## Identidad visual: SFA Global Tournament Edition

### Análisis de referencias

**WC 2026 oficial:** patrón de rectángulos concéntricos en rojo, naranja, amarillo, verde, azul. Muy saturado, festivo, multicultural. No se copia ningún elemento.

**ELNINE:** fondo verde estadio `≈#0A2618`, acento amarillo-chartreuse, indicadores rojo vivo, tipografía condensada bold. Buena referencia de "sports data" nocturno.

**SFA base:** `#111111` fondo, `#C9A84C` gold exclusivo para puntos, Barlow Condensed UPPERCASE.

### Palette "Global Tournament Edition"

La edición torneo **extiende** el sistema SFA — no lo reemplaza. Los tokens base (`--bg`, `--gold`, etc.) quedan intactos. Se añade una capa `--tm-*` que se activa con la clase `.mode-tournament` en el `<body>` o en el contenedor de la página.

```
Tournament Night (fondo):    #0C0C10   →  --tm-bg
Tournament Surface:          #141419   →  --tm-surface
Tournament Surface 2:        #1C1C26   →  --tm-surface2

Tournament Crimson:          #D92B2B   →  --tm-red      (energía competitiva, live, fuego)
Tournament Blue:             #1B4FD8   →  --tm-blue     (continente americano, noche de estadio)
Tournament Green:            #1A7A3C   →  --tm-green    (campo, naturaleza México/Canadá)
Tournament Gold:             #F5A623   →  --tm-gold     (trofeo, campeón — MÁS CÁLIDO que --gold)
Tournament Platinum:         #C8D4E0   →  --tm-platinum (plata, clasificación)

Live indicator:              #E5342C   →  --tm-live
Texto principal:             #FFFFFF   →  --tm-text
Texto secundario:            #8A94A8   →  --tm-text-dim
Borde sutil:                 rgba(255,255,255,0.06) →  --tm-border
Borde activo:                rgba(245,166,35,0.3)   →  --tm-border-gold
```

**El `--gold` SFA (`#C9A84C`) se mantiene para los SFA pts.** `--tm-gold` (`#F5A623`) se usa para contexto visual de torneo (badges, highlights de cabecera).

### Patrón de fondo (no copiar el FIFA concéntrico)

En vez de rectángulos concéntricos, SFA usa **líneas diagonales muy sutiles** como marca de agua:

```css
.tm-pattern-bg {
  background-image: repeating-linear-gradient(
    -45deg,
    transparent,
    transparent 20px,
    rgba(255,255,255,0.012) 20px,
    rgba(255,255,255,0.012) 21px
  );
}
```

Y para el header del torneo, un **gradient de 3 franjas** referenciando los 3 países sede:

```css
/* USA (rojo) — Canadá (rojo también, but más oscuro) — México (verde) */
.tm-header-gradient {
  background: linear-gradient(
    90deg,
    rgba(217,43,43,0.15) 0%,
    rgba(27,79,216,0.15) 40%,
    rgba(26,122,60,0.15) 100%
  );
}
```

### Tipografía torneo

Mismas fuentes del proyecto, diferentes pesos:

- Números de ranking: Barlow Condensed 900, 80–120px, gold
- Label "Mundial 2026": Barlow Condensed 700 UPPERCASE, letter-spacing 0.2em
- País/selección: Space Mono 400, 10px, UPPERCASE, letter-spacing 0.15em
- Puntos: Space Mono 700, color `var(--gold)` (SFA gold, no tm-gold)

---

## Requisito backend (prerequisito, no implementado aquí)

`GET /api/v1/seasons` debe devolver `is_world_cup: boolean` por item:

```json
{
  "seasons": [
    { "season": "2026", "is_latest": true, "is_world_cup": true, "label": "Mundial 2026" },
    { "season": "2025", "is_latest": false },
    { "season": "2024", "is_latest": false }
  ]
}
```

Hasta que el backend devuelva esto, el frontend funciona igual que antes. Ningún componente nuevo rompe si `is_world_cup` está ausente.

---

## Restricciones

- Pure CSS — sin Tailwind, sin librerías de animación
- Sin dependencias nuevas
- Todos los nuevos tokens en `:root` de `index.css`
- Sin emojis, sin em-dashes
- `npm run build` debe pasar sin errores TypeScript al terminar

---

## Checklist de implementación

Procesar en orden estricto. Marcar cada ítem al completarlo.

---

### 1. Tipos — `frontend/src/types/index.ts`

- [x] Añadir `is_world_cup?: boolean` y `label?: string` a `SeasonItem`:

```ts
export interface SeasonItem {
  season: string
  is_latest: boolean
  is_world_cup?: boolean   // true para Mundial 2026
  label?: string           // "Mundial 2026" para WC, undefined para temporadas normales
}
```

- [x] Añadir helper de detección (inline en el tipo, sin importar nada):

```ts
// Helper puro — no importa nada de React
export function isWorldCupItem(item: SeasonItem): boolean {
  return item.is_world_cup === true
}
```

---

### 2. Utilidad — `frontend/src/utils/season.ts`

Reemplazar contenido completo:

```ts
import type { SeasonItem } from '../types'

export function seasonLabel(season: string): string {
  if (season === 'all') return 'Total histórico'
  const year = parseInt(season, 10)
  if (isNaN(year)) return season
  const next = (year + 1).toString().slice(-2)
  return `${season}/${next}`
}

export function getSeasonLabel(season: string, items?: SeasonItem[]): string {
  if (items) {
    const item = items.find((i) => i.season === season)
    if (item?.label) return item.label
  }
  return seasonLabel(season)
}

export function isWorldCupSeason(season: string, items?: SeasonItem[]): boolean {
  if (!items) return false
  return items.some((i) => i.season === season && i.is_world_cup === true)
}

// Detecta si la temporada "2025" es la que recibirá puntos del Mundial
// (la inmediatamente anterior a la temporada WC)
export function isSeasonReceivingWcPoints(
  season: string,
  items?: SeasonItem[]
): boolean {
  if (!items) return false
  const wcItem = items.find((i) => i.is_world_cup)
  if (!wcItem) return false
  const wcYear = parseInt(wcItem.season, 10)
  const thisYear = parseInt(season, 10)
  // La temporada de clubes que recibirá los puntos es la que termina el año del WC
  // Ej: WC 2026 → temporada de clubes 2025 (2025/26)
  return thisYear === wcYear - 1
}
```

---

### 3. CSS tokens — `frontend/src/index.css`

En el bloque `:root` existente, añadir al final:

```css
/* ── Tournament Edition tokens ────────────────────────────────── */
--tm-bg:           #0C0C10;
--tm-surface:      #141419;
--tm-surface2:     #1C1C26;
--tm-red:          #D92B2B;
--tm-blue:         #1B4FD8;
--tm-green:        #1A7A3C;
--tm-gold:         #F5A623;
--tm-platinum:     #C8D4E0;
--tm-live:         #E5342C;
--tm-text:         #FFFFFF;
--tm-text-dim:     #8A94A8;
--tm-border:       rgba(255,255,255,0.06);
--tm-border-gold:  rgba(245,166,35,0.3);
--tm-border-red:   rgba(217,43,43,0.3);
--tm-ease:         cubic-bezier(0.23, 1, 0.32, 1);
```

---

### 4. Componente nuevo — `frontend/src/components/shared/WorldCupBanner.tsx`

**Propósito:** banner informativo que aparece cuando el usuario ve la temporada 2025/26 de clubes mientras el Mundial está activo. Informa que los puntos del Mundial se sumarán a esa temporada.

**Design (high-end-visual-design + emit-design-eng):**
- Double-Bezel adaptado a SFA: outer shell con borde gold tenue + inner core con fondo gold muy oscuro
- Entry animation: `translateY(-8px) opacity:0 → translateY(0) opacity:1` en 300ms con `--tm-ease`
- Dismiss con localStorage. No reaparece hasta el próximo día (86400s)
- Sin Framer Motion, sin librerías. Solo CSS transitions.

```tsx
import { useEffect, useState } from 'react'

interface Props {
  onViewWorldCup?: () => void   // callback para cambiar a temporada WC en la página padre
}

const DISMISS_KEY = 'sfa_wc2026_banner_v1'
const DISMISS_TTL = 86_400_000 // 24h en ms

function isDismissed(): boolean {
  try {
    const ts = localStorage.getItem(DISMISS_KEY)
    if (!ts) return false
    return Date.now() - Number(ts) < DISMISS_TTL
  } catch {
    return false
  }
}

export default function WorldCupBanner({ onViewWorldCup }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!isDismissed()) setVisible(true)
  }, [])

  function dismiss() {
    try { localStorage.setItem(DISMISS_KEY, String(Date.now())) } catch {}
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="wc-banner" role="status" aria-live="polite">
      <div className="wc-banner__inner">
        <div className="wc-banner__left">
          <span className="wc-banner__eyebrow">Mundial 2026</span>
          <p className="wc-banner__text">
            Los puntos del torneo se sumarán a esta temporada al finalizar la competición.
          </p>
        </div>
        <div className="wc-banner__actions">
          {onViewWorldCup && (
            <button
              className="wc-banner__cta"
              onClick={onViewWorldCup}
              type="button"
            >
              Ver ranking del Mundial
            </button>
          )}
          <button
            className="wc-banner__dismiss"
            onClick={dismiss}
            type="button"
            aria-label="Cerrar aviso"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
```

**CSS** (añadir al bloque de index.css):

```css
/* ─── WorldCupBanner ──────────────────────────────────────────── */
@keyframes wcBannerIn {
  from { opacity: 0; transform: translateY(-8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.wc-banner {
  /* Double-Bezel outer shell */
  background: rgba(245, 166, 35, 0.04);
  border: 1px solid rgba(245, 166, 35, 0.2);
  border-radius: 4px;
  padding: 2px;
  margin: 0 0 16px;
  animation: wcBannerIn 300ms var(--tm-ease) both;
}

.wc-banner__inner {
  /* Double-Bezel inner core */
  background: rgba(245, 166, 35, 0.05);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
  border-radius: 3px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.wc-banner__left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.wc-banner__eyebrow {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--tm-gold);
}

.wc-banner__text {
  font-family: var(--font-body, 'Inter', sans-serif);
  font-size: 0.8rem;
  color: var(--text-dim);
  margin: 0;
  line-height: 1.4;
}

.wc-banner__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.wc-banner__cta {
  background: rgba(245, 166, 35, 0.12);
  border: 1px solid rgba(245, 166, 35, 0.3);
  border-radius: 3px;
  color: var(--tm-gold);
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 6px 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 150ms var(--tm-ease), transform 100ms var(--tm-ease);
}

.wc-banner__cta:active {
  transform: scale(0.97);
}

@media (hover: hover) and (pointer: fine) {
  .wc-banner__cta:hover {
    background: rgba(245, 166, 35, 0.2);
  }
}

.wc-banner__dismiss {
  background: transparent;
  border: 0;
  color: var(--text-faint, #555);
  cursor: pointer;
  padding: 4px;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 150ms ease, transform 100ms ease-out;
}

.wc-banner__dismiss:active { transform: scale(0.92); }

@media (hover: hover) and (pointer: fine) {
  .wc-banner__dismiss:hover { color: var(--text-dim); }
}
```

---

### 5. Componente nuevo — `frontend/src/components/shared/WorldCupPageHeader.tsx`

**Propósito:** cabecera especial que reemplaza al `rp-header` cuando el usuario está en la vista de Mundial. Identidad visual "Tournament Edition" con patrón de franjas, eyebrow, y el nombre del torneo en grande.

```tsx
interface Props {
  totalPlayers: number
}

export default function WorldCupPageHeader({ totalPlayers }: Props) {
  return (
    <header className="wc-page-header">
      <div className="wc-page-header__pattern" aria-hidden="true" />
      <div className="wc-page-header__gradient" aria-hidden="true" />
      <div className="wc-page-header__content">
        <span className="wc-page-header__eyebrow">SFA · Edición Global</span>
        <h1 className="wc-page-header__title">
          <span className="wc-page-header__title-main">Mundial</span>
          <span className="wc-page-header__title-year">2026</span>
        </h1>
        <p className="wc-page-header__subtitle">
          Clasificación SFA · {totalPlayers.toLocaleString('es-ES')} jugadores
        </p>
      </div>
    </header>
  )
}
```

**CSS:**

```css
/* ─── WorldCupPageHeader ─────────────────────────────────────── */
.wc-page-header {
  position: relative;
  overflow: hidden;
  background: var(--tm-bg);
  border-bottom: 1px solid var(--tm-border);
  padding: 48px 48px 40px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Patrón diagonal SFA — no copia el concéntrico FIFA */
.wc-page-header__pattern {
  position: absolute;
  inset: 0;
  background-image: repeating-linear-gradient(
    -45deg,
    transparent,
    transparent 20px,
    rgba(255,255,255,0.012) 20px,
    rgba(255,255,255,0.012) 21px
  );
  pointer-events: none;
}

/* Gradient de 3 franjas: rojo (USA) / azul (nocturno) / verde (México) */
.wc-page-header__gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    105deg,
    rgba(217,43,43,0.12) 0%,
    rgba(27,79,216,0.10) 45%,
    rgba(26,122,60,0.12) 100%
  );
  pointer-events: none;
}

.wc-page-header__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wc-page-header__eyebrow {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  color: var(--tm-gold);
}

.wc-page-header__title {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin: 0;
  line-height: 1;
}

.wc-page-header__title-main {
  font-family: var(--font-display, 'Barlow Condensed', sans-serif);
  font-size: clamp(3rem, 8vw, 5.5rem);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: -0.01em;
  color: #fff;
}

.wc-page-header__title-year {
  font-family: var(--font-display, 'Barlow Condensed', sans-serif);
  font-size: clamp(2.5rem, 6vw, 4rem);
  font-weight: 900;
  text-transform: uppercase;
  color: var(--tm-gold);
  letter-spacing: -0.02em;
  /* Borde texto para darle profundidad */
  -webkit-text-stroke: 1px rgba(245,166,35,0.4);
}

.wc-page-header__subtitle {
  font-family: 'Space Mono', monospace;
  font-size: 0.65rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--tm-text-dim);
  margin: 0;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .wc-page-header {
    padding: 32px 20px 28px;
  }
  .wc-page-header__title-main { font-size: 3rem; }
  .wc-page-header__title-year { font-size: 2.2rem; }
}
```

---

### 6. Actualizar `SeasonDropdown.tsx` — soporte SeasonItem[]

**Archivo:** `frontend/src/components/shared/SeasonDropdown.tsx`

Cambiar la interfaz para aceptar `SeasonItem[]` y mostrar badge "Mundial" para temporadas WC:

```tsx
import { useEffect, useRef, useState } from 'react'
import type { SeasonItem } from '../../types'
import { getSeasonLabel, isWorldCupSeason } from '../../utils/season'

interface Props {
  items: SeasonItem[]         // CAMBIA: antes seasons: string[]
  value: string
  onChange: (s: string) => void
  includeAll?: boolean
}

export default function SeasonDropdown({ items, value, onChange, includeAll = true }: Props) {
  const allOption: SeasonItem = { season: 'all', is_latest: false }
  const options = includeAll ? [allOption, ...items] : items
  const latestItem = items.find((i) => i.is_latest)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const currentLabel =
    value === 'all'
      ? 'Total histórico'
      : getSeasonLabel(value, items) + (latestItem?.season === value ? ' · Actual' : '')

  const isCurrentWc = isWorldCupSeason(value, items)

  return (
    <div className="season-dropdown" ref={ref}>
      <button
        className={`season-dropdown__trigger${open ? ' season-dropdown__trigger--open' : ''}${isCurrentWc ? ' season-dropdown__trigger--wc' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="season-dropdown__meta">Temporada</span>
        <span className="season-dropdown__current">{currentLabel}</span>
        <svg className="season-dropdown__chevron" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
          <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
        </svg>
      </button>

      {open && (
        <ul className="season-dropdown__menu" role="listbox" aria-label="Seleccionar temporada">
          {options.map((item) => {
            const isWc = item.is_world_cup === true
            const label =
              item.season === 'all'
                ? 'Todas las temporadas'
                : getSeasonLabel(item.season, items)
            return (
              <li
                key={item.season}
                role="option"
                aria-selected={value === item.season}
                className={[
                  'season-dropdown__item',
                  value === item.season ? 'season-dropdown__item--active' : '',
                  isWc ? 'season-dropdown__item--wc' : '',
                ].filter(Boolean).join(' ')}
                onClick={() => { onChange(item.season); setOpen(false) }}
              >
                <span>{label}</span>
                {isWc && <small className="season-dropdown__wc-badge">Mundial</small>}
                {item.is_latest && !isWc && (
                  <small className="season-dropdown__latest">Actual</small>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
```

**CSS — añadir al bloque existente de `.season-dropdown`:**

```css
/* Trigger en modo WC */
.season-dropdown__trigger--wc .season-dropdown__current {
  color: var(--tm-gold);
}

/* Item WC en el menú */
.season-dropdown__item--wc {
  color: var(--tm-gold) !important;
}

.season-dropdown__wc-badge {
  font-family: 'Space Mono', monospace;
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--tm-bg, #0C0C10);
  background: var(--tm-gold);
  border-radius: 2px;
  padding: 1px 5px;
}
```

---

### 7. Actualizar `SeasonSelector.tsx` — soporte SeasonItem[]

**Archivo:** `frontend/src/components/shared/SeasonSelector.tsx`

```tsx
import type { CSSProperties, KeyboardEvent } from 'react'
import type { SeasonItem } from '../../types'
import { getSeasonLabel, isWorldCupSeason } from '../../utils/season'

interface Props {
  items: SeasonItem[]         // CAMBIA: antes seasons: string[]
  value: string
  onChange: (s: string) => void
  includeAll?: boolean
}

export default function SeasonSelector({ items, value, onChange, includeAll = true }: Props) {
  const allOption: SeasonItem = { season: 'all', is_latest: false }
  const options = includeAll ? [...items, allOption] : items
  const activeIdx = options.findIndex((o) => o.season === value)

  if (options.length <= 1) return null

  const selectorStyle = {
    '--season-count': options.length,
    '--season-index': Math.max(activeIdx, 0),
  } as CSSProperties

  const isWcActive = isWorldCupSeason(value, items)

  function moveSelection(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    let nextIndex = index
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + options.length) % options.length
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % options.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = options.length - 1
    onChange(options[nextIndex].season)
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('.season-btn')
      [nextIndex]?.focus()
  }

  return (
    <div
      className={`season-selector${isWcActive ? ' season-selector--wc' : ''}`}
      role="radiogroup"
      aria-label="Temporada de estadísticas"
      style={selectorStyle}
    >
      <div className="season-selector__track" aria-hidden="true" />
      {options.map((item, i) => {
        const isWc = item.is_world_cup === true
        const label = item.season === 'all' ? 'Todas' : getSeasonLabel(item.season, items)
        const meta = item.season === 'all' ? 'Histórico' : isWc ? 'Mundial' : item.is_latest ? 'Actual' : 'Temporada'
        return (
          <button
            key={item.season}
            type="button"
            role="radio"
            className={[
              'season-btn',
              value === item.season ? 'season-btn--active' : '',
              isWc ? 'season-btn--wc' : '',
            ].filter(Boolean).join(' ')}
            onClick={() => onChange(item.season)}
            onKeyDown={(event) => moveSelection(event, i)}
            aria-checked={value === item.season}
            tabIndex={value === item.season ? 0 : -1}
          >
            <span className="season-btn__label">{label}</span>
            <span className="season-btn__meta">{meta}</span>
          </button>
        )
      })}
    </div>
  )
}
```

**CSS — añadir:**

```css
/* Selector en modo WC activo */
.season-selector--wc .season-selector__track {
  border-color: rgba(245, 166, 35, 0.35);
  background: rgba(245, 166, 35, 0.08);
}

/* Botón WC */
.season-btn--wc .season-btn__label {
  color: var(--tm-gold);
}
.season-btn--wc.season-btn--active .season-btn__label {
  color: var(--tm-gold);
}
```

---

### 8. Actualizar `RankingRow.tsx` — pasar season en link

- [x] Añadir prop `season?: string`
- [x] Cambiar `to={`/player/${player.id}`}` a `to={`/player/${player.id}${season ? `?season=${season}` : ''}`}`

```tsx
interface Props {
  player: RankedPlayer
  index?: number
  season?: string            // NUEVO
}

export default function RankingRow({ player, index = 0, season }: Props) {
  const isTop = player.rank <= 3
  const playerLink = `/player/${player.id}${season ? `?season=${season}` : ''}`

  return (
    <Link
      to={playerLink}
      className="ranking-row"
      style={{ animationDelay: `${Math.min(index * 35, 500)}ms` }}
    >
      {/* resto del componente sin cambios */}
```

---

### 9. Actualizar `RankingCard.tsx` — pasar season en link

Mismo patrón que ítem 8:

- [x] Añadir prop `season?: string`
- [x] Cambiar `to={`/player/${player.id}`}` a `to={`/player/${player.id}${season ? `?season=${season}` : ''}`}`

---

### 10. Actualizar `ShowcaseCard.tsx` — pasar season en link

Mismo patrón que ítem 8:

- [x] Añadir prop `season?: string`
- [x] Cambiar `to={`/player/${player.id}`}` a `to={`/player/${player.id}${season ? `?season=${season}` : ''}`}`

---

### 11. Actualizar `RankingPage.tsx`

Este es el cambio más extenso. Pasos:

- [x] Importar nuevos componentes y utils:
```ts
import type { Competition, RankedPlayer, PlayerDetail, SeasonItem } from '../types'
import { isWorldCupSeason, isSeasonReceivingWcPoints } from '../utils/season'
import WorldCupBanner from '../components/shared/WorldCupBanner'
import WorldCupPageHeader from '../components/shared/WorldCupPageHeader'
```

- [x] Cambiar estado `availableSeasons: string[]` a `seasonItems: SeasonItem[]`:
```ts
const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
```

- [x] Actualizar el efecto de `fetchSeasons` para guardar `SeasonItem[]`:
```ts
fetchSeasons()
  .then((data) => {
    setSeasonItems(data.seasons)
    const current = data.seasons.find((s) => s.is_latest)?.season ?? data.seasons[0]?.season
    if (current) setSeason(current)
  })
  .catch(() => {})
```

- [x] Derivar variables reactivas:
```ts
const isWcSeason = isWorldCupSeason(season, seasonItems)
const showWcBanner = isSeasonReceivingWcPoints(season, seasonItems)
const wcSeason = seasonItems.find((i) => i.is_world_cup)?.season
```

- [x] En la sección del header, añadir lógica condicional:
  - Si `isWcSeason`: renderizar `<WorldCupPageHeader totalPlayers={totalPlayers} />` en lugar del `rp-header` normal
  - Si no: renderizar el `rp-header` normal

- [x] En la sección del header normal (`rp-header`), añadir `WorldCupBanner` cuando `showWcBanner`:
```tsx
{showWcBanner && (
  <div className="rp-wc-banner-wrap">
    <WorldCupBanner onViewWorldCup={wcSeason ? () => setSeason(wcSeason) : undefined} />
  </div>
)}
```
Insertar después del `SeasonDropdown` y antes del contenido principal.

- [x] Pasar `items={seasonItems}` al `SeasonDropdown` (en lugar de `seasons={availableSeasons}`)

- [x] En modo WC (`isWcSeason`), ocultar `FilterBar` (no aplican filtros de posición/competición para selecciones nacionales):
```tsx
{!isWcSeason && (
  <FilterBar ... />
)}
```

- [x] Mantener el podio top-3 en modo WC usando los escudos de selección disponibles:
```tsx
{showHero && (
  <section className="rp-podium"> ... </section>
)}
```

- [x] Pasar `season={season}` a cada `<RankingRow>`, `<RankingCard>` y `<ShowcaseCard>`:
```tsx
<RankingRow player={p} index={i} season={season} />
<RankingCard player={p} index={i} season={season} />
<ShowcaseCard player={p} detail={...} season={season} />
```

- [x] CSS — añadir clase al body en modo WC para que los tokens `--tm-*` estén disponibles globalmente. Usar `useEffect`:
```ts
useEffect(() => {
  if (isWcSeason) {
    document.body.classList.add('mode-tournament')
  } else {
    document.body.classList.remove('mode-tournament')
  }
  return () => { document.body.classList.remove('mode-tournament') }
}, [isWcSeason])
```

**CSS — añadir para `.mode-tournament` overrides:**

```css
/* ─── Tournament mode: sobrescribe tokens cuando el cuerpo tiene .mode-tournament ── */
body.mode-tournament {
  background: var(--tm-bg);
}

body.mode-tournament .main-content {
  background: var(--tm-bg);
}

.rp-wc-banner-wrap {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 48px;
}

@media (max-width: 768px) {
  .rp-wc-banner-wrap { padding: 0 16px; }
}
```

---

### 12. Actualizar `PlayerPage.tsx`

- [x] Importar `useSearchParams`:
```ts
import { useParams, Link, useSearchParams } from 'react-router-dom'
```

- [x] Importar utils y tipos nuevos:
```ts
import type { SeasonItem } from '../types'
import { fetchSeasons } from '../api/client'
import { isWorldCupSeason } from '../utils/season'
```

- [x] Leer param de URL al montar:
```ts
const [searchParams] = useSearchParams()
const seasonFromUrl = searchParams.get('season') ?? ''
```

- [x] Guardar `SeasonItem[]` en estado:
```ts
const [seasonItems, setSeasonItems] = useState<SeasonItem[]>([])
```

- [x] Cargar `fetchSeasons()` en el efecto inicial (usa caché — no es una llamada extra en la red si ya se llamó en RankingPage):
```ts
fetchSeasons()
  .then((data) => setSeasonItems(data.seasons))
  .catch(() => {})
```

- [x] Usar `seasonFromUrl` como temporada inicial si está presente, de lo contrario usar `p.available_seasons[0]`:
```ts
// En el .then() de fetchPlayer:
const initialSeason = seasonFromUrl || p.available_seasons?.[0] || ''
initialSeasonRef.current = initialSeason
setSeason(initialSeason)
```

- [x] Derivar `isWcSeason`:
```ts
const isWcSeason = isWorldCupSeason(season, seasonItems)
```

- [x] Construir `SeasonItem[]` para el `SeasonSelector` combinando `available_seasons` del jugador con los metadatos globales:
```ts
const playerSeasonItems: SeasonItem[] = (player?.available_seasons ?? []).map((s) => {
  const meta = seasonItems.find((i) => i.season === s)
  return meta ?? { season: s, is_latest: false }
})
```

- [x] Pasar `items={playerSeasonItems}` al `SeasonSelector` (en lugar de `seasons={...}`)

- [x] En modo WC, añadir badge de selección nacional. Dentro del JSX, después de `<PlayerHeader>`:
```tsx
{isWcSeason && player?.team && (
  <div className="pp-national-badge">
    <span className="pp-national-badge__label">Selección</span>
    <span className="pp-national-badge__team">{player.team}</span>
  </div>
)}
```

- [x] Aplicar clase `.mode-tournament` al body cuando `isWcSeason` (mismo `useEffect` que en RankingPage):
```ts
useEffect(() => {
  if (isWcSeason) {
    document.body.classList.add('mode-tournament')
  } else {
    document.body.classList.remove('mode-tournament')
  }
  return () => { document.body.classList.remove('mode-tournament') }
}, [isWcSeason])
```

**CSS — badge selección nacional:**

```css
/* ─── National team badge (PlayerPage en modo WC) ────────────── */
@keyframes nationalBadgeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.pp-national-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  animation: nationalBadgeIn 250ms var(--tm-ease) both;
}

.pp-national-badge__label {
  font-family: 'Space Mono', monospace;
  font-size: 0.55rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--tm-text-dim, #8A94A8);
}

.pp-national-badge__team {
  font-family: var(--font-display, 'Barlow Condensed', sans-serif);
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--tm-gold);
  background: rgba(245, 166, 35, 0.08);
  border: 1px solid rgba(245, 166, 35, 0.2);
  border-radius: 3px;
  padding: 3px 10px;
}
```

---

### 13. Verificar build limpio

- [x] `npm run build` sin errores TypeScript
- [x] Verificar que `SeasonDropdown` en `RankingPage` recibe `items` (no `seasons`)
- [x] Verificar que `SeasonSelector` en `PlayerPage` recibe `items` (no `seasons`)
- [x] Sin console errors al cambiar entre temporada normal y WC (aunque WC aún no esté en DB)
- [x] El modo `.mode-tournament` se limpia del body al navegar a otra página

---

## Resumen visual del resultado

| Vista | Sin WC en DB | Con WC ingresado |
|---|---|---|
| Ranking (temporada 2025) | igual que hoy + banner amarillo al fondo | mismo |
| Ranking (temporada 2026/WC) | no aplica | header "Mundial 2026" + fondo oscuro + patrón diagonal |
| Perfil jugador (2025) | igual que hoy | igual que hoy |
| Perfil jugador (2026/WC) | no aplica | badge selección + fondo oscuro |
| Selector temporada | igual que hoy | aparece "Mundial 2026" en gold en el dropdown |

---

## Prompt estándar para Codex

```
Lee CLAUDE.md y ejecuta el plan en specs/0006-mundial-2026-tournament-edition.md.

Reglas:
- Sigue el checklist en orden, marca cada ítem al completarlo
- No reescribas componentes completos salvo los indicados en el spec
- Usa solo pure CSS (sin Tailwind), variables var(--token)
- No instales dependencias nuevas sin verificar package.json primero
- Código completo en cada archivo — sin // ... ni truncar
- Al terminar: npm run build debe pasar sin errores de tipo
```
