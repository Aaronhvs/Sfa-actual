# Spec 0004 — Highlights Redesign

> Leer `CLAUDE.md` completo antes de empezar. Aplicar `/high-end-visual-design` + `/design-taste-frontend` (VARIANCE=6, MOTION=4, DENSITY=7) + `/emil-design-eng`.
> 
> **SOLO CSS + cambios mínimos de estructura en el JSX.** No tocar la lógica de cálculo de cards. No cambiar los datos que se calculan.

## Problema actual

1. Grid uniforme 4 columnas — todas las cards tienen el mismo peso, no hay jerarquía
2. `hl-card--accent` usa azul que choca con el gold de marca
3. Las chips están recargadas — demasiados elementos compitiendo
4. El número stat no tiene suficiente presencia tipográfica
5. Todas las cards se ven como recuadros de formulario, no como highlights de una app deportiva

---

## Solución

### Layout: grid asimétrico editorial

```
[ FEATURED — 2 cols, 260px alto ] [ card normal ] [ card normal ]
[ card normal ] [ card normal ] [ card normal ] [ card normal ]
[ card normal ] [ card normal ] [ card normal ] [ card normal ]
```

La card `hl-card--featured` ocupa 2 columnas y tiene más altura. El resto en grid de 4 columnas.

### Estética de card: línea izquierda + número dominante

Eliminar el aspecto de "caja con borde completo". Cada card tiene:
- Fondo muy sutil `rgba(255,255,255,0.03)` — casi negro
- **Border-left** de 2px como único acento de color
- Sin border completo ni border-radius grande (max 2px)
- El número stat ocupa prácticamente toda la card — tipografía agresiva
- Headline pequeño arriba en mono uppercase
- Context en una sola línea truncada abajo — sin chips dentro

### Chips: sacarlas del interior de la card

Mover las chips a dentro de la card pero como un elemento flotante posicionado en la esquina superior derecha, no inline con el contenido. O directamente eliminarlas y fusionar su info en el `context` text.

**Solución más limpia**: eliminar `.hl-card__chips` del JSX de la card normal y dejar solo el tag (esquina). El context text ya tiene la info relevante.

Para la card `--featured`: mantener chips porque tiene más espacio.

---

## Cambios en `HighlightsView.tsx`

### Cambio 1: Estructura de cada card

Cambiar el render del `<article>` para separar mejor las zonas:

```tsx
<article
  key={card.id}
  className={`hl-card hl-card--${card.variant}${card.id === 'best' ? ' hl-card--featured' : ''}${isClickable ? ' hl-card--clickable' : ''}`}
  style={{ animationDelay: `${i * 40}ms` }}
  onClick={isClickable ? () => setModal(card.modal!) : undefined}
  role={isClickable ? 'button' : undefined}
  tabIndex={isClickable ? 0 : undefined}
  onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') setModal(card.modal!) } : undefined}
>
  <div className="hl-card__top">
    <span className="hl-card__headline">{card.headline}</span>
    {card.tag && <span className="hl-card__tag">{card.tag}</span>}
  </div>
  <div className="hl-card__stat">{card.stat}</div>
  <div className="hl-card__bottom">
    {card.id === 'best' && card.chips && card.chips.length > 0 && (
      <div className="hl-card__chips">
        {card.chips.map((chip, ci) => <span key={ci} className="hl-chip">{chip}</span>)}
      </div>
    )}
    <div className="hl-card__context">{card.context}</div>
    {isClickable && <span className="hl-card__cta">Ver todos</span>}
  </div>
</article>
```

> Nota: chips solo se renderizan en la card `best` (featured). En el resto, el context text ya es suficiente.

---

## CSS — reemplazar todos los estilos `.hl-*` en `src/index.css`

Buscar el bloque que empieza con `.hl-grid` o `/* HIGHLIGHTS */` y reemplazarlo íntegro con:

```css
/* ══════════════════════════════════════════════
   HIGHLIGHTS
   ══════════════════════════════════════════════ */

/* Grid asimétrico */
.hl-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 2px;
  background: rgba(255,255,255,0.04);  /* color del gap */
}

/* Card base */
.hl-card {
  background: #111111;
  padding: 24px 22px 20px;
  border-left: 2px solid transparent;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 160px;
  opacity: 0;
  transform: translateY(16px);
  animation: hl-card-in 0.5s cubic-bezier(0.23, 1, 0.32, 1) forwards;
  transition: background 0.15s ease;
  cursor: default;
}

.hl-card--clickable {
  cursor: pointer;
}
.hl-card--clickable:hover {
  background: #161616;
}
.hl-card--clickable:active {
  background: #131313;
  transform: scale(0.995);
}

@keyframes hl-card-in {
  to { opacity: 1; transform: translateY(0); }
}

/* Featured — ocupa 2 columnas y tiene más altura */
.hl-card--featured {
  grid-column: span 2;
  min-height: 220px;
  padding: 32px 28px 24px;
}

/* Variantes de color — solo el border-left cambia */
.hl-card--gold   { border-left-color: var(--gold); }
.hl-card--accent { border-left-color: rgba(255,255,255,0.25); }

/* Top: headline + tag en la misma línea */
.hl-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.hl-card__headline {
  font-family: var(--font-mono);
  font-size: 0.58rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--text-faint);
  line-height: 1.3;
}

/* El número/stat — ocupa el espacio central */
.hl-card__stat {
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 3.5vw, 2.8rem);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
  color: #ffffff;
  flex: 1;
  display: flex;
  align-items: center;
  padding: 8px 0;
}

.hl-card--gold .hl-card__stat { color: var(--gold); }

/* Featured: stat aún más grande */
.hl-card--featured .hl-card__stat {
  font-size: clamp(2.5rem, 5vw, 4rem);
}

/* Bottom: context + CTA */
.hl-card__bottom {
  margin-top: auto;
}

.hl-card__context {
  font-size: 0.72rem;
  color: var(--text-secondary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* En featured el context puede tener 2 líneas */
.hl-card--featured .hl-card__context {
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* CTA link */
.hl-card__cta {
  display: inline-block;
  margin-top: 8px;
  font-family: var(--font-mono);
  font-size: 0.58rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--gold);
  opacity: 0.7;
  transition: opacity 0.15s;
}
.hl-card--clickable:hover .hl-card__cta { opacity: 1; }

/* Tag — esquina superior derecha dentro del top */
.hl-card__tag {
  font-family: var(--font-mono);
  font-size: 0.52rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 3px 7px;
  background: rgba(201,168,76,0.12);
  color: var(--gold);
  border-radius: 2px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* Chips — solo en featured */
.hl-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.hl-chip {
  font-family: var(--font-mono);
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 3px 8px;
  background: rgba(255,255,255,0.06);
  color: var(--text-secondary);
  border-radius: 2px;
}

/* ── Responsive ──────────────────────────────── */
@media (max-width: 1024px) {
  .hl-grid { grid-template-columns: repeat(3, 1fr); }
  .hl-card--featured { grid-column: span 2; }
}

@media (max-width: 640px) {
  .hl-grid { grid-template-columns: repeat(2, 1fr); }
  .hl-card--featured { grid-column: span 2; }
  .hl-card { min-height: 130px; padding: 18px 16px 14px; }
}
```

---

## Verificación

1. `npm run build` — sin errores de TypeScript
2. `npm run dev` → abrir un perfil de jugador → tab Highlights
3. Verificar:
   - [ ] La card "MEJOR ACTUACIÓN" ocupa 2 columnas y es más alta
   - [ ] El número stat es grande y legible en todas las cards
   - [ ] El border-left dorado se ve en las cards gold
   - [ ] Las cards accent tienen border-left gris/blanco sutil
   - [ ] Solo la card featured muestra chips internas
   - [ ] Cada card tiene headline (mono pequeño) arriba y context truncado abajo
   - [ ] Las cards clickables tienen hover visible
   - [ ] En mobile (640px) el grid cae a 2 columnas
   - [ ] Las animaciones de entrada son fluidas con stagger

## Prompt para Codex

```
Lee CLAUDE.md y ejecuta el plan en specs/0004-highlights-redesign.md.

Reglas:
- Los cambios de lógica de datos en HighlightsView.tsx son mínimos — solo la estructura del JSX del render
- NO tocar ninguna función de cálculo (useMemo, goalCount, etc.)
- Reemplazar íntegro el bloque CSS de highlights en index.css
- Pure CSS, var(--token), sin librerías nuevas
- Al terminar: npm run build debe pasar sin errores de tipo
```
