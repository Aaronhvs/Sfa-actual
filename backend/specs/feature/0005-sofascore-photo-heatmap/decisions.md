# 0005 — Sofascore: foto y heatmap de jugador

## Contexto de negocio

El perfil del jugador en la app muestra `photo_url` (ya existente) y necesita soportar dos
enriquecimientos adicionales desde la API pública de Sofascore (sin autenticación):

1. **Foto del jugador** — URL de imagen de perfil construida a partir del `sofascore_id`.
   Se persiste en la columna `players.photo_url` ya existente, sustituyendo o rellenando
   la foto proveniente de API-Football cuando esta falta o es de baja calidad.
2. **Heatmap por temporada** — URL de imagen PNG del heatmap del jugador en una
   temporada/torneo específico de Sofascore. Se persiste en una nueva columna
   `players.heatmap_url` y se expone en `GET /players/{id}`.

La columna `players.sofascore_id` ya existe en el modelo SQLAlchemy (`Integer, nullable,
unique`) pero su migration SQL está pendiente.

---

## Restricciones

- La API de Sofascore no requiere autenticación ni API key.
- Los IDs de torneo (`unique_tournament_id`) y temporada (`season_id`) de Sofascore son
  distintos a los IDs de API-Football y no están almacenados en la DB. El operador los
  provee manualmente como parámetros en el endpoint admin.
- La URL del heatmap es una URL pública estable; se almacena para servirla sin
  re-consultar Sofascore en cada petición del cliente.
- Solo se mantiene un heatmap activo por jugador (el de la temporada en curso).
- La búsqueda de jugador en Sofascore es por nombre; el matching usa
  `difflib.SequenceMatcher` con umbral ≥ 0.75 (mismo patrón que `name_matching.py`).

---

## Decisiones tomadas

| ID | Decisión | Alternativa descartada | Razón |
|----|----------|------------------------|-------|
| D1 | Flujo en dos fases independientes: Fase A (resolve `sofascore_id` + foto) / Fase B (fetch heatmap) | Flujo único combinado | El operador puede re-ejecutar solo el heatmap al cambiar de temporada sin tocar la foto; la separación también permite tener `sofascore_id` pre-cargado manualmente |
| D2 | `heatmap_url` como columna `TEXT` en `players` | Tabla separada `player_heatmaps(player_id, tournament_id, season_id)` | Un único heatmap activo por jugador es suficiente para los requisitos actuales; la tabla separada añadiría complejidad injustificada |
| D3 | La URL de foto se construye determinísticamente como `https://img.sofascore.com/api/v1/player/{sofascore_id}/image` sin hacer GET | Descargar la imagen y almacenarla en S3 | Sin coste de almacenamiento; la URL de Sofascore es pública y estable |
| D4 | `SofascoreProviderPort` con dos métodos: `search_player` (async, HTTP) y `get_heatmap_url` (sync, solo construye string) | Un método único `fetch_all` | Separación de responsabilidades; `get_heatmap_url` es puro y testeable sin mocks HTTP |
| D5 | `unique_tournament_id` y `season_id` de Sofascore se pasan como parámetros explícitos en el endpoint admin | Mapeo automático desde IDs de API-Football | No existe una tabla de correspondencia entre ambos sistemas de IDs; el mapeo manual es más seguro y mantenible |
| D6 | `SofascoreEnrichmentRepositoryPort` separado del `EnrichmentRepositoryPort` existente | Ampliar `EnrichmentRepositoryPort` | El repo existente está acoplado al flujo FBref/Understat; Sofascore tiene un conjunto de campos ortogonal (`sofascore_id`, `photo_url`, `heatmap_url`) |
| D7 | `heatmap_url` se expone en `GET /players/{id}` ampliando `PlayerDetailResult` y `PlayerScoreDTO` | Endpoint nuevo `GET /players/{id}/heatmap` | El campo es un atributo del perfil del jugador, no un recurso independiente; añadir un endpoint nuevo solo por una URL sería sobrediseño |
| D8 | `PlayerScoreDTO` se amplía con `heatmap_url: str \| None = None` y el JOIN con `players.heatmap_url` se hace en `SFAScoreRepository.get_best_score_for_player_season` | Leer `heatmap_url` desde `PlayerRepository` en el use case de detalle con una segunda query | El use case de detalle ya obtiene el score; añadir una segunda query solo para `heatmap_url` es redundante y viola el principio de mínimas queries |
| D9 | `update_player_sofascore_id` aplica solo cuando `sofascore_id IS NULL` (no sobreescribe) | Siempre sobreescribir | Protege IDs verificados manualmente por el operador |
| D10 | No se requiere `@DDD-Designer` | — | Ver sección siguiente |

---

## ¿Requiere @DDD-Designer?

**No.** Justificación explícita:

- No se crean nuevas entidades de dominio ni value objects de scoring.
- `photo_url` y `heatmap_url` son strings simples — atributos de datos del jugador. No
  tienen invariantes de negocio, no participan en el cálculo de SFA pts, no introducen
  nuevos `ActionType` ni multiplicadores.
- El flujo es enrichment de datos externos puro: fetch → transform → persist URL. Patrón
  idéntico al ya implementado para `fbref_id`, `understat_id` y `photo_url` (vía
  API-Football).
- `SofascorePlayerDTO`, `SofascorePlayerRow` y `SofascoreEnrichmentResult` son DTOs de
  transferencia (frozen dataclasses), no entidades de dominio.

---

## Nuevos componentes — resumen

| Capa | Archivo | Tipo |
|------|---------|------|
| `domain/enrichment_ports.py` | DTOs: `SofascorePlayerDTO`, `SofascorePlayerRow`, `SofascoreEnrichmentResult` | Frozen dataclasses |
| `domain/enrichment_ports.py` | Protocols: `SofascoreProviderPort`, `SofascoreEnrichmentRepositoryPort` | Protocol / runtime_checkable |
| `domain/ports.py` | `PlayerDTO.heatmap_url`, `PlayerScoreDTO.heatmap_url` | Campo nuevo con default None |
| `infrastructure/providers/` | `SofascoreProvider` | Nueva clase |
| `infrastructure/repositories/` | `SofascoreEnrichmentRepository` | Nueva clase |
| `application/use_cases/` | `EnrichSofascorePhotoUseCase` | Nuevo use case (Fase A) |
| `application/use_cases/` | `FetchSofascoreHeatmapUseCase` | Nuevo use case (Fase B) |
| `tasks/` | `sofascore_tasks.py` | Dos nuevas Celery tasks |
| `api/v1/admin.py` | 3 endpoints admin nuevos | `POST` endpoints |
| `infrastructure/models/players/` | Columna `heatmap_url TEXT` | Migration SQL |

---

## Integraciones externas

| Endpoint | Método | Auth | Uso |
|----------|--------|------|-----|
| `https://api.sofascore.com/api/v1/search/multi-search?q={name}` | GET | Ninguna | Buscar jugador por nombre → obtener `sofascore_id` |
| `https://img.sofascore.com/api/v1/player/{sofascore_id}/image` | — | — | URL de foto (se construye, no se fetcha) |
| `https://api.sofascore.com/api/v1/player/{sofascore_id}/heatmap/{unique_tournament_id}/{season_id}` | — | — | URL del heatmap PNG (se construye, no se fetcha) |

**Rate limiting:** la API de Sofascore no documenta límites públicamente. El provider
implementa retry con backoff (2 reintentos, 10s de espera). Las tasks Celery tienen
`max_retries=2`, `default_retry_delay=60`.

**IDs de Sofascore conocidos (referencia para el operador):**
- La Liga 2024/25: `unique_tournament_id=8`, `season_id=61644`
- Premier League 2024/25: `unique_tournament_id=17`, `season_id=61627`
- Champions League 2024/25: `unique_tournament_id=7`, `season_id=61644`
(Los IDs reales deben verificarse en Sofascore antes de usarlos en producción.)
