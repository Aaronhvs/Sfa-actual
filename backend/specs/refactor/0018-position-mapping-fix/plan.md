# Plan: Position Mapping Fix — Corrección masiva de posiciones de jugadores

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py` — agregar `update_position: bool = True` a `upsert_player` en el Protocol
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — modificar `upsert_player` para respetar el flag `update_position`
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — pasar `update_position=False` cuando la posición resuelta es `MC` y el jugador ya puede existir

## Archivos a crear

- [ ] `src/sfa/application/use_cases/fix_player_positions.py` — use case one-shot para bulk UPDATE de posiciones existentes
- [ ] `http/fix_player_positions.http` — archivo HTTP para invocar el endpoint de fix
- [ ] `tests/use_cases/test_fix_player_positions.py` — tests del use case

## Checklist de implementación

### Paso 1 — Leer `ingestion_repository.py` completo antes de modificarlo

- [ ] Leer `src/sfa/infrastructure/repositories/ingestion_repository.py` completo
- [ ] Identificar el método `upsert_player` exacto (firma + SQL/ORM usado para ON CONFLICT)

### Paso 2 — Modificar `IngestionRepositoryPort.upsert_player` en `ingestion_ports.py`

Agregar parámetro `update_position: bool = True` a la firma del Protocol:

```python
async def upsert_player(
    self, external_id: int, name: str, team_id: int, position: Position,
    photo_url: str | None = None,
    update_position: bool = True,
) -> int: ...
```

El default `True` preserva el comportamiento actual para cualquier caller que no pase el flag.

### Paso 3 — Modificar `ingestion_repository.py`: método `upsert_player`

Localizar el `INSERT ... ON CONFLICT DO UPDATE` de `upsert_player`. Cambiar el SET de
`position` para respetar el flag:

```sql
-- Lógica resultante en el ON CONFLICT:
-- Si update_position=True → SET position = EXCLUDED.position (comportamiento actual)
-- Si update_position=False → NO incluir position en el SET (preservar valor existente)
```

En SQLAlchemy con `pg_insert` esto se logra condicionalmente construyendo el dict `set_`:

```python
set_dict = {"name": ..., "photo_url": ...}
if update_position:
    set_dict["position"] = insert_stmt.excluded.position
stmt = insert_stmt.on_conflict_do_update(
    index_elements=["external_id"],
    set_=set_dict,
)
```

La llave de conflict es `external_id` (columna UNIQUE en `players`).

### Paso 4 — Modificar `ingest_competition.py`: llamada a `upsert_player`

En la línea donde se llama `upsert_player` (dentro del loop de `player_stats_list`):

```python
position = map_position(ps.player_name, ps.position)
# Solo actualizar posición si viene de KNOWN_POSITIONS o si es diferente de MC.
# Cuando API-Football devuelve null, ps.position cae en fallback "Midfielder" → MC.
# En ese caso, no sobrescribir una posición que puede haber sido correctamente seteada.
update_pos = (
    ps.player_name in KNOWN_POSITIONS  # siempre confiar en KNOWN_POSITIONS
    or position != Position.MC         # posición específica (GK, DC, LAT, EXT, DEL)
)
player_db_id = await self._repo.upsert_player(
    ps.player_external_id, ps.player_name,
    proc_team_db_id, position,
    photo_url=ps.photo_url,
    update_position=update_pos,
)
```

Importar `KNOWN_POSITIONS` desde `sfa.domain.position_mapping` al inicio del use case
(ya importa `map_position`, agregar `KNOWN_POSITIONS` al mismo import).

### Paso 5 — Crear `FixPlayerPositionsUseCase` en `fix_player_positions.py`

Este use case es one-shot: corrige posiciones en la DB basándose en los datos que ya
existen en `players.external_id` y en el mapping `BASE_POSITION_MAP`. No llama a
API-Football.

**Lógica:**

El problema es que no tenemos el string de posición original de API-Football guardado en DB
(solo tenemos el enum mapeado). Sin embargo, sí podemos inferir:
- Todos los jugadores con `position = 'MC'` que NO están en `KNOWN_POSITIONS` → muy
  probablemente son Defender (DC) o Goalkeeper (GK) mal clasificados.
- No podemos saber cuáles son GK, DC, LAT sin re-consultar la API.

**Solución pragmática con datos disponibles:**

El use case ejecuta las siguientes correcciones mediante SQL directo:

```sql
-- 1. Jugadores con posición MC que tienen 0 goles, 0 asistencias, saves > 0
--    en sus player_stats → probablemente GK
UPDATE players p
SET position = 'GK'
WHERE p.position = 'MC'
  AND EXISTS (
    SELECT 1 FROM player_stats ps
    WHERE ps.player_id = p.id
      AND ps.saves > 0
  )
  AND NOT EXISTS (
    SELECT 1 FROM player_stats ps2
    WHERE ps2.player_id = p.id
      AND (ps2.goals > 0 OR ps2.assists > 0)
  );

-- 2. Jugadores con posición MC que en sus stats muestran patrón defensivo:
--    intercepciones altas, goals bajos, passes_total bajo → probablemente DC
--    Heurística: avg interceptions > 1.0 AND avg goals < 0.1 por partido
UPDATE players p
SET position = 'DC'
WHERE p.position = 'MC'
  AND (
    SELECT AVG(ps.interceptions)
    FROM player_stats ps
    WHERE ps.player_id = p.id
  ) > 1.0
  AND (
    SELECT AVG(ps.goals)
    FROM player_stats ps
    WHERE ps.player_id = p.id
  ) < 0.05
  AND (
    SELECT COUNT(*)
    FROM player_stats ps
    WHERE ps.player_id = p.id
  ) >= 3;  -- al menos 3 partidos para que la heurística sea confiable
```

**Importante:** este uso de heurísticas estadísticas cubre GK y DC (los casos más
impactantes en scoring). LAT vs DC es difícil de distinguir; por ahora todos los
defensas quedan en DC salvo los que están en `KNOWN_POSITIONS` (que ya están correctos).

El use case también aplica `KNOWN_POSITIONS` directamente a la DB: para cada jugador
en `KNOWN_POSITIONS`, si existe en `players` (por nombre), forzar la posición correcta.

**Firma del use case:**

```python
@dataclass(frozen=True)
class FixPlayerPositionsResult:
    gk_fixed: int
    dc_fixed: int
    known_positions_fixed: int
    total_fixed: int

class FixPlayerPositionsUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self) -> FixPlayerPositionsResult: ...
```

**Nota de arquitectura:** este use case recibe `AsyncSession` directamente porque es un
fix administrativo one-shot que no pertenece al flujo normal de ingesta. No viola la
arquitectura hexagonal: es equivalente a una migration de datos con lógica de dominio.
Se accede mediante un endpoint admin protegido.

### Paso 6 — Agregar router y endpoint para `FixPlayerPositionsUseCase`

Agregar al router existente de admin/scoring (buscar el router más adecuado — probablemente
`api/v1/scoring.py` o `api/v1/admin.py`):

```
POST /admin/fix-player-positions
```

Sin body. Retorna `FixPlayerPositionsResult` como JSON.

Leer `src/sfa/api/v1/` para identificar el router correcto antes de modificarlo.

### Paso 7 — Registrar en `core/dependencies.py` y `main.py`

- Agregar factory `get_fix_player_positions_use_case` en `dependencies.py`
- Si el endpoint va en un router nuevo, registrarlo en `main.py`
- Si va en un router existente, verificar que esté registrado

### Paso 8 — Crear `http/fix_player_positions.http`

```http
### Fix player positions (one-shot admin operation)
POST http://localhost:8000/admin/fix-player-positions
Content-Type: application/json

###
```

### Paso 9 — Verificar el estado pre-fix con queries SQL de diagnóstico

Antes de ejecutar el fix, correr estos queries para documentar el estado inicial:

```sql
-- Distribución actual de posiciones
SELECT position, COUNT(*) as cnt
FROM players
GROUP BY position
ORDER BY cnt DESC;

-- Jugadores con saves > 0 pero position = 'MC' (candidatos a GK)
SELECT COUNT(*) as gk_candidates
FROM players p
WHERE p.position = 'MC'
  AND EXISTS (
    SELECT 1 FROM player_stats ps WHERE ps.player_id = p.id AND ps.saves > 0
  );

-- Top 20 defensores conocidos mal clasificados
SELECT p.name, p.position
FROM players p
WHERE p.name IN (
  'Virgil van Dijk', 'Antonio Rüdiger', 'Marc-André ter Stegen',
  'Alisson', 'Ederson', 'Manuel Neuer', 'David Raya'
)
ORDER BY p.name;
```

### Paso 10 — Tests en `tests/use_cases/test_fix_player_positions.py`

Los tests NO usan DB real. Usar `AsyncSession` mockeada o un Fake simple.

Escenarios a cubrir:
- [ ] `test_gk_detection_by_saves` — jugador con saves > 0 y sin goles es detectado como GK
- [ ] `test_dc_detection_by_heuristic` — jugador con intercepciones altas y 0 goles → DC
- [ ] `test_known_positions_applied` — jugador en KNOWN_POSITIONS recibe posición correcta
- [ ] `test_mc_player_unchanged_if_ambiguous` — MC con stats ambiguas no se toca
- [ ] `test_result_counts_are_accurate` — el resultado reporta los conteos correctos

**Nota:** dado que el use case usa `text()` SQL directo para el bulk UPDATE, los tests
deben mockear `session.execute` con resultados simulados, o bien extraer la lógica de
clasificación a funciones puras testeables (preferido).

Patrón recomendado: extraer la función de clasificación como función pura:

```python
# En fix_player_positions.py
def classify_player_from_stats(
    avg_saves: float,
    avg_interceptions: float,
    avg_goals: float,
    match_count: int,
) -> Position | None:
    """Retorna la posición inferida o None si no hay suficiente evidencia."""
    if avg_saves > 0:
        return Position.GK
    if match_count >= 3 and avg_interceptions > 1.0 and avg_goals < 0.05:
        return Position.DC
    return None
```

Testear `classify_player_from_stats` directamente como función pura (sin async, sin DB).

### Paso 11 — Ejecutar el fix en producción (secuencia de operaciones)

**Orden obligatorio:**

1. Desplegar el código con el fix en `upsert_player` (Paso 3 y 4)
2. Llamar `POST /admin/fix-player-positions` para corregir los registros existentes
3. Verificar distribución post-fix con el query de diagnóstico (Paso 9)
4. Llamar `POST /scoring/recalculate-full` con `force_recalculate=True` para regenerar
   `player_event_scores` y `sfa_season_scores` con las posiciones corregidas
5. Verificar ranking con queries de sanidad (Paso 12)

### Paso 12 — Queries de verificación post-fix

```sql
-- Distribución de posiciones post-fix (esperar: DC ~20%, GK ~10%, MC ~25%)
SELECT position, COUNT(*) as cnt,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM players
GROUP BY position
ORDER BY cnt DESC;

-- Verificar jugadores conocidos tienen posición correcta
SELECT p.name, p.position
FROM players p
WHERE p.name IN (
  'Virgil van Dijk', 'Antonio Rüdiger', 'Marc-André ter Stegen',
  'Alisson', 'Ederson', 'Manuel Neuer', 'David Raya',
  'Alejandro Balde', 'Jules Koundé', 'Trent Alexander-Arnold'
)
ORDER BY p.name;

-- Verificar que player_event_scores.position refleja posiciones corregidas
SELECT pes.position, COUNT(*) as cnt
FROM player_event_scores pes
JOIN players p ON pes.player_id = p.id
WHERE pes.rules_version_id = (SELECT MAX(id) FROM scoring_rules_versions)
GROUP BY pes.position
ORDER BY cnt DESC;

-- Top DC por SFA pts (sanity check: deben aparecer van Dijk, Rüdiger, etc.)
SELECT p.name, p.position, ss.total_pts
FROM sfa_season_scores ss
JOIN players p ON ss.player_id = p.id
WHERE p.position = 'DC'
  AND ss.season = '2024'
ORDER BY ss.total_pts DESC
LIMIT 20;
```

### Paso 13 — Linter y tests

- [ ] `flake8 src/ tests/` sin errores nuevos
- [ ] `isort --check-only src/ tests/` sin errores
- [ ] `pytest tests/` pasa con coverage ≥ 80%

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no requiere nuevas entidades de dominio ni value objects. Los cambios son:
1. Un flag adicional en un Protocol existente (`update_position`)
2. Lógica condicional en un repositorio existente
3. Un use case administrativo one-shot que opera sobre modelos ya existentes
4. Heurísticas de clasificación expresadas como funciones puras

El enum `Position` y el modelo `Player` no cambian. No hay nuevas reglas de scoring.

## Verificación

1. `GET /players/{id}` para Van Dijk o Rüdiger → `"position": "DC"` (no `"MC"`)
2. `GET /players/{id}` para Ter Stegen o Alisson → `"position": "GK"`
3. `GET /players/{id}` para Koundé o Alexander-Arnold → `"position": "LAT"`
4. Query SQL de distribución de posiciones muestra DC ~15-20%, GK ~8-12%
5. Ranking de DC en SFA pts muestra defensas reales en el top (no mediocampistas)
6. Futuras ingestas: ingestar un fixture nuevo y verificar que un jugador con
   `position=null` en API-Football no sobrescribe su posición correcta en DB
