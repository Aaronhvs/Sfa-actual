# Spec 0001 — Selector de Temporada Multi-Season

## Contexto

Actualmente `SEASON = '2024'` está hardcodeado en `RankingPage.tsx` y `PlayerPage.tsx`.
El backend tendrá un nuevo endpoint `GET /api/v1/seasons` y soporte para `season=all`.
Este spec cubre SOLO el frontend. Ejecutar después de que el spec backend esté aplicado.

**Stack:** React 18 + TypeScript 5 (strict) + pure CSS — sin Tailwind, sin Framer Motion.
**Design tokens:** `var(--bg)`, `var(--gold)`, `var(--surface)`, `var(--surface2)`, `var(--text)`, `var(--text-dim)`, `var(--ease-out): cubic-bezier(0.23, 1, 0.32, 1)`.
**Fonts:** Barlow Condensed (`var(--font-display)`), Space Mono, Inter.

---

## Checklist de implementación

Procesar en orden. Marcar cada ítem al completarlo.

---

### 1. API client — nuevos tipos y función `fetchSeasons`

**Archivo:** `frontend/src/api/client.ts`

- [ ] Añadir `fetchSeasons()` que llame `GET /api/v1/seasons` y retorne `SeasonsResponse`
- [ ] La función debe usar el sistema de caché existente con key `'seasons'`
- [ ] Añadir a `frontend/src/types/index.ts`:

```ts
export interface SeasonsResponse {
  seasons: string[]   // ej: ["2025", "2024", "2023"] — ordenadas desc
  current: string     // la temporada más reciente con datos
}
```

- [ ] En `fetchPlayer`, la respuesta `PlayerDetail` ya tiene `competitions: string[]`.
  El backend añadirá `seasons: string[]` a `PlayerDetail`. Añadir ese campo al tipo:
  ```ts
  // En PlayerDetail (types/index.ts)
  seasons: string[]   // temporadas con datos para este jugador, ordenadas desc
  ```

---

### 2. Helper de formato de temporada

**Archivo:** `frontend/src/utils/season.ts` (archivo nuevo)

```ts
// Convierte "2024" → "24·25", "2025" → "25·26", "all" → "Historial"
export function seasonLabel(season: string): string {
  if (season === 'all') return 'Historial'
  const year = parseInt(season, 10)
  if (isNaN(year)) return season
  const next = (year + 1).toString().slice(-2)
  return `${season.slice(-2)}·${next}`
}
```

---

### 3. Componente `SeasonSelector`

**Archivo:** `frontend/src/components/shared/SeasonSelector.tsx` (archivo nuevo)

**Comportamiento:**
- Recibe `seasons: string[]`, `value: string`, `onChange: (s: string) => void`
- Siempre muestra las temporadas disponibles + opción `"all"` (Historial) al final
- El "track" (fondo deslizante) se mueve con `transform: translateX()` — GPU-accelerated
- Sin librería de animación — solo CSS transitions + useEffect para posicionar el track
- `scale(0.97)` en `:active` en cada botón (Emil: toda acción presionable tiene feedback físico)
- Gated detrás de `@media (hover: hover) and (pointer: fine)` para hover styles

```tsx
import { useEffect, useRef, useState } from 'react'
import { seasonLabel } from '../../utils/season'

interface Props {
  seasons: string[]          // ej: ["2025", "2024"]
  value: string              // temporada activa o "all"
  onChange: (s: string) => void
  includeAll?: boolean       // si mostrar opción "Historial" (default: true)
}

export default function SeasonSelector({ seasons, value, onChange, includeAll = true }: Props) {
  const options = includeAll ? [...seasons, 'all'] : seasons
  const activeIdx = options.indexOf(value)
  const trackRef = useRef<HTMLDivElement>(null)
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const btn = btnRefs.current[activeIdx]
    const track = trackRef.current
    if (!btn || !track) return
    track.style.transform = `translateX(${btn.offsetLeft}px)`
    track.style.width = `${btn.offsetWidth}px`
    // Primera vez: sin transición para que aparezca en posición correcta instantáneamente
    if (!ready) {
      track.style.transition = 'none'
      setReady(true)
    } else {
      track.style.transition = 'transform 200ms cubic-bezier(0.23, 1, 0.32, 1), width 200ms cubic-bezier(0.23, 1, 0.32, 1)'
    }
  }, [activeIdx, ready])

  return (
    <div className="season-selector" role="group" aria-label="Seleccionar temporada">
      <div className="season-selector__track" ref={trackRef} aria-hidden="true" />
      {options.map((s, i) => (
        <button
          key={s}
          ref={(el) => { btnRefs.current[i] = el }}
          className={`season-btn${value === s ? ' season-btn--active' : ''}`}
          onClick={() => onChange(s)}
          aria-pressed={value === s}
        >
          {seasonLabel(s)}
        </button>
      ))}
    </div>
  )
}
```

**Criterio de completitud:** el track desliza suavemente entre opciones, sin saltos.

---

### 4. CSS — `SeasonSelector` styles

**Archivo:** `frontend/src/index.css` — añadir al final (después de todos los bloques existentes)

```css
/* ─── SeasonSelector ─────────────────────────────────────────── */
.season-selector {
  position: relative;
  display: inline-flex;
  align-items: center;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 4px;
  padding: 2px;
}

.season-selector__track {
  position: absolute;
  top: 2px;
  left: 2px;
  height: calc(100% - 4px);
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(201,168,76,0.22);
  border-radius: 3px;
  pointer-events: none;
  z-index: 0;
  /* transition set via JS the first time */
}

.season-btn {
  position: relative;
  z-index: 1;
  background: transparent;
  border: 0;
  border-radius: 3px;
  color: var(--text-dim);
  font-family: 'Space Mono', monospace;
  font-size: 0.65rem;
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 150ms ease, transform 100ms ease-out;
}

.season-btn--active {
  color: var(--text);
}

.season-btn:active {
  transform: scale(0.97);
}

@media (hover: hover) and (pointer: fine) {
  .season-btn:not(.season-btn--active):hover {
    color: rgba(255,255,255,0.7);
  }
}

/* ─── Season bar (RankingPage) ──────────────────────────────── */
.rp-season-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 48px 0;
  max-width: 1200px;
  margin: 0 auto;
}

.rp-season-bar__label {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-faint);
}

/* ─── Player season selector (PlayerPage) ───────────────────── */
.pp-season-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.pp-season-bar__label {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-faint);
}
```

---

### 5. `RankingPage.tsx` — integrar season state

**Archivo:** `frontend/src/pages/RankingPage.tsx`

- [ ] Eliminar `const SEASON = '2024'`
- [ ] Añadir import: `import SeasonSelector from '../components/shared/SeasonSelector'`
- [ ] Añadir import: `import { fetchSeasons } from '../api/client'`
- [ ] Añadir import: `import type { SeasonsResponse } from '../types'`
- [ ] Añadir estado:
  ```ts
  const [seasonsData, setSeasonsData] = useState<SeasonsResponse | null>(null)
  const [season, setSeason] = useState<string>('') // '' = usa current del backend
  ```
- [ ] En `useEffect` inicial (el de `fetchCompetitions`), añadir también:
  ```ts
  fetchSeasons().then((data) => {
    setSeasonsData(data)
    setSeason(data.current)
  }).catch(() => {})
  ```
- [ ] En el `useEffect` que llama a `fetchRanking`, usar `season` en vez de `SEASON`:
  ```ts
  fetchRanking({ season, position: position || undefined, competition_id: competition, limit: 100 })
  ```
  **IMPORTANTE:** No disparar el efecto hasta que `season` esté inicializado (cuando `season === ''` no llamar).
  Condición: añadir `if (!season) return` al inicio del efecto, y añadir `season` al array de dependencias.
- [ ] En el `useEffect` de top3 (el que llama `fetchPlayer` para los 3 primeros), pasar `season`:
  ```ts
  data.ranking.slice(0, 3).map((p) => fetchPlayer(p.id, season))
  ```
- [ ] En la cabecera `rp-header`, añadir `rp-season-bar` DEBAJO de la sección existente:
  ```tsx
  {seasonsData && (
    <div className="rp-season-bar">
      <span className="rp-season-bar__label">Temporada</span>
      <SeasonSelector
        seasons={seasonsData.seasons}
        value={season}
        onChange={setSeason}
        includeAll={true}
      />
    </div>
  )}
  ```
  Insertar entre `</header>` y el bloque de loading skeleton.
- [ ] Actualizar el texto del header dinámicamente:
  ```tsx
  // En rp-header__eyebrow:
  <span className="rp-header__eyebrow">
    {season === 'all' ? 'Historial · Clasificación SFA' : `Temporada ${season} · Clasificación SFA`}
  </span>
  ```
- [ ] Cuando `season === 'all'`, ocultar la sección `rp-podium` (el podio top-3 no aplica para "all"):
  ```tsx
  {showHero && season !== 'all' && (
    <section className="rp-podium"> ... </section>
  )}
  ```

**Criterio de completitud:** cambiar temporada recarga el ranking y el podio sin errores de consola.

---

### 6. `PlayerPage.tsx` — integrar season state

**Archivo:** `frontend/src/pages/PlayerPage.tsx`

- [ ] Eliminar o reemplazar el hardcode de `season` (actualmente se pasa como param de URL o hardcoded)
- [ ] Añadir import: `import SeasonSelector from '../components/shared/SeasonSelector'`
- [ ] Añadir estado:
  ```ts
  const [season, setSeason] = useState<string>('')
  ```
- [ ] Una vez que `playerDetail` se carga, inicializar la temporada con la más reciente:
  ```ts
  // En el .then() del fetchPlayer inicial:
  if (!season && data.seasons && data.seasons.length > 0) {
    setSeason(data.seasons[0])
  }
  ```
- [ ] Añadir `season` como dependencia en los `useEffect` de `fetchPlayerEvents` y `fetchPlayerFixtures`
- [ ] En el header del jugador (componente `PlayerHeader` o directamente en la página), añadir el selector debajo del nombre:
  ```tsx
  {playerDetail && playerDetail.seasons && playerDetail.seasons.length > 1 && (
    <div className="pp-season-bar">
      <span className="pp-season-bar__label">Temporada</span>
      <SeasonSelector
        seasons={playerDetail.seasons}
        value={season}
        onChange={setSeason}
        includeAll={true}
      />
    </div>
  )}
  ```
  Si el jugador solo tiene datos de una temporada, no mostrar el selector.

**Criterio de completitud:** cambiar temporada en el perfil recarga stats, eventos y fixtures sin errores.

---

### 7. `fetchSeasons` — actualizar `client.ts`

```ts
export async function fetchSeasons(): Promise<SeasonsResponse> {
  const key = 'seasons'
  const cached = getCached<SeasonsResponse>(key)
  if (cached) return cached
  const data = await get<SeasonsResponse>('/seasons')
  setCache(key, data)
  return data
}
```

Añadir importar `SeasonsResponse` en `client.ts`.

---

### 8. Verificar build limpio

- [ ] `npm run build` pasa sin errores de TypeScript
- [ ] Verificar que los tipos de `fetchRanking` con `season=all` no rompen nada (el parámetro `season` ya es `string | undefined`, pasarle `"all"` es válido)

---

## Decisiones de diseño (para referencia)

### Por qué el selector va en el `rp-season-bar` y no dentro de `FilterBar`

La temporada es un filtro de nivel superior — afecta tanto el podio (top 3) como el grid completo y las estadísticas de la cabecera. Si estuviera en FilterBar, parecería un filtro secundario al mismo nivel que posición o competición. La jerarquía visual correcta es: temporada → todo lo demás.

### Por qué segmented control (track deslizante) y no dropdown

- Un dropdown genérico no forma parte del lenguaje visual del sistema
- Los segmented controls son más rápidos de operar (un clic vs dos)
- Con 2-4 temporadas + "Historial", las opciones caben siempre en una fila
- El track deslizante con `transform: translateX()` corre en GPU — sin jank

### Por qué `scale(0.97)` en `:active` en cada `season-btn`

Emil: todo elemento presionable debe dar feedback físico. El scale simula que el botón se hunde ligeramente. Invisible individualmente; compuesto con el track, hace que el selector se sienta "real".

### Por qué `transition: none` en el primer render

Sin esto, el track aparece en `left: 2px` y luego se mueve visualmente hasta su posición correcta — el usuario ve un destello de movimiento al cargar. Suprimiendo la transición en el primer frame y activándola después, el track aparece ya en su posición.

### Por qué ocultar el podio en modo "Historial"

El podio top-3 usa `ShowcaseCard` con fotos y stats específicos de la temporada. Para un ranking acumulado de todas las temporadas, no existe un "jugador de la temporada" con foto contextual — la jerarquía temporal se rompe. El grid de cards sí puede mostrar ranking histórico con stats acumulados.
