# Frontend Performance: Caché Cliente + Parallel Fetch + Pre-grouping

## Contexto de negocio

El frontend de SFA muestra lentitud perceptible al navegar entre páginas y cargar perfiles de
jugadores. La API responde en < 300ms, por lo que el problema es puramente del lado cliente:
peticiones en cascada (waterfall), re-fetching innecesario en cada navegación y trabajo
computacional redundante en el render de FixtureList.

El impacto es directo en la experiencia de uso: el ranking, que es la pantalla principal, no
muestra nada hasta que completan 4 batches de requests secuenciales; navegar de vuelta a un
jugador ya visitado es igual de lento que la primera vez.

## Restricciones

- Sin librerías externas de data fetching (no SWR, no React Query, no Zustand)
- Sin cambios al backend — es refactor exclusivamente frontend
- Las animaciones CSS existentes no deben romperse
- El skeleton de loading debe seguir funcionando correctamente

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Caché de módulo en `client.ts` (Map + TTL) | React Context / useReducer | Sin re-renders innecesarios; no necesita coordinación cross-component compleja |
| TTL de 60 segundos | Sin TTL / TTL por ruta | Los datos de una sesión de navegación no cambian; 60s cubre múltiples idas y vueltas |
| Desacoplar ranking de showcase con `useState` separados | Un único `loading` booleano | Permite mostrar la tabla inmediatamente; showcase carga en paralelo con su propio skeleton |
| `useMemo` para pre-agrupar eventos en `FixtureList` | Filtrar en cada `FixtureRow` | Reduce de O(n×m) a O(n+m); el agrupado ocurre una sola vez al montar el componente |
| Skeleton propio en `ShowcaseCard` | Ocultar showcase hasta que cargue | Mejor percepción de velocidad; la tabla ya es útil mientras el showcase termina |

## Integraciones externas

Ninguna. Refactor puramente interno al frontend.
