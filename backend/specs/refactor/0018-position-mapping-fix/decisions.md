# Position Mapping Fix — Corrección masiva de posiciones de jugadores

## Contexto de negocio

La tabla `players` muestra la siguiente distribución de posiciones:

| Position | Count | % |
|---|---|---|
| MC | 6,727 | ~97% |
| EXT | 90 | <1% |
| DEL | 78 | <1% |
| LAT | 34 | <1% |
| DC | 0 | 0% |
| GK | 0 | 0% |

Virgil van Dijk, Rüdiger, Ter Stegen y prácticamente todos los defensas centrales y arqueros
están almacenados como MC. Esto significa que sus `player_event_scores.base_points` corresponden
a la tabla MF en lugar de DF, lo que corrompe el ranking SFA para esos jugadores.

El impacto es crítico: el scoring system tiene tablas de `base_points` diferenciadas por
grupo posicional (FW / MF / DF). Un DC scored como MF recibe puntos incorrectos por tackles,
intercepciones, bloqueos y duelos (que pesan diferente para DF vs MF en `BASE_POINTS_TABLE`).

## Causa raíz identificada

El endpoint `fixtures/players` de API-Football devuelve:

```json
{ "games": { "position": "Goalkeeper" | "Defender" | "Midfielder" | "Attacker" | null } }
```

En el provider (`api_football.py` línea 207):
```python
position=games.get("position") or "Midfielder",
```

El fallback cuando `position` es `null` o vacío es `"Midfielder"`. Esto es correcto.

La función `map_position()` en `domain/position_mapping.py` tiene el mapping correcto:
- `"Goalkeeper"` → `GK`
- `"Defender"` → `DC`
- `"Midfielder"` → `MC`
- `"Attacker"` → `DEL`

**El problema real está en `upsert_player`**: el use case llama `upsert_player` en cada fixture
procesado para cada jugador. Un jugador como Van Dijk aparece en 38+ partidos por temporada.
Si API-Football devuelve `null` para `position` en cualquiera de esos partidos (lo cual ocurre
frecuentemente en la respuesta de `fixtures/players`), el `upsert_player` sobrescribe la
posición correctamente asignada previamente con `MC` (el fallback). La última escritura gana,
y como hay muchos partidos, el resultado estadístico es que la mayoría termina en MC.

Adicionalmente, `KNOWN_POSITIONS` en `position_mapping.py` solo cubre ~250 jugadores (los
más conocidos de las 5 grandes ligas), dejando sin cubrir a ~6,400 jugadores de copas, equipos
menores y ligas secundarias que dependen 100% del mapping base — y que quedan como MC cuando
API-Football devuelve null.

## Restricciones

- No re-ingestar: los 7,500 requests/día de cuota no permiten re-procesar toda la historia
- No hay DDL migration necesaria: el enum `Position` ya tiene todos los valores correctos (`GK`, `DC`, `LAT`, `MC`, `EXT`, `DEL`)
- El recálculo de scores debe hacerse después del fix de posiciones, no antes
- `player_event_scores.position` no requiere UPDATE directo: la columna se escribe en recálculo
  leyendo `Player.position` en vivo desde la DB (join en `get_events_for_recalc`)
- El endpoint `POST /scoring/recalculate-full` (con `force_recalculate=True`) ya existe y
  puede disparar el recálculo completo sin nueva infraestructura

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Fix en `upsert_player`: no sobrescribir posición si el jugador ya existe y la nueva posición es `MC` (fallback genérico) | Re-ingestar todos los fixtures | Re-ingestar consume toda la cuota diaria; el fix en upsert es quirúrgico |
| Bulk UPDATE SQL para corregir los 6,727 jugadores existentes usando el mapping de API-Football vía `external_id` | Script Python que re-llame al provider | No hay acceso a datos históricos del provider sin re-ingestar; el campo `position` de API-Football no cambió — lo que cambió es que ya no se debe sobrescribir |
| Lógica de "no sobrescribir": comparar posición nueva contra la existente; solo actualizar si la nueva posición es distinta de `MC` O si el jugador no existe todavía | Guard con lista blanca de posiciones "confiables" | Más simple, cubre todos los casos incluyendo `KNOWN_POSITIONS` que puede devolver LAT/EXT |
| Defaultear `"Defender"` → `DC` para todos los jugadores sin posición específica conocida | Intentar inferir LAT vs DC por número de camiseta | Heurística de camiseta es imprecisa y no disponible en el endpoint de stats; DC es mejor default que MC para un defensa |
| Defaultear `"Attacker"` → `DEL` (el mapping base ya lo hace, sin cambio) | Defaultear a EXT | DEL ya es el default correcto en `BASE_POSITION_MAP`; EXT/LAT se cubren vía `KNOWN_POSITIONS` |
| Recálculo completo via `POST /scoring/recalculate-full` (endpoint existente) | Recálculo parcial solo para jugadores afectados | El volumen de jugadores afectados es ~97% del total; recálculo completo es más seguro y ya está implementado |
| Agregar método `update_player_position_bulk` al `IngestionRepository` para el bulk UPDATE | Alembic migration con UPDATE inline | El update lógico pertenece al dominio de ingesta; mantiene la arquitectura hexagonal |

## Integraciones externas

Ninguna nueva. El fix es puramente en capa de infra y dominio interno. No se llama a
API-Football para este fix.

## Archivos afectados (lectura previa)

| Archivo | Rol |
|---|---|
| `src/sfa/domain/position_mapping.py` | `map_position()` — sin cambio en lógica, correcto |
| `src/sfa/infrastructure/providers/api_football.py` | Fallback `"Midfielder"` — sin cambio |
| `src/sfa/application/use_cases/ingest_competition.py` | Llama `upsert_player` cada fixture — AQUÍ se agrega la guard |
| `src/sfa/domain/ingestion_ports.py` | `IngestionRepositoryPort.upsert_player` — agregar param `update_position: bool` |
| `src/sfa/infrastructure/repositories/ingestion_repository.py` | Implementa `upsert_player` — agregar lógica ON CONFLICT con guard |
| `src/sfa/infrastructure/models/players/models.py` | Modelo `Player` — sin cambio |
| `src/sfa/infrastructure/models/enums.py` | Enum `Position` — sin cambio |
