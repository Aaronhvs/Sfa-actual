# Spec 0003 — Página Metodología SFA

> Leer `CLAUDE.md` completo antes de empezar. Aplicar skills `/high-end-visual-design` + `/design-taste-frontend` (VARIANCE=6, MOTION=4, DENSITY=7) + `/emil-design-eng`.

## Objetivo

Crear una página `/metodologia` completa que explique cómo funciona el sistema de puntuación SFA. Dos niveles de lectura:
- **Nivel casual**: entiende la idea en 30 segundos
- **Nivel entusiasta**: comprende cada multiplicador en detalle

Sin llamadas a API. Todo el contenido es estático. Animaciones CSS puras (sin Framer Motion ni GSAP).

---

## Checklist de implementación

### Paso 1 — Routing y Navbar

**`src/App.tsx`**: agregar la ruta:
```tsx
import MetodologiaPage from './pages/MetodologiaPage'
// dentro de <Routes>:
<Route path="/metodologia" element={<MetodologiaPage />} />
```

**`src/components/layout/Navbar.tsx`**: agregar el link junto a EQUIPOS y COMPARAR:
```tsx
<NavLink to="/metodologia">Metodología</NavLink>
```

---

### Paso 2 — Estructura del archivo

Crear `src/pages/MetodologiaPage.tsx`. Estructura de secciones en orden:

```
<div className="met-page">
  <MET_HERO />
  <MET_CONCEPTO />
  <MET_FORMULA />
  <MET_MULTIPLICADORES />
  <MET_POSICIONES />
  <MET_LOGROS />
  <MET_EJEMPLO />
</div>
```

Cada sección es un bloque `<section>` con su clase CSS. No usar componentes separados — todo en un solo archivo para que Codex no pierda contexto.

---

### Paso 3 — Sección HERO (`met-hero`)

**Diseño**: Full-width, alto mínimo `100dvh`, centrado vertical. Fondo `#0a0a0a` con una cuadrícula de puntos muy sutil (CSS `radial-gradient` en el background). Título enorme que entra con animación.

**Contenido**:
```tsx
<section className="met-hero">
  <div className="met-hero__inner">
    <span className="met-hero__eyebrow">Sistema de Puntuación</span>
    <h1 className="met-hero__title">
      <span className="met-hero__title-line">No todos</span>
      <span className="met-hero__title-line met-hero__title-line--gold">los goles</span>
      <span className="met-hero__title-line">valen igual.</span>
    </h1>
    <p className="met-hero__sub">
      El SFA mide el impacto real de cada acción: contra quién, en qué momento,
      en qué competición y qué tan difícil fue.
    </p>
    <div className="met-hero__scroll-hint">
      <span>Descubrir cómo</span>
      <div className="met-hero__scroll-arrow" />
    </div>
  </div>
  {/* Número flotante decorativo de fondo */}
  <div className="met-hero__bg-formula" aria-hidden="true">SFA</div>
</section>
```

**CSS clave**:
```css
.met-hero {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  background:
    radial-gradient(circle at 50% 50%, rgba(201,168,76,0.04) 0%, transparent 60%),
    #0a0a0a;
  position: relative;
  overflow: hidden;
}
.met-hero__title-line { display: block; }
.met-hero__title-line--gold { color: var(--gold); }
.met-hero__bg-formula {
  position: absolute;
  right: -0.1em;
  top: 50%;
  transform: translateY(-50%);
  font-family: var(--font-display);
  font-size: clamp(180px, 30vw, 320px);
  font-weight: 800;
  color: rgba(255,255,255,0.025);
  letter-spacing: -0.05em;
  pointer-events: none;
  user-select: none;
}
/* Animación de entrada del título — stagger por línea */
.met-hero__title-line {
  opacity: 0;
  transform: translateY(24px);
  animation: met-line-in 0.7s cubic-bezier(0.23, 1, 0.32, 1) forwards;
}
.met-hero__title-line:nth-child(1) { animation-delay: 0.1s; }
.met-hero__title-line:nth-child(2) { animation-delay: 0.22s; }
.met-hero__title-line:nth-child(3) { animation-delay: 0.34s; }
@keyframes met-line-in {
  to { opacity: 1; transform: translateY(0); }
}
/* Scroll hint con flecha pulsante */
.met-hero__scroll-arrow {
  width: 1px;
  height: 40px;
  background: linear-gradient(to bottom, var(--gold), transparent);
  margin: 8px auto 0;
  animation: met-pulse-arrow 2s ease-in-out infinite;
}
@keyframes met-pulse-arrow {
  0%, 100% { opacity: 1; transform: translateY(0); }
  50% { opacity: 0.4; transform: translateY(6px); }
}
```

---

### Paso 4 — Sección CONCEPTO (`met-concepto`)

**Diseño**: 3 tarjetas horizontales (o verticales en mobile). Cada tarjeta tiene un número grande dorado, título corto y descripción breve. Entran con `animation-delay` escalonado al hacer scroll (usar `IntersectionObserver` con clase `--visible`).

**Contenido de las 3 tarjetas**:

| # | Título | Descripción |
|---|---|---|
| 01 | El contexto importa | Un gol contra el líder en el minuto 89 vale más que un gol en un partido sin trascendencia. El SFA lo captura. |
| 02 | Cada posición tiene su metro | Un lateral que genera juego puntúa diferente a un delantero. Los roles no son intercambiables. |
| 03 | Los logros colectivos cuentan | Ganar la Champions o tu liga suma puntos extra proporcionales a tu participación en el éxito del equipo. |

**CSS clave**:
```css
.met-concepto__cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;
}
.met-concepto__card {
  background: var(--surface);
  padding: 40px 32px;
  border-top: 1px solid rgba(255,255,255,0.06);
  opacity: 0;
  transform: translateY(32px);
  transition: opacity 0.6s cubic-bezier(0.23,1,0.32,1), transform 0.6s cubic-bezier(0.23,1,0.32,1);
}
.met-concepto__card.--visible {
  opacity: 1;
  transform: translateY(0);
}
.met-concepto__card:nth-child(2) { transition-delay: 0.1s; }
.met-concepto__card:nth-child(3) { transition-delay: 0.2s; }
.met-concepto__num {
  font-family: var(--font-display);
  font-size: 3.5rem;
  font-weight: 800;
  color: var(--gold);
  opacity: 0.35;
  line-height: 1;
  margin-bottom: 16px;
}
```

**IntersectionObserver** (dentro del componente React):
```tsx
useEffect(() => {
  const cards = document.querySelectorAll('.met-concepto__card, .met-mult__item, .met-logro__row')
  const obs = new IntersectionObserver(
    (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('--visible') }),
    { threshold: 0.15 }
  )
  cards.forEach((c) => obs.observe(c))
  return () => obs.disconnect()
}, [])
```

---

### Paso 5 — Sección FÓRMULA (`met-formula`)

**Diseño**: Fondo `#0a0a0a`, centrado. La fórmula se muestra en un bloque visual grande con cada componente destacado. Abajo, una leyenda que explica cada símbolo.

**Contenido**:
```tsx
<section className="met-formula">
  <div className="met-section-header">
    <span className="met-eyebrow">La matemática detrás</span>
    <h2 className="met-section-title">La Fórmula</h2>
  </div>
  <div className="met-formula__display">
    <span className="met-formula__pts">SFA pts</span>
    <span className="met-formula__eq">=</span>
    <span className="met-formula__sigma">Σ</span>
    <div className="met-formula__factors">
      <span className="met-formula__factor met-formula__factor--base">base</span>
      <span className="met-formula__op">×</span>
      <span className="met-formula__factor met-formula__factor--m1">M1</span>
      <span className="met-formula__op">×</span>
      <span className="met-formula__factor met-formula__factor--m2">M2</span>
      <span className="met-formula__op">×</span>
      <span className="met-formula__factor met-formula__factor--m3">M3</span>
      <span className="met-formula__op">×</span>
      <span className="met-formula__factor met-formula__factor--m4">M4</span>
      <span className="met-formula__op">×</span>
      <span className="met-formula__factor met-formula__factor--mv">Mv</span>
    </div>
  </div>
  <div className="met-formula__legend">
    {/* 6 píldoras, una por factor */}
    <div className="met-formula__pill met-formula__pill--base">
      <strong>base</strong> Puntos base según posición y acción
    </div>
    <div className="met-formula__pill met-formula__pill--m1">
      <strong>M1</strong> Fuerza del rival (0.6 – 1.8×)
    </div>
    <div className="met-formula__pill met-formula__pill--m2">
      <strong>M2</strong> Fase de la competición (1.0 – 1.5×)
    </div>
    <div className="met-formula__pill met-formula__pill--m3">
      <strong>M3</strong> Momento del partido (minuto + marcador)
    </div>
    <div className="met-formula__pill met-formula__pill--m4">
      <strong>M4</strong> Dificultad del disparo (xG)
    </div>
    <div className="met-formula__pill met-formula__pill--mv">
      <strong>Mv</strong> Bonus visitante (1.15× fuera de casa)
    </div>
  </div>
</section>
```

**CSS clave**: Los factores de la fórmula tienen colores distintos (no todos dorados). Usar variaciones de opacity del gold y tintes neutros para diferenciarlos. El `Σ` es grande y dorado.

```css
.met-formula__display {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 3vw, 2.5rem);
  font-weight: 700;
}
.met-formula__pts { color: var(--gold); }
.met-formula__sigma { font-size: 3em; color: var(--gold); line-height: 1; }
.met-formula__factor {
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid;
  font-size: 0.85em;
}
.met-formula__factor--base { border-color: rgba(201,168,76,0.4); color: var(--gold); }
.met-formula__factor--m1  { border-color: rgba(100,160,255,0.4); color: #64a0ff; }
.met-formula__factor--m2  { border-color: rgba(100,220,180,0.4); color: #64dcb4; }
.met-formula__factor--m3  { border-color: rgba(255,140,80,0.4);  color: #ff8c50; }
.met-formula__factor--m4  { border-color: rgba(200,100,255,0.4); color: #c864ff; }
.met-formula__factor--mv  { border-color: rgba(255,220,80,0.4);  color: #ffdc50; }
.met-formula__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  margin-top: 48px;
}
.met-formula__pill {
  padding: 10px 18px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  font-size: 0.8rem;
  line-height: 1.5;
  max-width: 220px;
  color: var(--text-secondary);
}
.met-formula__pill strong { display: block; font-size: 1.1em; margin-bottom: 2px; }
/* Colores que coinciden con los factores de arriba */
.met-formula__pill--base strong { color: var(--gold); }
.met-formula__pill--m1 strong   { color: #64a0ff; }
.met-formula__pill--m2 strong   { color: #64dcb4; }
.met-formula__pill--m3 strong   { color: #ff8c50; }
.met-formula__pill--m4 strong   { color: #c864ff; }
.met-formula__pill--mv strong   { color: #ffdc50; }
```

---

### Paso 6 — Sección MULTIPLICADORES (`met-multiplicadores`)

**Diseño**: Lista vertical de 5 bloques. Cada bloque (`met-mult__item`) tiene: nombre del multiplicador a la izquierda (sticky o fijo), descripción y rango visual a la derecha. Alterna fondo `var(--surface)` y `var(--bg)`. Entran con scroll animation (clase `--visible` via IntersectionObserver del Paso 4).

**Datos de cada multiplicador**:

```tsx
const MULTIPLICADORES = [
  {
    id: 'M1',
    color: '#64a0ff',
    nombre: 'Fuerza del Rival',
    rango: '0.6× – 1.8×',
    descripcion: 'Cuanto más fuerte el equipo contrario, más valen tus acciones. Un gol contra el líder de la Premier League puntúa casi el triple que contra el colista.',
    detalle: 'Se calcula a partir del ELO del equipo rival, ajustado por la fortaleza de su liga. El clamp [0.6, 1.8] evita que equipos irrelevantes o dominantes distorsionen el ranking.',
    ejemplo: { bajo: 'vs equipo débil → ×0.6', alto: 'vs líder Champions → ×1.8' }
  },
  {
    id: 'M2',
    color: '#64dcb4',
    nombre: 'Fase de Competición',
    rango: '1.0× – 1.5×',
    descripcion: 'Una semifinal de Champions vale más que la fase de grupos. A mayor trascendencia del partido, mayor multiplicador.',
    detalle: 'La fase del torneo determina M2: fase de grupos = 1.0, octavos = 1.1, cuartos = 1.2, semifinal = 1.35, final = 1.5. En liga, los partidos directos por el título aplican un bonus.',
    ejemplo: { bajo: 'Fase de grupos → ×1.0', alto: 'Final Champions → ×1.5' }
  },
  {
    id: 'M3',
    color: '#ff8c50',
    nombre: 'Momento del Partido',
    rango: 'variable',
    descripcion: 'Un gol en el minuto 89 que da la vuelta al marcador vale mucho más que un gol en el 10 cuando ya ganabas 3-0. El SFA captura la tensión del momento.',
    detalle: 'M3 combina el minuto del partido con la diferencia de goles en ese instante. Acciones en empate o desventaja, en los últimos 20 minutos, reciben el mayor bonus.',
    ejemplo: { bajo: 'Gol en min 10, ganando 3-0 → bajo', alto: 'Gol en min 89, perdiendo → máximo' }
  },
  {
    id: 'M4',
    color: '#c864ff',
    nombre: 'Dificultad del Disparo',
    rango: '0.8× – 1.2×',
    descripcion: 'No es lo mismo rematar solo frente al portero que marcar desde 35 metros en ángulo imposible. El xG mide la probabilidad real del disparo.',
    detalle: 'Basado en el Expected Goals (xG) de la acción. Un disparo con xG bajo (difícil) que acaba en gol recibe bonus M4 alto. Solo aplica a goles — no a asistencias ni otras acciones.',
    ejemplo: { bajo: 'Penalti (xG≈0.76) → ×0.8', alto: 'Tiro difícil (xG<0.1) → ×1.2' }
  },
  {
    id: 'Mv',
    color: '#ffdc50',
    nombre: 'Bonus Visitante',
    rango: '×1.15 fuera de casa',
    descripcion: 'Jugar fuera de casa es más difícil. Las acciones clave como goles, asistencias y corners asistidos se multiplican por 1.15 cuando el jugador juega de visitante.',
    detalle: 'Solo aplica a las acciones más decisivas (goal, assist, corner_assist, goal_penalty, goal_shootout). Las acciones de estadística como pases o tackles no reciben este bonus.',
    ejemplo: { bajo: 'En casa → ×1.0', alto: 'De visitante → ×1.15' }
  },
]
```

**Render de cada item**:
```tsx
{MULTIPLICADORES.map((m, i) => (
  <div key={m.id} className="met-mult__item" style={{ '--mult-color': m.color } as React.CSSProperties}>
    <div className="met-mult__id">{m.id}</div>
    <div className="met-mult__body">
      <div className="met-mult__header">
        <h3 className="met-mult__nombre">{m.nombre}</h3>
        <span className="met-mult__rango">{m.rango}</span>
      </div>
      <p className="met-mult__desc">{m.descripcion}</p>
      <p className="met-mult__detalle">{m.detalle}</p>
      <div className="met-mult__ejemplos">
        <span className="met-mult__ej met-mult__ej--bajo">{m.ejemplo.bajo}</span>
        <span className="met-mult__ej met-mult__ej--alto">{m.ejemplo.alto}</span>
      </div>
    </div>
  </div>
))}
```

**CSS clave**:
```css
.met-mult__item {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 48px;
  padding: 56px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  opacity: 0;
  transform: translateX(-24px);
  transition: opacity 0.6s cubic-bezier(0.23,1,0.32,1), transform 0.6s cubic-bezier(0.23,1,0.32,1);
}
.met-mult__item.--visible { opacity: 1; transform: translateX(0); }
.met-mult__id {
  font-family: var(--font-display);
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--mult-color, var(--gold));
  letter-spacing: -0.02em;
  padding-top: 4px;
}
.met-mult__nombre { color: var(--mult-color, white); font-size: 1.2rem; }
.met-mult__rango {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--mult-color, var(--gold));
  background: rgba(255,255,255,0.05);
  padding: 3px 10px;
  border-radius: 3px;
}
.met-mult__desc { color: var(--text-primary); margin: 12px 0 8px; line-height: 1.6; }
.met-mult__detalle { color: var(--text-secondary); font-size: 0.85rem; line-height: 1.6; }
.met-mult__ejemplos { display: flex; gap: 16px; margin-top: 16px; flex-wrap: wrap; }
.met-mult__ej {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  padding: 4px 12px;
  border-radius: 3px;
}
.met-mult__ej--bajo { background: rgba(255,255,255,0.04); color: var(--text-secondary); }
.met-mult__ej--alto { background: rgba(201,168,76,0.1); color: var(--gold); }
```

---

### Paso 7 — Sección POSICIONES (`met-posiciones`)

**Diseño**: Tabla visual que muestra para cada posición las acciones más valoradas. NO usar `<table>` — usar una grid visual. Fondo oscuro `#0a0a0a`.

**Contenido**:
```tsx
const POSICIONES = [
  { pos: 'DEL', nombre: 'Delantero', color: '#ff6b6b', top: ['Gol (650 pts)', 'Penal (390 pts)', 'Asistencia (500 pts)'] },
  { pos: 'EXT', nombre: 'Extremo',   color: '#ff8c50', top: ['Regate ganado (110 pts)', 'Gol (550 pts)', 'Falta recibida (60 pts)'] },
  { pos: 'MCO', nombre: 'MC Ofensivo', color: '#c864ff', top: ['Gol (600 pts)', 'Asistencia (520 pts)', 'xG sin gol (70 pts)'] },
  { pos: 'MC',  nombre: 'Mediocampista', color: '#64dcb4', top: ['Pases completados (7 pts/c)', 'Gol (720 pts)', 'Recuperación (95 pts)'] },
  { pos: 'LAT', nombre: 'Lateral',   color: '#64a0ff', top: ['Gol (850 pts)', 'Asistencia (620 pts)', 'Córner asistido (300 pts)'] },
  { pos: 'DC',  nombre: 'Def. Central', color: '#aaa', top: ['Gol (1000 pts)', 'Bloqueo (180 pts)', 'Intercepción (160 pts)'] },
]
```

Render: grid de 6 tarjetas con la posición abreviada grande, nombre, y las 3 acciones top como lista de chips.

---

### Paso 8 — Sección LOGROS (`met-logros`)

**Diseño**: Dos columnas — Competición internacional (Champions, Europa, Conference) y Liga doméstica/Copa. Cada logro tiene una barra de progreso visual que muestra el peso relativo.

**Datos**:
```tsx
const LOGROS = [
  { comp: 'Champions League', fase: 'Campeón',    pts: 18000, weight: 1.0,  color: '#ffdc50' },
  { comp: 'Champions League', fase: 'Semifinal',  pts: 9000,  weight: 1.0,  color: '#ffdc50' },
  { comp: 'Champions League', fase: 'Cuartos',    pts: 5500,  weight: 1.0,  color: '#ffdc50' },
  { comp: 'Liga doméstica',   fase: 'Campeón',    pts: 14000, weight: 0.95, color: '#64a0ff' },
  { comp: 'Liga doméstica',   fase: 'Subcampeón', pts: 5000,  weight: 0.95, color: '#64a0ff' },
  { comp: 'Liga doméstica',   fase: 'Top 4',      pts: 2000,  weight: 0.95, color: '#64a0ff' },
  { comp: 'Europa League',    fase: 'Campeón',    pts: 7000,  weight: 0.75, color: '#ff8c50' },
  { comp: 'Copa Nacional',    fase: 'Campeón',    pts: 6000,  weight: 0.65, color: '#64dcb4' },
]
```

Nota aclaratoria importante a incluir:
> "Los puntos de logro se distribuyen según tu participación real en la temporada. Un jugador que jugó el 80% de los minutos recibe más bonus que uno que jugó el 20%. Los mejores del equipo en rendimiento reciben un multiplicador adicional."

---

### Paso 9 — Sección EJEMPLO (`met-ejemplo`)

**Diseño**: Caja destacada con fondo `var(--surface2)`, borde izquierdo dorado. Un ejemplo concreto de cómo se calcula un gol específico paso a paso.

**Contenido**:
```
Ejemplo: Gol de Lamine Yamal en semifinal de Champions

  Base (EXT · Gol)                    550 pts
  × M1 rival fuerte (Bayern, 82 pts)  × 1.80
  × M2 semifinal Champions            × 1.35
  × M3 minuto 78, empate a 1          × 1.42  (estimado)
  × M4 xG bajo (remate difícil 0.08)  × 1.15
  × Mv (partido de visitante)         × 1.15
  ─────────────────────────────────────────────
  TOTAL                               ≈ 3.200 pts
```

Mostrar como una "cuenta" visual con cada fila siendo una línea de la multiplicación. La última línea con el total en dorado grande.

Nota al pie:
> "Los valores de M3 y M4 son aproximaciones con fines ilustrativos. El cálculo real usa los datos exactos del partido."

---

### Paso 10 — Estilos generales de la página

Agregar al final de `src/index.css`:

```css
/* ══════════════════════════════════════════════
   METODOLOGÍA PAGE
   ══════════════════════════════════════════════ */

.met-page {
  min-height: 100dvh;
  background: var(--bg);
}

.met-section {
  max-width: 1100px;
  margin: 0 auto;
  padding: 100px 48px;
}

.met-eyebrow {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--gold);
  margin-bottom: 16px;
}

.met-section-title {
  font-family: var(--font-display);
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: -0.02em;
  margin-bottom: 48px;
}

.met-section-header {
  margin-bottom: 64px;
}

/* Responsive */
@media (max-width: 768px) {
  .met-section { padding: 60px 24px; }
  .met-concepto__cards { grid-template-columns: 1fr; }
  .met-mult__item { grid-template-columns: 60px 1fr; gap: 24px; }
  .met-formula__display { font-size: 1.2rem; }
}
```

---

## Verificación post-implementación

1. `npm run build` — sin errores de TypeScript
2. `npm run dev` → abrir `http://localhost:5173/metodologia`
3. Verificar:
   - [ ] El hero ocupa toda la pantalla, título entra animado con stagger
   - [ ] Las 3 cards de concepto aparecen al hacer scroll
   - [ ] La fórmula se ve legible, cada factor tiene su color
   - [ ] Los 5 multiplicadores aparecen al hacer scroll, cada uno con su color
   - [ ] La sección de posiciones muestra las 6 posiciones
   - [ ] La sección de logros tiene los bonus correctos (18000 UCL campeón)
   - [ ] El ejemplo de cálculo se entiende de un vistazo
   - [ ] No hay errores en consola
   - [ ] Navbar tiene el link "Metodología"
   - [ ] En mobile (viewport 375px) no hay overflow horizontal

## Prompt para Codex

```
Lee CLAUDE.md y ejecuta el plan en specs/0003-metodologia-page.md.

Reglas:
- Sigue el checklist en orden, marca cada ítem al completarlo
- No reescribas componentes completos — cambios quirúrgicos donde corresponda
- Usa solo pure CSS (sin Tailwind), variables var(--token)
- No instales dependencias nuevas
- Aplica los dials del proyecto: VARIANCE=6, MOTION=4, DENSITY=7
- Sin emojis en la UI
- Al terminar: npm run build debe pasar sin errores de tipo
```
