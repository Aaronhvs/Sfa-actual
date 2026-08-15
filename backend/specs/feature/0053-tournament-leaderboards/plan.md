# Plan: Lideres estadisticos en torneos

## Archivos a crear

- [x] `frontend/src/components/tournaments/TournamentLeaders.tsx` - banda reutilizable de tres
  columnas con goleadores, asistidores y carrusel posicional.

## Archivos a modificar

- [x] `frontend/src/pages/TournamentsPage.tsx` - integrar el bloque global bajo el dashboard.
- [x] `frontend/src/pages/TournamentDetailPage.tsx` - integrar el bloque filtrado bajo el contenido.
- [x] `frontend/src/index.css` - estilos de banda, filas, controles, carga y responsive.

## Checklist de implementacion

- [x] Cargar en paralelo goleadores, asistidores y rankings por posicion con `fetchRanking`.
- [x] Aislar errores por consulta y conservar las columnas que si respondan.
- [x] Mostrar foto, nombre, club, escudo, posicion ordinal y valor principal por jugador.
- [x] Rotar las posiciones disponibles cada 2000 ms.
- [x] Agregar flechas pequenas con nombres accesibles y reinicio natural del intervalo.
- [x] Pausar la rotacion durante hover o foco y respetar `prefers-reduced-motion`.
- [x] Integrar la variante global en `/torneos` con el scope de la temporada resuelta.
- [x] Integrar la variante por competicion en `/torneos/:competitionId`.
- [x] Agregar estados de carga y vacio que no cambien la altura de la banda.
- [x] Adaptar de tres columnas a una lista vertical en movil sin overflow horizontal.
- [x] Verificar TypeScript y build de Vite.
- [x] Verificar visualmente escritorio y movil con Playwright.

## Agent Routing Brief

**DDD Designer needed:** no

La funcionalidad compone filtros y ordenes ya soportados por el read model de ranking. No modifica
el scoring, la persistencia ni las invariantes del dominio.

## Verificacion

1. Abrir `/torneos` y confirmar que el bloque global muestra tres goleadores, tres asistidores y
   una posicion que cambia cada dos segundos.
2. Abrir un torneo y confirmar que todos los jugadores del bloque pertenecen a esa competicion.
3. Usar ambas flechas y confirmar navegacion circular sin desplazamiento del layout.
4. Comprobar estado parcial cuando una posicion no tenga jugadores.
5. Ejecutar `npm run build` y validar 1280px, 768px y 390px sin overflow.
