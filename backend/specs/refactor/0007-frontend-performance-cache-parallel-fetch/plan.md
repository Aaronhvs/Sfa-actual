# Plan: Frontend Performance — Caché Cliente + Parallel Fetch + Pre-grouping

## Archivos a modificar

- [ ] `frontend/src/api/client.ts` — agregar caché de módulo con TTL para todas las funciones de fetch
- [ ] `frontend/src/pages/RankingPage.tsx` — desacoplar estado de ranking y showcase; parallel fetch
- [ ] `frontend/src/components/player/FixtureList.tsx` — pre-agrupar eventos por fixture_id con useMemo
- [ ] `frontend/src/components/ranking/ShowcaseCard.tsx` — skeleton propio cuando `detail` es null

## Checklist de implementación

### Task 1 — Caché de módulo en client.ts

- [ ] Declarar `const _cache = new Map<string, { data: unknown; ts: number }>()` al nivel de módulo
- [ ] Declarar `const TTL_MS = 60_000`
- [ ] Crear helper interno `getCached<T>(key: string): T | null` que retorna null si expirado o ausente
- [ ] Crear helper interno `setCache(key: string, data: unknown): void`
- [ ] Envolver `fetchPlayer` con caché usando key `player:{id}:{season}`
- [ ] Envolver `fetchPlayerFixtures` con caché usando key `fixtures:{id}:{season}`
- [ ] Envolver `fetchPlayerEvents` con caché usando key `events:{id}:{season}`
- [ ] Envolver `fetchRanking` con caché usando key `ranking:{season}:{position}:{competition_id}`
- [ ] Verificar que en segunda llamada con mismos parámetros no sale ningún request de red (Network tab)

### Task 2 — Parallel fetch en RankingPage

- [ ] Separar en dos estados independientes: `loadingRanking` y `loadingShowcase`
- [ ] Al montar: disparar `fetchRanking` inmediatamente
- [ ] Cuando `fetchRanking` resuelve: setear `players` y `loadingRanking = false` sin esperar el showcase
- [ ] Disparar los 3 `fetchPlayer` en paralelo con `Promise.allSettled` inmediatamente después de obtener `players`
- [ ] Cuando los 3 `fetchPlayer` resuelven: setear `topDetails` y `loadingShowcase = false`
- [ ] La tabla de ranking usa `loadingRanking` para su skeleton — no bloquea en `loadingShowcase`
- [ ] `ShowcaseCard` recibe `detail={null}` mientras `loadingShowcase` es true — muestra su propio skeleton
- [ ] Verificar en Network tab que ranking y los 3 fetchPlayer salen en el mismo tick

### Task 3 — Pre-grouping en FixtureList

- [ ] Agregar `useMemo` que construye `Map<number, PlayerEvent[]>` a partir de `events` agrupando por `fixture_id`
- [ ] Cambiar la prop que recibe `FixtureRow` de `events: PlayerEvent[]` a `events: PlayerEvent[]` (los eventos ya filtrados para ese fixture)
- [ ] En `FixtureList.filtered.map(...)` pasar `events={eventsByFixture.get(f.fixture_id) ?? []}` a cada `FixtureRow`
- [ ] Eliminar el filtrado interno de `FixtureRow` si lo tiene, o asegurar que ya recibe solo sus eventos
- [ ] Verificar en React DevTools que `FixtureRow` no hace iteraciones sobre todos los eventos

### Task 4 — Skeleton propio en ShowcaseCard

- [ ] Cuando `detail === null`, renderizar skeleton interno con las mismas dimensiones que el card real
- [ ] El skeleton no debe causar layout shift al resolverse
- [ ] Verificar que el showcase se ve en "loading" mientras la tabla ya muestra jugadores

## Agent Routing Brief

**DDD Designer needed:** no

Refactor puramente frontend. No hay nuevas entidades de dominio, value objects ni cambios al
modelo de scoring. Los cambios son en capa de presentación y data fetching del cliente.

## Verificación

1. Abrir DevTools → Network → cargar `/ranking` → verificar que la tabla aparece antes que el showcase
2. Navegar a un jugador → volver al ranking → volver al mismo jugador → verificar en Network que **no** salen nuevas requests (caché hit)
3. Abrir perfil de un jugador con muchos partidos → abrir React DevTools Profiler → verificar que `FixtureRow` no re-renderiza al filtrar fixtures
4. Esperar 61 segundos → navegar a la misma página → verificar que salen nuevas requests (TTL expirado)
