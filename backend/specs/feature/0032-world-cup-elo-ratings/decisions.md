# World Cup ELO Ratings

## Contexto de negocio

El scoring actual calcula la dificultad del rival (M1) desde `team_strengths.strength`
cuando existen strengths para ambos equipos del fixture. Para clubes, esas strengths pueden
venir de ELO (`clubelo_seed` o `elo_v1`). Para el Mundial, las selecciones no están cubiertas
por ClubElo, por lo que el sistema puede caer al fallback de posiciones de standings del
torneo. Ese fallback es débil para fase de grupos y especialmente inestable antes de que haya
suficientes partidos jugados.

La página del Mundial ya está en producción en un VPS. El fix debe poder desplegarse sin
romper el sitio, poblar strengths de selecciones, auditar que todos los equipos mundialistas
tienen strength, y luego lanzar un recálculo de scores para `season='2026'` y la competición
World Cup.

## Restricciones

- No modificar la fórmula de M1 ni los contratos públicos de ranking/player detail.
- No reemplazar el sistema ELO de clubes; este cambio debe convivir con `clubelo_seed` y
  `elo_v1`.
- `team_strengths` es el hot path que ya lee scoring; el nuevo flujo debe escribir ahí para
  reutilizar el scoring existente.
- La tabla `team_strengths.source` tiene un `CHECK` que hoy no permite una fuente de ELO de
  selecciones; se requiere migración antes del seed.
- El sitio ya está en producción: el deploy debe tener backup, auditoría previa/posterior,
  rollback claro y recálculo explícito.
- La fuente externa principal para selecciones será World Football Elo Ratings
  (`eloratings.net`), que publica ratings de selecciones y una vista específica del Mundial
  2026. Debe existir fallback manual/importable porque la fuente no es una API con SLA.
- La ingesta/reingesta del Mundial debe respetar el estado de specs de snapshots de equipo:
  no habilitar paths que dependan de snapshots incompletos si los gates de migración siguen
  abiertos.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Crear un provider específico `NationalTeamEloProvider` para selecciones basado en `eloratings.net` | Reusar `ClubEloProvider` | ClubElo es explícitamente de clubes y su mapping actual contiene clubes, no selecciones. |
| Guardar ELO de selecciones en `team_strengths` con `source='national_elo_seed'` | Crear tabla nueva de ratings de selecciones | M1 ya lee `team_strengths`; una tabla nueva agregaría joins y duplicaría el concepto strength. |
| Mantener `elo_raw` como rating bruto y `strength` como normalización 0-100 | Guardar solo strength normalizada | `elo_raw` permite auditar rankings y comparar con la fuente externa antes/después del recálculo. |
| Agregar migración para ampliar `ck_team_strength_source` | Sobrescribir con `source='override'` | Se pierde trazabilidad operacional y no queda claro qué datos vienen del seed de selecciones. |
| Crear `SeedNationalTeamEloUseCase` separado | Extender `SeedClubEloUseCase` con branches | Mantiene responsabilidades limpias y evita mezclar reglas de matching club vs selección. |
| Reusar `EloCalculatorService.normalize` inicialmente | Crear fórmula nueva de normalización | Mantiene M1 consistente con clubes; cualquier ajuste de rango puede hacerse luego como refactor medido. |
| Exponer endpoint admin `POST /api/v1/admin/elo/national-teams/seed` | Hacer solo script local | Producción vive en VPS; el endpoint protegido/admin permite ejecutar seed auditable sin SSH complejo. |
| Agregar tarea Celery `seed_national_team_elo_task` | Ejecutar el seed síncrono siempre desde HTTP | Evita timeouts y permite retry controlado en producción. |
| El recálculo de SFA sigue usando el pipeline existente de scoring | Crear cálculo especial para Mundial | El objetivo es alimentar M1 correctamente, no bifurcar scoring por torneo. |
| El rollout exige auditoría de coverage antes del recálculo | Recalcular inmediatamente después del seed | Si faltan selecciones por mapping, M1 mezclaría ELO y fallback legacy de forma silenciosa. |

## Domain Model

No se requieren nuevas entidades ni value objects de scoring. El bounded context afectado es
scoring, pero el modelo existente ya representa el concepto requerido:

- `TeamStrength` en infraestructura persiste la fuerza normalizada por
  `(team_id, season, competition_id)`.
- `M1RivalDifficulty` consume `player_team_strength` y `rival_team_strength`.
- `EloCalculatorService` ya normaliza ELO bruto a strength 0-100.

Se agregan DTOs simples en `domain/scoring_ports.py` para transportar snapshots de ELO de
selecciones desde el provider/use case hacia el repositorio. No hay invariantes nuevas que
justifiquen `@DDD-Designer`.

### Nuevos DTOs

- `NationalTeamEloEntry(country_name, elo_raw, rank, source_date)` — fila externa resuelta
  desde World Football Elo Ratings antes del matching con equipos SFA.

### Protocols modificados

- `TeamStrengthRepositoryPort` agrega métodos de lectura/auditoría necesarios para seed de
  selecciones y verificación de coverage mundialista.

## Integraciones externas

- Fuente primaria: `https://www.eloratings.net/` para ranking global de selecciones.
- Vista útil para Mundial 2026: `https://www.eloratings.net/2026_World_Cup`.
- No se asume SLA ni API JSON estable; el provider debe parsear HTML/texto de forma defensiva
  y retornar error claro si la fuente cambia.
- Fallback requerido: permitir seed desde payload manual/archivo controlado con
  `(team_name, elo_raw)` para producción si `eloratings.net` falla el día del deploy.
