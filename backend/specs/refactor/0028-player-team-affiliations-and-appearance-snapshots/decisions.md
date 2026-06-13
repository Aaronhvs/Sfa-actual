# 0028 - Snapshots de equipo por aparicion (v2 post-auditoria)

## Contexto de negocio

API-Football usa el mismo `external_id` para un jugador tanto en su club como en su
seleccion nacional. Pedri tiene `external_id=133609` con Barcelona y con Espana.

El problema es que `IngestionRepository.upsert_player()` sobreescribe `players.team_id`
en cada aparicion. Cuando se ingeste el Mundial 2026, Pedri pasara de Barcelona a Espana
globalmente. Todas las consultas que leen ese campo para atribuir goles (ELO), calcular
minutos (logros), reconstruir scores y mostrar equipos (ranking/perfil) se romperian
historicamente aunque el jugador y sus puntos no se dupliquen.

## Contexto de negocio - Mundial 2026

El Mundial es un evento aislado. Su ranking empieza en cero y mide quien es el mejor
jugador del torneo usando el mismo algoritmo SFA adaptado a selecciones. Los puntos del
Mundial NO se acumulan con los puntos de la liga o de la Champions. La pagina web mostrara
el ranking del Mundial en su propia vista; las temporadas de clubes siguen intactas.

Consecuencias directas para este spec:

- No existe un ranking global que mezcle puntos de clubes y Mundial.
- No hay que resolver que equipo mostrar cuando un jugador tiene datos en dos contextos:
  cada competicion tiene su propio ranking con su propio team_id.
- El ELO de selecciones es un sistema separado (spec futuro). El ELO de clubes actual
  es correcto porque aun no se ha ingestado ningun torneo de selecciones.
- No se necesita recalcular ELO historico.

## El problema real

`players.team_id` es un campo mutable que refleja el ultimo equipo ingestado. Se usa como
fuente de verdad en:

| Consulta | Uso actual | Riesgo si se procesa Espana |
|---|---|---|
| ELO | Separa goles home/away por `Player.team_id == fixture.*_team_id` | Goles historicos de Pedri se atribuyen a Espana |
| Logros - minutos | Filtra `player_stats` por `Player.team_id` | Minutos calculados con el equipo incorrecto |
| Logros - ranking | `get_player_rank_in_team` usa `Player.team_id` | Ranking interno del equipo incorrecto |
| Reingesta | `get_fixtures_for_player` usa `Player.team_id` | Local/visitante invertido en fixtures historicos |
| Rebuild scores | Copia `players.team_id` a `sfa_season_scores` | Snapshot historico sobreescrito |
| Inferencia copas | Agrupa goles por `Player.team_id` | Puede inferir ganador incorrecto |
| `sfa_score_repository` | Joins contra `Player.team_id` para ranking y perfil | Jugadores desaparecen si `team_id` queda NULL |
| Enriquecimiento | `enrich_position_repository` filtra por `Player.team_id` | Enriquecimiento enviado al equipo incorrecto |
| `scoring_repository` | Lee `Player.team_id` para construir scores | Score asociado al equipo incorrecto |
| `ingestion_repository` | Lee `Player.team_id` en queries de contexto | Contexto de ingestion contaminado |

## La fix minima

Agregar `team_id` como snapshot inmutable en `player_stats` y `player_events`. Dejar de
escribir `players.team_id` durante la ingestion. Redirigir todas las consultas de negocio
al snapshot.

No se crea ninguna tabla nueva. No se introduce ningun modelo de dominio nuevo.

## Restricciones

- No se modifican formulas, multiplicadores ni puntos base de scoring.
- El snapshot `player_stats.team_id` debe ser `fixtures.home_team_id` o
  `fixtures.away_team_id`. La aplicacion valida esto en ingestion y lanza error explicito.
- `player_events.team_id` debe coincidir con `player_stats.team_id` del mismo
  `(player_id, fixture_id)`. La auditoria critica verifica esta consistencia.
- Los contratos HTTP existentes conservan `team_name` y `team_logo_url`.
- `players.team_id` no se elimina fisicamente. Queda nullable en expand y deprecado.
- El Mundial 2026 no se ingesta en este spec. La ingesta del Mundial queda bloqueada
  hasta completar 0022 y los contadores de auditoria en cero.
- No se toca el ELO historico. No hay contaminacion activa.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Agregar `player_stats.team_id` | Derivarlo siempre del fixture | La aparicion debe conservar su equipo de forma auditable. |
| Agregar `player_events.team_id` desde la aparicion | Solo `player_stats.team_id` | El evento de scoring debe ser auditable sin join adicional. |
| Agregar `competitions.participant_kind` DEFAULT `club` con CHECK | Detectarlo por nombre | Permite marcar el Mundial explicitamente sin heuristicas. |
| Parar escritura de `players.team_id` en `upsert_player` | Priorizar club sobre seleccion | Cualquier politica de equipo unico mantiene el bug. |
| Hacer `players.team_id` nullable en `0021` (expand), antes del codigo nuevo | Hacerlo en `0022` | Si el codigo se despliega antes de que la columna sea nullable, los inserts de jugadores nuevos fallan con NOT NULL. |
| COALESCE validado contra fixture para ELO transitorio | COALESCE directo | Un COALESCE sin validacion puede devolver el equipo actual del jugador para un fixture historico donde nunca jugo en ese equipo. |
| Fuente secundaria de backfill: `sfa_season_scores.team_id` validado contra fixture | Solo `players.team_id` | Para jugadores transferidos cuyo equipo actual no coincide con el fixture historico, el score snapshot puede ofrecer un candidato valido. |
| Separar expand/backfill (0021) y constraints (0022) | Una sola migracion | Permite auditar, corregir y desplegar codigo nuevo antes de imponer NOT NULL. |
| Bloquear ingesta del Mundial hasta cero contadores criticos | Ingesta paralela al rollout | Una fila unresolved durante la ingesta del Mundial producirla atribuciones incorrectas. |
| No crear `PlayerTeamAffiliation` ni bounded context | Arquitectura completa de afiliaciones | El Mundial es un evento aislado; no existe ranking global mixto que lo justifique. |
| No recalcular ELO historico | Recalculo obligatorio | No hay datos de selecciones en DB; el ELO de clubes es correcto. |

## Modelo de persistencia

### `competitions`

```sql
ALTER TABLE competitions
  ADD COLUMN participant_kind VARCHAR(20) NOT NULL DEFAULT 'club'
  CHECK (participant_kind IN ('club', 'national_team'));
```

### `player_stats`

```sql
ALTER TABLE player_stats
  ADD COLUMN team_id INTEGER REFERENCES teams(id);
-- nullable en expand; NOT NULL en 0022
CREATE INDEX ix_player_stats_team_season ON player_stats(team_id, season);
```

### `player_events`

```sql
ALTER TABLE player_events
  ADD COLUMN team_id INTEGER REFERENCES teams(id);
-- nullable en expand; NOT NULL en 0022
CREATE INDEX ix_player_events_team_fixture ON player_events(team_id, fixture_id);
```

### `players`

```sql
-- En 0021, ANTES de desplegar codigo nuevo:
ALTER TABLE players ALTER COLUMN team_id DROP NOT NULL;
```

`players.team_id` queda como fallback de presentacion de ultimo recurso. Ningun use case
ni repositorio escribe en el despues del cutover.

## Estrategia de migracion

### Prerequisito

Ejecutar `scripts/audit_player_team_snapshots.sql` sobre copia de DB en modo diagnostico
antes de expand. Registrar conteos. El resultado define el trabajo operativo esperado.

### `0021_player_team_snapshots_expand.sql`

Orden obligatorio:

1. `ALTER players.team_id DROP NOT NULL` — debe ocurrir ANTES de que el codigo nuevo
   se despliegue para evitar fallo de NOT NULL en inserts de jugadores nuevos.
2. Agregar `competitions.participant_kind`.
3. Agregar `player_stats.team_id` nullable + indice.
4. Agregar `player_events.team_id` nullable + indice.
5. Backfill `player_stats.team_id` con dos candidatos en orden de prioridad:
   - candidato 1: `players.team_id` si coincide con `fixtures.home_team_id` o
     `fixtures.away_team_id`;
   - candidato 2: `sfa_season_scores.team_id` del mismo `(player_id, competition_id, season)`
     si coincide con `fixtures.home_team_id` o `fixtures.away_team_id`;
   - sin candidato valido: la fila queda NULL y se reporta como unresolved.
6. Backfill `player_events.team_id` desde la aparicion exacta `(player_id, fixture_id)`.
7. Ejecutar auditoria post-backfill: mostrar conteos; no imponer NOT NULL aun.

El backfill debe ser idempotente y ejecutable por lotes. No se exige una transaccion
unica de larga duracion.

### Gestion de filas unresolved

Si quedan filas unresolved tras el backfill:

- No se puede ejecutar `0022`.
- Opciones de recuperacion en orden de preferencia:
  1. Reingesta controlada del fixture desde API-Football.
  2. Correccion manual auditada con `player_id` y `fixture_id` identificados.
  3. Consulta adicional a `player_achievement_bonuses.team_id` para el mismo alcance.
- La ingesta del Mundial queda bloqueada hasta que los contadores criticos sean cero.
- El sistema permanece en modo dual-read con el codigo nuevo y columnas nullable.

### `0022_player_team_snapshots_constraints.sql`

Solo se ejecuta cuando se cumplen TODAS las condiciones:

- Codigo nuevo desplegado y todos los productores escriben snapshots.
- Ningun caller antiguo activo.
- Los cinco contadores criticos son exactamente cero.
- Se ha ejecutado al menos una reingesta de muestra y los scores no cambiaron.

```sql
ALTER TABLE player_stats ALTER COLUMN team_id SET NOT NULL;
ALTER TABLE player_events ALTER COLUMN team_id SET NOT NULL;
```

## Lecturas de `Player.team_id` a corregir

Todos los archivos siguientes tienen lecturas o joins que deben redirigirse al snapshot:

| Archivo | Tipo de lectura |
|---|---|
| `ingestion_repository.py` | Contexto de ingestion |
| `team_strength_repository.py` | Separacion goles ELO |
| `competition_achievement_repository.py` | Minutos, jugadores y ranking interno |
| `infer_achievements_repository.py` | Agrupacion de goles |
| `player_event_score_repository.py` | Rebuild team_id en scores |
| `player_repository.py` | Fallback de perfil |
| `sfa_score_repository.py` (lineas 43, 211, 433) | Joins para ranking y perfil |
| `scoring_repository.py` | Construccion de scores |
| `enrich_position_repository.py` | Contexto de enriquecimiento |
| `reingest_player.py` | Calculo local/visitante |

## COALESCE transitorio para ELO

Durante la fase entre 0021 y 0022, las filas historicas pueden tener `player_stats.team_id`
NULL. El fallback en ELO debe validar el candidato contra el fixture:

```sql
COALESCE(
  ps.team_id,
  CASE
    WHEN p.team_id = f.home_team_id THEN f.home_team_id
    WHEN p.team_id = f.away_team_id THEN f.away_team_id
    ELSE NULL
  END
)
```

Si el resultado es NULL, el fixture debe registrarse en auditoria y excluirse del calculo
de ELO. No puede procesarse con un equipo arbitrario.

## Equipo mostrado en perfil con apariciones mixtas

Cuando un jugador tiene apariciones de club y de seleccion, la jerarquia de resolucion es:

1. `sfa_season_scores.team_id` de la competicion solicitada en el contexto.
2. Ultima aparicion en `player_stats` de la temporada solicitada por mayor suma de minutos.
3. Ultima aparicion en `player_stats` sin filtro de competicion.
4. `players.team_id` como ultimo fallback de presentacion.

Esta logica nunca devuelve NULL al frontend si el jugador tiene al menos una aparicion.

## Criterios criticos de auditoria (bloquean 0022 y Mundial)

- `player_stats.team_id IS NULL`
- `player_events.team_id IS NULL`
- snapshot fuera de `fixtures.home_team_id` y `fixtures.away_team_id`
- `player_events.team_id <> player_stats.team_id` para el mismo `(player_id, fixture_id)`
- evento sin `player_stats` correspondiente para el mismo `(player_id, fixture_id)`

## Verificacion final

1. Ingestar un fixture de La Liga con Pedri: `player_stats.team_id = Barcelona`.
2. Ingestar un fixture del Mundial con Pedri: `player_stats.team_id = Espana`.
3. `players.id` es el mismo. `players.team_id` no cambio en ninguno de los dos.
4. El ranking de La Liga muestra Barcelona; el del Mundial muestra Espana.
5. ELO de Barcelona: goles al mismo lado que antes del refactor.
6. Logros de Barcelona: selecciona solo minutos con `player_stats.team_id = Barcelona`.
7. Insertar un jugador nuevo durante la transicion (entre 0021 y 0022): no falla NOT NULL.
8. `audit_player_team_snapshots.sql` devuelve cero en los cinco contadores criticos.
9. `rg "Player\.team_id|p\.team_id" src/` no encuentra lecturas de negocio.
10. `sfa_season_scores` antes y despues del refactor: `total_pts` identico por jugador.
