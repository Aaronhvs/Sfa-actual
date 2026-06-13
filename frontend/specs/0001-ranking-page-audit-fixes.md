# Spec 0001 — RankingPage: fixes del audit de diseño

> Ejecutar en orden. No saltear ningún ítem. No reescribir componentes completos — mejoras quirúrgicas sobre el código existente.

## Contexto

Stack: React 18 + TypeScript + Vite + pure CSS (sin Tailwind). Las clases CSS viven en `src/index.css`. Variables en `:root`. El skill activo es `/design-taste-frontend` con dials VARIANCE=6, MOTION=4, DENSITY=7.

Leer antes de empezar:
- `frontend/CLAUDE.md` — convenciones del proyecto
- `frontend/src/index.css` — tokens CSS existentes

---

## Checklist de implementación

### Fix 1 — Em-dash en subtítulo del header (pre-flight fail)
**Archivo:** `src/pages/RankingPage.tsx` línea 152

Cambiar:
```tsx
"Clasificación por puntuación de impacto real — rival, competición, momento y dificultad"
```
Por:
```tsx
"Clasificación por puntuación de impacto real: rival, competición, momento y dificultad"
```

---

### Fix 2 — Agregar MCO al FilterBar
**Archivo:** `src/components/ranking/FilterBar.tsx` línea 3–9

Agregar MCO a la lista de posiciones:
```tsx
const POSITIONS: { value: string; label: string }[] = [
  { value: 'DEL', label: 'Delantero' },
  { value: 'EXT', label: 'Extremo' },
  { value: 'MCO', label: 'MC Ofensivo' },
  { value: 'MC',  label: 'Mediocampista' },
  { value: 'DC',  label: 'Def. Central' },
  { value: 'LAT', label: 'Lateral' },
]
```

---

### Fix 3 — Eliminar redundancia de rank en ShowcaseCard
**Archivo:** `src/components/ranking/ShowcaseCard.tsx`

El rank aparece 3 veces: `psc-rank-watermark`, `psc-medal` y dentro de `psc-content > psc-rank`.
Eliminar el bloque `psc-medal` (líneas 41–44) — el watermark ya hace el trabajo estético y el texto en `psc-content` da la información:

```tsx
// ELIMINAR estas líneas:
<div className="psc-medal">
  <span className="psc-medal-lbl">RANK</span>
  <span className="psc-medal-num">{String(player.rank).padStart(2, '0')}</span>
</div>
```

---

### Fix 4 — tabular-nums en números del ranking
**Archivo:** `src/index.css`

Buscar las clases que renderizan puntos SFA y números de ranking y agregarles `font-variant-numeric: tabular-nums`. Las clases a modificar son:
- `.rc-stat-val` (RankingCard)
- `.psc-stat-val` (ShowcaseCard)
- `.ranking-row__pts` (RankingRow)
- `.rc-rank` (RankingCard rank badge)
- `.psc-rank-watermark` (ShowcaseCard watermark)

Para cada una, agregar dentro de su bloque CSS:
```css
font-variant-numeric: tabular-nums;
```

---

### Fix 5 — Scroll horizontal en FilterBar de competiciones (responsive)
**Archivo:** `src/index.css`

Buscar la clase `.filter-bar__group--comp` y asegurarse de que tenga scroll horizontal en lugar de wrapping:

```css
.filter-bar__group--comp {
  overflow-x: auto;
  flex-wrap: nowrap;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none; /* Firefox */
}

.filter-bar__group--comp::-webkit-scrollbar {
  display: none; /* Chrome/Safari */
}
```

Si la clase no existe con estas propiedades, agregarlas. Si existe, reemplazar solo lo que corresponde al overflow/wrap.

---

### Fix 6 — H1 con `<br>` hardcoded
**Archivo:** `src/pages/RankingPage.tsx` línea 150 y `src/index.css`

En el JSX, cambiar:
```tsx
<h1 className="rp-header__title">Ranking<br />Global</h1>
```
Por:
```tsx
<h1 className="rp-header__title">Ranking Global</h1>
```

En `src/index.css`, buscar `.rp-header__title` y agregar para controlar el salto de línea visualmente si se desea:
```css
.rp-header__title {
  /* existente... */
  word-break: break-word; /* o agregar max-width si quieres el break natural */
}
```

---

### Fix 7 — Stat contextual en RankingCard por posición
**Archivo:** `src/components/ranking/RankingCard.tsx`

Actualmente muestra siempre GOL y AST. Para posiciones defensivas (DC, LAT) esto siempre es 0 o muy bajo y no aporta información. Sin embargo, el tipo `RankedPlayer` puede no tener stats adicionales disponibles. 

**Solo si el tipo `RankedPlayer` en `src/types/index.ts` incluye stats adicionales** (verificar antes de implementar):
- DC/LAT: mostrar `matches_played` en lugar de goles
- MC/MCO: mantener goles + asistencias

**Si `RankedPlayer` no tiene `matches_played`**: dejar este fix pendiente y agregar un TODO comment en `RankingCard.tsx`:
```tsx
// TODO: mostrar stat contextual por posición cuando API exponga matches_played en ranking
```

---

## Verificación post-implementación

Después de todos los fixes:

1. Arrancar el frontend: `npm run dev` (desde PowerShell Windows, no WSL)
2. Verificar en `http://localhost:5173`:
   - [ ] Subtítulo sin em-dash
   - [ ] FilterBar tiene "MC Ofensivo" como opción
   - [ ] ShowcaseCard: sin badge de medal redundante
   - [ ] Números de puntos alineados uniformemente al cambiar de página
   - [ ] Filtro de competiciones hace scroll horizontal sin wrapping en pantalla media (~768px)
   - [ ] H1 dice "Ranking Global" en una línea o con break natural según el font-size

3. No debe haber errores de TypeScript (`npm run build` debe pasar sin errores de tipo).
