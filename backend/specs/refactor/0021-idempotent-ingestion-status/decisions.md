# Refactor 0021 — Idempotent Ingestion & Status Visibility

## Contexto de negocio

El sistema de ingesta actual opera como una caja negra: no hay forma de saber qué ligas y
temporadas tienen datos en DB antes de lanzar una tarea. Esto provocó dos incidentes reales:

1. Se lanzó `ingest_all_competitions_task(season=2024)` sin saber si los datos ya existían,
   consumiendo quota de API-Football innecesariamente (plan = 7500 req/día).
2. Se lanzó ingesta de season=2025 pero el quota se agotó antes de completarse; no hay forma
   de saber qué competiciones llegaron a completarse y cuáles quedaron a medias.

Adicionalmente, `GET /admin/ingestion-logs` retorna `{"logs": []}` (TODO sin implementar),
y el beat schedule de Celery está vacío pero sin ninguna garantía documentada de que así
permanezca.

## Restricciones

- Sin migraciones de DB: `IngestionLog` ya existe con columnas suficientes.
- No modificar `IngestCompetitionUseCase` ni `IngestAllCompetitionsUseCase` — la lógica de
  ingesta en sí es correcta; el cambio es en la capa de orquestación (tasks + endpoints).
- No se necesita @DDD-Designer: no hay nuevas entidades de dominio con invariantes.
- El rate limit de API-Football (7500 req/día) es la restricción operacional principal que
  motiva la idempotencia.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| El guard de idempotencia vive en la **task**, no en el use case | Guard en el use case | El use case no debe saber sobre estado global de ingesta; la task es el punto de entrada operacional |
| `force=False` como parámetro de task y endpoint | Campo en DB o header HTTP | Más simple, sin estado adicional; el operador lo pasa explícitamente cuando sabe lo que hace |
| `GetIngestionStatusUseCase` resuelve tanto `/ingestion-status` como `/ingestion-logs` | Dos use cases separados | Evita duplicación; un mismo use case puede retornar el report completo o solo los logs según contexto |
| `IngestionRepositoryPort` extendido con 3 métodos nuevos | Port nuevo `IngestionStatusRepositoryPort` | El port ya cubre escritura de ingesta; los reads de estado pertenecen al mismo contrato |
| `status="MISSING"` para ligas sin ningún log | Solo mostrar ligas con logs | El operador necesita ver exactamente qué falta, no solo lo que hay |
| `BEAT_SCHEDULE_DISABLED = True` + comentario en `celery_app.py` | Eliminar la variable `beat_schedule` | El comentario explícito es suficiente garantía; eliminarla podría confundir en un refactor futuro |
| Fixtures count se obtiene con query `GROUP BY competition_id` | Count por separado para cada liga | Una sola query es más eficiente y no cambia la interfaz del use case |

## Domain Model

No aplica. Este refactor no introduce entidades de dominio nuevas. Los dos DTOs nuevos
(`IngestionLogRow`, `CompetitionIngestionStatusDTO`) son frozen dataclasses de lectura sin
invariantes — no requieren modelado por @DDD-Designer.

### Nuevos DTOs en `domain/ingestion_ports.py`

**`IngestionLogRow`** — row de lectura del log de ingesta:
- `competition_id: int`
- `season: str`
- `status: IngestionStatus`
- `started_at: datetime`
- `finished_at: datetime | None`
- `error_msg: str | None`

**`CompetitionIngestionStatusDTO`** — vista consolidada por liga/temporada para el operador:
- `competition_name: str`
- `league_id: int`
- `season: str`
- `status: str`  — `"COMPLETED"` | `"FAILED"` | `"MISSING"` | `"RUNNING"`
- `fixtures_in_db: int`
- `last_ingested_at: datetime | None`
- `error_msg: str | None`

## Integraciones externas

Ninguna. Este refactor opera exclusivamente sobre datos ya almacenados en PostgreSQL.
