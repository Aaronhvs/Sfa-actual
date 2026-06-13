# Spec 0007 - Mundial 2026 Festival Visual Refresh

## Estado

Implementado y verificado el 13 de junio de 2026.

Este spec mejora la identidad visual ya creada en el spec 0006. No cambia datos,
ranking, rutas, algoritmo ni detección de temporada. El backend ya devuelve
`is_world_cup: true` para 2026 y esa señal sigue siendo la única fuente de verdad.

---

## Skills aplicados

| Área | Skills |
|---|---|
| Auditoría de la UI existente | `design-taste-frontend` + `redesign-existing-projects` |
| Dirección visual y composición | `high-end-visual-design` |
| Paleta y convivencia con SFA | `brand` |
| Movimiento e interacción | `emil-design-eng` |
| Accesibilidad y responsive | `ui-ux-pro-max` |

Dials SFA:

- `DESIGN_VARIANCE: 6`
- `MOTION_INTENSITY: 4`
- `VISUAL_DENSITY: 7`

---

## Diagnóstico

La edición Mundial actual ya se distingue del ranking de clubes, pero la identidad
queda concentrada en `WorldCupPageHeader`. Después del encabezado, la experiencia
regresa casi por completo a las superficies negras y al dorado habitual de SFA.

Problemas concretos:

1. El gradiente rojo, azul y verde del header tiene poca saturación y desaparece al
   comenzar el contenido.
2. El podio y las tarjetas del ranking no tienen una variante visual propia del
   torneo.
3. El selector indica "Mundial", pero no transmite claramente el cambio de edición.
4. El perfil del jugador solo incorpora una etiqueta de selección; no continúa la
   atmósfera del ranking.
5. No existe un ritmo gráfico compartido entre header, secciones, tarjetas,
   paginación y estados de carga.
6. El color de torneo compite conceptualmente con `--gold`, aunque el dorado SFA debe
   seguir reservado para puntos y posición.

---

## Referencia y traducción propia

La identidad oficial de 2026 enfatiza:

- tres países anfitriones;
- diversidad de ciudades y culturas;
- rojo, verde y azul como familia cromática reconocible;
- patrones, carteles y composiciones distintas por ciudad;
- una sensación de festival colectivo, no una única identidad corporativa plana.

SFA no copiará el emblema, los carteles, el trofeo ni los patrones oficiales. La
traducción propia será **Festival nocturno de datos**:

- la noche y precisión editorial siguen perteneciendo a SFA;
- el torneo introduce bloques de color alegres, ritmos diagonales y transiciones
  breves;
- las fotos, escudos y datos mantienen el protagonismo;
- el dorado SFA conserva su significado exclusivo.

---

## Principios de la dirección

### 1. Color distribuido, no color concentrado

La identidad debe sentirse desde el encabezado hasta la paginación. El color aparece
en bordes, bandas, fondos recortados y estados interactivos, no como un gradiente
lavado sobre toda la pantalla.

### 2. Base oscura, energía alta

La página continúa siendo dark-only. La proporción visual objetivo es:

- 68% fondos nocturnos;
- 22% color de torneo;
- 10% texto, escudos y datos destacados.

### 3. El dorado sigue siendo dato

`--gold` y `--gold-light` solo representan puntos SFA, ranking y posición. Ninguna
decoración del Mundial debe usar esos tokens.

### 4. Sistema cromático controlado

Los colores del torneo no se asignan al azar por jugador o selección. Cada color
tiene un papel estable:

- rojo: competencia y acción;
- azul: estructura, navegación y profundidad;
- verde: cancha, clasificación y progreso;
- amarillo solar: celebración y edición especial, nunca puntos SFA.

### 5. Sin ruido de transmisión

No se añadirán marcadores, resultados, partidos "en vivo" ni datos ficticios. Un
ticker real queda fuera de alcance hasta disponer de un endpoint y estados fiables.

---

## Paleta propuesta

Mantener todos los tokens base y reemplazar la capa `--tm-*` por una familia más
clara y alegre:

```css
--tm-bg: #0B1010;
--tm-surface: #121918;
--tm-surface2: #18211F;

--tm-red: #F04B3F;
--tm-blue: #3978F6;
--tm-green: #20A866;
--tm-sun: #FFC83D;
--tm-sky: #54C6E8;

--tm-text: #FFFFFF;
--tm-text-dim: #A7B3AF;
--tm-border: rgba(255, 255, 255, 0.09);
--tm-ease: cubic-bezier(0.23, 1, 0.32, 1);
```

Reglas:

- retirar `--tm-gold` para evitar confusión semántica con `--gold`;
- usar `--tm-sun` para la edición especial y celebración;
- comprobar contraste AA en textos y controles;
- usar texto oscuro sobre `--tm-sun` y texto blanco sobre rojo, azul y verde;
- no usar color como único indicador de selección, rango o estado.

---

## Sistema gráfico

### Tournament Spectrum

Crear una secuencia visual reutilizable:

```css
linear-gradient(
  90deg,
  var(--tm-red) 0 25%,
  var(--tm-sun) 25% 43%,
  var(--tm-green) 43% 68%,
  var(--tm-blue) 68% 100%
)
```

No se aplicará como fondo completo. Se usará en:

- una banda de 4px del header;
- la guía activa del selector;
- el borde superior del podio;
- separadores de sección;
- la paginación activa;
- estados skeleton del torneo a opacidad reducida.

### Formas

La forma propia de SFA Mundial será un bloque rectangular recortado:

```css
clip-path: polygon(0 0, 100% 0, 94% 100%, 0 100%);
```

Uso limitado a fondos decorativos, labels grandes y marcas de agua. Los controles
interactivos conservan hit areas rectangulares y accesibles.

### Textura

Sustituir la trama diagonal uniforme actual por dos capas:

1. cuadrícula técnica muy tenue;
2. dos bloques cromáticos recortados y desenfocados solo con opacidad, sin glow.

No añadir imágenes nuevas ni ruido raster en esta fase.

---

## Alcance por componente

### 1. `src/index.css`

- [x] Reemplazar la paleta `--tm-*` conforme a este spec.
- [x] Eliminar usos decorativos de `--tm-gold` y migrarlos a `--tm-sun`.
- [x] Definir `--tm-spectrum`.
- [x] Crear reglas de atmósfera para `body.mode-tournament` con fondos radiales
      estáticos y de baja opacidad.
- [x] Crear variantes de torneo solo bajo `.mode-tournament` para impedir cambios
      en temporadas de clubes.
- [x] Mantener radios máximos de 6px y las tipografías existentes.

### 2. `src/components/shared/WorldCupPageHeader.tsx`

No reescribir el componente completo. Extender su estructura actual.

- [x] Añadir una banda `wc-page-header__spectrum` decorativa con `aria-hidden`.
- [x] Convertir el layout en dos zonas asimétricas:
      título e información a la izquierda, sello "48 selecciones / edición 2026"
      a la derecha.
- [x] Mantener el número real de jugadores recibido por props.
- [x] Añadir una línea breve: `Ranking independiente del torneo`.
- [x] No usar logotipos, emblemas ni nombres comerciales de FIFA.
- [x] Evitar que el header supere aproximadamente 260px de alto en desktop.

### 3. Selector de temporada

Archivos:

- `src/components/shared/SeasonDropdown.tsx`
- `src/components/shared/SeasonSelector.tsx`

- [x] Cuando la selección activa sea Mundial, usar una guía spectrum de 3px.
- [x] Mantener el texto `Mundial 2026` y el badge textual `Torneo`.
- [x] Hacer que el cambio desde clubes a Mundial tenga una transición de color y
      opacidad de 180-220ms.
- [x] Mantener navegación por teclado, foco visible y `aria-selected`.
- [x] No animar las acciones de teclado.

### 4. Podio

Archivos:

- `src/components/ranking/ShowcaseCard.tsx`
- `src/pages/RankingPage.tsx`

- [x] Pasar una prop explícita `isWorldCup` a `ShowcaseCard`.
- [x] Añadir una variante `player-showcase-card--wc` sin alterar el podio normal.
- [x] Usar un borde superior spectrum común para unir visualmente las tres tarjetas.
- [x] Dar a cada puesto un bloque cromático estable:
      primero `--tm-sun`, segundo `--tm-blue`, tercero `--tm-green`.
- [x] Mantener puntos y número de posición en `--gold`.
- [x] Reforzar el escudo de selección con un fondo oscuro y borde neutro.
- [x] Mostrar el nombre de la selección junto al escudo cuando el ancho lo permita.
- [x] En móvil, conservar el orden 1, 2, 3 y evitar scroll horizontal.

### 5. Clasificación completa

Archivos:

- `src/components/ranking/RankingCard.tsx`
- `src/pages/RankingPage.tsx`

- [x] Pasar `isWorldCup` a `RankingCard`.
- [x] Crear una variante de torneo con una banda lateral spectrum de 3px.
- [x] Usar `--tm-green` para el badge de rol/posición, sin reemplazar el dorado de
      los puntos.
- [x] Aumentar la presencia del escudo de selección a 28-30px.
- [x] Mostrar el nombre de la selección como metadata cuando exista espacio.
- [x] Aplicar hover mediante `translateY(-2px)`, cambio de borde y aumento leve de
      saturación de la foto.
- [x] Mantener las tarjetas legibles sin depender del hover.

### 6. Encabezados y ritmo de secciones

Archivo:

- `src/pages/RankingPage.tsx`

- [x] Añadir una clase de torneo a `rp-podium`, `rp-table-section` y
      `rp-ranking-head`.
- [x] Sustituir la línea dorada decorativa de los títulos de sección por un
      separador spectrum solo en modo Mundial.
- [x] Mantener `--gold` dentro de cifras y posiciones.
- [x] Añadir la etiqueta `Edición Mundial` sobre `Todos los jugadores`.
- [x] Conservar filtros ocultos en Mundial según el comportamiento actual.

### 7. Paginación

- [x] Crear variante `.mode-tournament .ranking-pagination`.
- [x] Usar `--tm-blue` para foco/navegación y spectrum para la página activa.
- [x] Mantener botones anterior/siguiente próximos y con hit area mínima de 44px.
- [x] Aplicar `scale(0.97)` al presionar.
- [x] No cambiar la lógica, cantidad de páginas ni URLs.

### 8. Perfil del jugador

Archivos:

- `src/pages/PlayerPage.tsx`
- componentes de perfil ya existentes, solo mediante props/clases cuando sea
  necesario.

- [x] Extender `pp-national-badge` con spectrum y `--tm-sun`, sin `--tm-gold`.
- [x] Añadir una banda cromática al header del jugador en modo Mundial.
- [x] Usar separadores spectrum en `Estadísticas técnicas`,
      `Rendimiento por partido` y `Trofeos`.
- [x] Mantener todos los puntos SFA en dorado.
- [x] Aplicar el color del torneo a tooltips y selección de partido, no a la línea
      de datos principal si reduce su legibilidad.
- [x] No modificar cálculos, eventos, fixtures ni contratos de API.

### 9. Estados de carga, vacío y error

- [x] Crear skeletons de torneo con una banda spectrum tenue y sin animación
      perpetua intensa.
- [x] Añadir contexto `Mundial 2026` al estado vacío.
- [x] Mantener mensajes precisos y sin tono promocional.
- [x] Verificar que el error sigue siendo legible sobre `--tm-bg`.

---

## Motion spec

Todas las animaciones deben usar `transform` y `opacity`.

### Entrada de página

- header: 240ms, `translateY(6px)` a `0`, opacidad `0` a `1`;
- spectrum: 280ms, `scaleX(0.92)` a `1`, origen izquierdo;
- podio: stagger de 45ms, máximo total 320ms;
- ranking: conservar stagger actual de 45ms.

### Interacción

- selector: 200ms;
- hover de tarjeta: 180ms;
- press de botón/tarjeta: `scale(0.97)`, 100ms;
- cambio de temporada: crossfade 180ms, sin blur superior a 1px.

### Reduced motion

Con `prefers-reduced-motion: reduce`:

- eliminar stagger, desplazamientos y escalas;
- conservar solo cambios instantáneos de color, borde y opacidad;
- ningún contenido debe depender de una animación para aparecer.

---

## Responsive

### Desktop, 1200px o más

- header asimétrico de dos zonas;
- podio conserva composición principal;
- selector alineado con el borde derecho del contenido;
- color visible en al menos cuatro puntos del viewport inicial.

### Tablet, 768-1199px

- el sello informativo baja bajo el título;
- el spectrum no se corta ni genera overflow;
- tarjetas conservan escudo y nombre de selección.

### Mobile, 320-767px

- header de una columna;
- título máximo de dos líneas;
- sello reducido a una fila de metadata;
- selector ocupa 100%;
- controles de 44px como mínimo;
- color presente sin sacrificar contraste ni espacio para datos.

---

## Fuera de alcance

- cambios de backend o algoritmo;
- integración de partidos en vivo;
- ticker de resultados;
- colores automáticos por bandera o selección;
- assets oficiales, trofeo, emblema o mascotas;
- Tailwind, styled-components o librerías de animación;
- nuevas fuentes;
- rediseño de temporadas de clubes.

---

## Orden de implementación recomendado

### Fase 1 - Identidad base

- [x] Ítems 1-5 de `src/index.css`.
- [x] Header y selector.
- [x] Capturas desktop y mobile para aprobar la dirección antes de continuar.

### Fase 2 - Ranking

- [x] Podio.
- [x] Clasificación completa.
- [x] Encabezados y paginación.
- [x] Estados de carga, vacío y error.

### Fase 3 - Perfil y polish

- [x] Perfil del jugador.
- [x] Motion final.
- [x] Responsive y accesibilidad.
- [x] Limpieza de reglas antiguas de torneo que queden sin uso.

---

## Criterios de aceptación

- [x] El Mundial se reconoce visualmente aun cuando el header no está visible.
- [x] El color aparece en header, selector, podio, ranking y paginación.
- [x] `--gold` continúa reservado a puntos SFA y posición.
- [x] La temporada 2025/26 y el total histórico no cambian visualmente.
- [x] No se usan datos ficticios ni recursos oficiales protegidos.
- [x] El diseño funciona a 320px, 768px, 1200px y 1440px.
- [x] Todos los controles tienen foco visible y hit area mínima de 44px.
- [x] La experiencia es completa con `prefers-reduced-motion`.
- [x] No se instala ninguna dependencia.
- [x] `npm run build` termina sin errores TypeScript.

---

## Resultado esperado

La página debe seguir sintiéndose como SFA: oscura, editorial y centrada en datos.
La diferencia es que el Mundial ya no será un banner colocado encima del ranking,
sino una edición reconocible en toda la experiencia: más plural, más luminosa y más
celebratoria, sin perder precisión ni convertir el producto en una transmisión
televisiva.
