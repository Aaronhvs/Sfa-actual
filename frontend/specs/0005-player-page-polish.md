# Spec 0005 — Player Page Polish + Footer + Fixture Context

> Lee `CLAUDE.md` completo antes de empezar.
> Aplica `/design-taste-frontend` (VARIANCE=6, MOTION=4, DENSITY=7) + `/emil-design-eng`.
> **Cambios quirúrgicos.** No reescribas componentes completos. Pure CSS, `var(--token)`.

---

## 1. Renombrar tab "Lista completa" → "Todos"

**Archivo:** `src/components/player/FixtureList.tsx`

Busca el botón con label `Lista completa` y cámbialo a `Todos`.

```tsx
// antes
>Lista completa</button>
// después
>Todos</button>
```

---

## 2. Eliminar ActionValues + ScoringExplainer del final de PlayerPage

**Archivo:** `src/pages/PlayerPage.tsx`

Elimina el bloque final que envuelve esos dos componentes:

```tsx
// ELIMINAR — estas líneas ya no van en el player page
<div className="card mt-32">
  <ActionValues position={player.position} />
  <ScoringExplainer initialOpen={false} />
</div>
```

Elimina también los dos imports (`ActionValues`, `ScoringExplainer`).

> Esos componentes ya tienen su lugar en `/metodologia`. El player page queda limpio.

---

## 3. Logo en Navbar

**Archivo:** `src/components/layout/Navbar.tsx`

El logo ya existe en `public/blanco.png`. Añade un `<img>` a la izquierda del pill, como link a `/ranking`.

```tsx
import { NavLink, Link } from 'react-router-dom'

// Dentro del JSX, ANTES del <div className="navbar__pill">:
<Link to="/ranking" className="navbar__logo-link" aria-label="SFA — inicio">
  <img src="/blanco.png" alt="SFA" className="navbar__logo-img" />
</Link>
```

**CSS a añadir en `index.css`:**

```css
/* ─── Navbar logo ───────────────────────────────────────────── */
.navbar__logo-link {
  position: absolute;
  left: 24px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  text-decoration: none;
  opacity: 0.9;
  transition: opacity 0.15s;
}
.navbar__logo-link:hover { opacity: 1; }

.navbar__logo-img {
  height: 24px;
  width: auto;
  display: block;
}
```

> La navbar ya usa `position: fixed` (o similar). El logo queda flotando a la izquierda sin romper el pill centrado.

---

## 4. Footer global (nuevo componente)

**Crear:** `src/components/layout/Footer.tsx`

```tsx
import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__brand">
          <Link to="/ranking" className="site-footer__logo-link" aria-label="SFA">
            <img src="/blanco.png" alt="SFA" className="site-footer__logo-img" />
          </Link>
          <p className="site-footer__tagline">
            Sistema de análisis de fútbol · Temporada 2024/25
          </p>
        </div>

        <nav className="site-footer__nav" aria-label="Pie de página">
          <Link to="/ranking" className="site-footer__nav-link">Ranking</Link>
          <Link to="/compare" className="site-footer__nav-link">Comparar</Link>
          <Link to="/metodologia" className="site-footer__nav-link">Metodología</Link>
        </nav>

        <p className="site-footer__legal">
          Datos: API-Football · Solo con fines analíticos y educativos
        </p>
      </div>
    </footer>
  )
}
```

**Añadir a `src/App.tsx`:**

```tsx
import Footer from './components/layout/Footer'

// Dentro del return, después de </main>:
<Footer />
```

**CSS a añadir en `index.css`:**

```css
/* ─── Site footer ───────────────────────────────────────────── */
.site-footer {
  background: #0a0a0a;
  border-top: 1px solid var(--border-sub);
  padding: 48px 0 32px;
  margin-top: 80px;
}

.site-footer__inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 32px;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 24px 64px;
  align-items: start;
}

.site-footer__brand {
  grid-column: 1;
  grid-row: 1;
}

.site-footer__logo-link {
  display: inline-flex;
  text-decoration: none;
  margin-bottom: 12px;
}

.site-footer__logo-img {
  height: 28px;
  width: auto;
  opacity: 0.85;
  transition: opacity 0.15s;
}
.site-footer__logo-link:hover .site-footer__logo-img { opacity: 1; }

.site-footer__tagline {
  font-family: var(--font-mono);
  font-size: 0.60rem;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-faint);
  line-height: 1.6;
  margin: 0;
}

.site-footer__nav {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-end;
}

.site-footer__nav-link {
  font-family: var(--font-mono);
  font-size: 0.60rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.15s;
}
.site-footer__nav-link:hover { color: var(--text); }

.site-footer__legal {
  grid-column: 1 / -1;
  grid-row: 2;
  font-family: var(--font-mono);
  font-size: 0.54rem;
  letter-spacing: 0.08em;
  color: var(--text-faint);
  opacity: 0.55;
  border-top: 1px solid var(--border-sub);
  padding-top: 20px;
  margin: 0;
}

@media (max-width: 640px) {
  .site-footer__inner {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }
  .site-footer__nav {
    grid-column: 1;
    grid-row: 2;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 10px 20px;
  }
  .site-footer__legal { grid-row: 3; }
}
```

---

## 5. Desglose de puntos — section totals + tile animation

**Archivo:** `src/components/player/PointsBreakdown.tsx`

### 5a. Añadir total de pts por sección

Cambia el render de cada section para mostrar el total de puntos al lado del título:

```tsx
// Reemplaza el bloque sections.map(...)
{sections.map((section) => {
  const sectionPts = section.tiles.reduce((sum, t) => sum + t.pts, 0)
  return (
    <div key={section.title} className="ptsbr__section">
      <div className="ptsbr__section-header">
        <span className="ptsbr__section-title">{section.title}</span>
        {sectionPts !== 0 && (
          <span className={`ptsbr__section-pts${sectionPts < 0 ? ' ptsbr__section-pts--neg' : ''}`}>
            {sectionPts > 0 ? '+' : '−'}{fmt(Math.abs(sectionPts))}
          </span>
        )}
      </div>
      <div className="ptsbr__grid">
        {section.tiles.map((tile) => {
          const idx = globalIdx++
          return (
            <StatTile key={tile.key} tile={tile} delay={idx * 50} visible={visible} />
          )
        })}
      </div>
    </div>
  )
})}
```

### 5b. Count-up animation para números enteros simples

Añade este hook ANTES del componente `StatTile`:

```tsx
import { useMemo, useState, useEffect, useRef } from 'react'

function useCountUp(target: number, visible: boolean, delay: number): number {
  const [count, setCount] = useState(0)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (!visible || target === 0) return
    const timer = setTimeout(() => {
      const duration = 750
      const startTime = performance.now()
      const step = (now: number) => {
        const t = Math.min((now - startTime) / duration, 1)
        const eased = 1 - Math.pow(1 - t, 3)
        setCount(Math.round(target * eased))
        if (t < 1) { rafRef.current = requestAnimationFrame(step) }
      }
      rafRef.current = requestAnimationFrame(step)
    }, delay)
    return () => {
      clearTimeout(timer)
      cancelAnimationFrame(rafRef.current)
    }
  }, [visible, target, delay])

  return count
}
```

Modifica `StatTile` para usar el hook en valores enteros simples:

```tsx
function StatTile({ tile, delay, visible }: TileProps) {
  const offset = CIRC * (1 - tile.pct)
  const isInt = /^\d+$/.test(tile.displayValue)
  const targetInt = isInt ? parseInt(tile.displayValue, 10) : 0
  const animatedInt = useCountUp(targetInt, visible && isInt, delay)
  const displayNum = visible && isInt ? String(animatedInt) : tile.displayValue

  return (
    <div className="ptsbr__tile" style={{ animationDelay: `${delay}ms` }}>
      <div className="ptsbr__ring-wrap">
        <svg viewBox="0 0 64 64" aria-hidden="true">
          <circle className="ptsbr__ring-track" cx="32" cy="32" r="26" />
          <circle
            className={`ptsbr__ring-fill${tile.isNeg ? ' ptsbr__ring-fill--neg' : ''}`}
            cx="32" cy="32" r="26"
            style={{
              strokeDasharray:  CIRC,
              strokeDashoffset: visible ? offset : CIRC,
              transitionDelay:  visible ? `${delay}ms` : '0ms',
            }}
          />
        </svg>
        <span className="ptsbr__ring-num">{displayNum}</span>
      </div>
      <span className="ptsbr__tile-label">{tile.label}</span>
      {tile.pts !== 0 && (
        <span className={`ptsbr__tile-pts${tile.isNeg ? ' ptsbr__tile-pts--neg' : tile.isEst ? ' ptsbr__tile-pts--est' : ''}`}>
          {tile.isNeg ? '−' : '+'}{fmt(Math.abs(tile.pts))}{tile.isEst ? ' ~' : ''}
        </span>
      )}
      {tile.subText && (
        <span className="ptsbr__tile-sub">{tile.subText}</span>
      )}
    </div>
  )
}
```

**CSS a añadir en `index.css`** (en la sección de `.ptsbr`):

```css
/* Reemplaza la regla .ptsbr__section-title existente */
.ptsbr__section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 20px 12px;
}

.ptsbr__section-title {
  display: block;
  font-family: 'Space Mono', monospace;
  font-size: 0.60rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-faint);
  border-left: 2px solid var(--gold);
  padding: 2px 0 2px 10px;
  margin: 0;           /* ← quitar el margin que tenía antes */
}

.ptsbr__section-pts {
  font-family: var(--font-display);
  font-size: 0.80rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--gold);
}

.ptsbr__section-pts--neg { color: var(--neg); }

/* Tile entry stagger */
@keyframes ptsbr-tile-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.ptsbr__tile {
  animation: ptsbr-tile-in 0.45s cubic-bezier(0.23, 1, 0.32, 1) both;
}
```

> IMPORTANTE: `.ptsbr__tile` ya tiene otras propiedades definidas — añade `animation` y el `@keyframes` sin duplicar las propiedades existentes.

---

## 6. Contexto en FixtureRow — minutos jugados + panel de contexto

**Archivo:** `src/components/player/FixtureRow.tsx`

### 6a. Mostrar minutos en la cabecera

`PlayerFixture` ya tiene el campo `minutes: number`. Añádelo junto al score:

```tsx
// Dentro de fixture-row__score-col, ANTES del pts:
{fixture.minutes > 0 && (
  <span className="fixture-row__mins">{fixture.minutes}'</span>
)}
```

### 6b. Panel de contexto (nuevo componente interno)

Añade este componente ANTES de `EventsPanel`:

```tsx
function FixtureContextBar({ fixture, events }: { fixture: PlayerFixture; events: PlayerEvent[] }) {
  const keyEvents = events.filter(
    (e) => GOAL_TYPES.has(e.event_type) || CREATION_TYPES.has(e.event_type)
  )
  const avgM1 = keyEvents.length > 0
    ? keyEvents.reduce((s, e) => s + e.m1, 0) / keyEvents.length
    : null
  const isVisitor = keyEvents.some((e) => e.mvisit > 1)

  const items: { label: string; value: string }[] = []

  if (fixture.minutes > 0)
    items.push({ label: 'Jugó', value: `${fixture.minutes}'` })

  if (avgM1 !== null) {
    const rivalDesc =
      avgM1 >= 1.4 ? 'Élite' :
      avgM1 >= 1.1 ? 'Superior' :
      avgM1 >= 0.9 ? 'Similar' : 'Inferior'
    items.push({ label: 'Rival', value: `M1 ×${avgM1.toFixed(2)} · ${rivalDesc}` })
  }

  if (keyEvents.length > 0)
    items.push({ label: 'Campo', value: isVisitor ? 'Visitante ×1.15' : 'Local' })

  if (fixture.rating != null)
    items.push({ label: 'Nota API', value: fixture.rating.toFixed(1) })

  if (items.length === 0) return null

  return (
    <div className="fxctx">
      {items.map((item) => (
        <div key={item.label} className="fxctx__item">
          <span className="fxctx__label">{item.label}</span>
          <span className="fxctx__value">{item.value}</span>
        </div>
      ))}
    </div>
  )
}
```

Añádelo al inicio de `EventsPanel`:

```tsx
function EventsPanel({ events, fixture }: ...) {
  ...
  return (
    <div className="events-panel">
      <FixtureContextBar fixture={fixture} events={events} />  {/* ← añadir */}
      <ActionBreakdownGrid fixture={fixture} />
      ...
    </div>
  )
}
```

**CSS a añadir en `index.css`:**

```css
/* ─── Fixture row — minutos + contexto ──────────────────────── */
.fixture-row__mins {
  font-family: var(--font-mono);
  font-size: 0.54rem;
  letter-spacing: 0.06em;
  color: var(--text-faint);
  display: block;
  text-align: right;
  margin-bottom: 2px;
}

.fxctx {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
  padding: 8px 14px;
  margin-bottom: 4px;
  background: rgba(255,255,255,0.02);
  border-left: 2px solid rgba(255,255,255,0.07);
}

.fxctx__item {
  display: flex;
  align-items: center;
  gap: 7px;
}

.fxctx__label {
  font-family: var(--font-mono);
  font-size: 0.52rem;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--text-faint);
}

.fxctx__value {
  font-family: var(--font-mono);
  font-size: 0.58rem;
  font-weight: 700;
  color: var(--text-secondary);
}
```

---

## Verificación

1. `npm run build` — sin errores TypeScript
2. Abrir un perfil de jugador:
   - [ ] Tab "Destacados" y tab "Todos" visibles
   - [ ] El bloque ActionValues/ScoringExplainer ya NO aparece al fondo del player page
   - [ ] En `Desglose de puntos`: cada sección muestra total de pts a la derecha
   - [ ] Los números de los tiles animan (count-up) al hacer scroll hasta ellos
   - [ ] Al expandir un partido: se ve barra con `Jugó Xmin · Rival M1 ×X.XX · ...`
   - [ ] Los minutos (`X'`) aparecen en la cabecera del partido
3. Abrir cualquier página:
   - [ ] Navbar muestra el logo `blanco.png` a la izquierda del pill
   - [ ] Footer visible al fondo con logo, links y legal
4. En mobile (640px): footer en columna, nav links en fila
