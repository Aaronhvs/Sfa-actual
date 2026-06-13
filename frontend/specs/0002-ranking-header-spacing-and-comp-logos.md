# Spec 0002 — Header spacing + competition filter con logos

> Cambios quirúrgicos. No reescribir componentes completos. Leer CLAUDE.md antes de empezar.

## Contexto

Stack: React 18 + TypeScript + Vite + pure CSS. Sin Tailwind. Variables en `var(--token)`.
Imágenes de ligas: CDN API-Football → `https://media.api-sports.io/football/leagues/{id}.png`

---

## Cambio 1 — Reducir el espacio entre navbar y contenido del header

### Problema
La zona entre la navbar fija y el primer contenido visible (logo STA + "TEMPORADA 2024") tiene demasiado espacio vertical. El bloque `.rp-brand` (logo de 72px + 28px margin-bottom) más el padding del header hacen que el showcase de jugadores quede muy abajo.

### Archivos a modificar: `src/index.css`

**1a. Reducir padding del `.rp-header`** (línea ~1789):
```css
/* Antes: */
.rp-header {
  padding: 28px 48px 16px;
}

/* Después: */
.rp-header {
  padding: 12px 48px 12px;
}
```

**1b. Reducir tamaño del logo de marca** (línea ~1806):
```css
/* Antes: */
.rp-brand__logo {
  height: 72px;
}

/* Después: */
.rp-brand__logo {
  height: 44px;
}
```

**1c. Reducir margin-bottom del `.rp-brand`** (línea ~1797):
```css
/* Antes: */
.rp-brand {
  margin-bottom: 28px;
}

/* Después: */
.rp-brand {
  margin-bottom: 16px;
}
```

**1d. Verificar el responsive** — buscar el bloque `@media` que sobreescribe `.rp-header` (línea ~2480) y ajustar también:
```css
/* Antes: */
.rp-header { padding: 36px 24px 28px; }

/* Después: */
.rp-header { padding: 12px 24px 10px; }
```

---

## Cambio 2 — Competition filter: solo ligas principales con logos

### Problema
El filtro de competiciones muestra todas las ligas como botones de texto. El usuario quiere ver solo las 5 ligas grandes + Champions League + Global, con sus logos en lugar de texto.

### Lógica de filtrado

Mantener en el filtro SOLO estas competiciones (por ID):

| ID | Competición |
|----|-------------|
| —  | Global (sin id) |
| 10 | UEFA Champions League |
| 1  | La Liga |
| 3  | Premier League |
| 6  | Bundesliga |
| 7  | Serie A |
| 9  | Ligue 1 |

Todo lo demás (Europa League, Conference League, copas nacionales, etc.) se elimina del filtro.

### Archivo: `src/pages/RankingPage.tsx`

Reemplazar la lógica de `mainCompetitions` (líneas ~118–121) con un filtro por ID:

```tsx
const MAIN_COMPETITION_IDS = [10, 1, 3, 6, 7, 9]

const mainCompetitions = competitions
  .filter((c) => MAIN_COMPETITION_IDS.includes(c.id))
  .sort((a, b) => MAIN_COMPETITION_IDS.indexOf(a.id) - MAIN_COMPETITION_IDS.indexOf(b.id))
```

Eliminar la variable `CUP_KEYWORDS` — ya no se usa.

### Archivo: `src/components/ranking/FilterBar.tsx`

**2a. Agregar helper de logo** — encima del componente:

```tsx
const COMP_LOGO_URL: Record<number, string> = {
  10: 'https://media.api-sports.io/football/leagues/2.png',   // UCL (API id=2 para logo)
  1:  'https://media.api-sports.io/football/leagues/140.png', // La Liga
  3:  'https://media.api-sports.io/football/leagues/39.png',  // Premier League
  6:  'https://media.api-sports.io/football/leagues/78.png',  // Bundesliga
  7:  'https://media.api-sports.io/football/leagues/135.png', // Serie A
  9:  'https://media.api-sports.io/football/leagues/61.png',  // Ligue 1
}
```

> IMPORTANTE: Los IDs en el CDN de API-Football para logos son distintos a los IDs internos de SFA.
> Verificar estas URLs cargando cada imagen en el navegador antes de confirmar que son correctas.
> Si alguna URL no carga, usar el ID interno de SFA directamente:
> `https://media.api-sports.io/football/leagues/{competition.id}.png`

**2b. Reemplazar los botones de competición** — los botones del grupo `--comp` deben mostrar logo + nombre corto:

```tsx
{competitions.map((c) => {
  const logoUrl = COMP_LOGO_URL[c.id]
  return (
    <button
      key={c.id}
      className={`filter-btn filter-btn--comp filter-btn--logo${competition === c.id ? ' filter-btn--active' : ''}`}
      onClick={() => onCompetition(c.id)}
      title={c.name}
    >
      {logoUrl && (
        <img
          src={logoUrl}
          alt=""
          className="filter-btn__logo"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
      )}
      <span className="filter-btn__label">{c.name}</span>
    </button>
  )
})}
```

**2c. CSS nuevo en `src/index.css`** — agregar después de los estilos existentes de `.filter-btn`:

```css
.filter-btn--logo {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 6px 8px;
}

.filter-btn__logo {
  width: 20px;
  height: 20px;
  object-fit: contain;
  flex-shrink: 0;
}

.filter-btn__label {
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}
```

---

## Verificación post-implementación

1. `npm run build` — sin errores de tipo
2. `npm run dev` → `http://localhost:5173`
3. Verificar visualmente:
   - [ ] El espacio entre navbar y el showcase de jugadores es notablemente menor
   - [ ] El logo STA en el header es más pequeño y compacto
   - [ ] El filtro de competiciones muestra solo 6 opciones + Global
   - [ ] Cada competición muestra su logo
   - [ ] Si un logo no carga, la imagen se oculta y solo queda el texto
   - [ ] El orden en el filtro es: Global → UCL → La Liga → Premier → Bundesliga → Serie A → Ligue 1
