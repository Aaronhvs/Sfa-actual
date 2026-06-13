# Scrapling: Fix FBref 403 + Advanced Metrics (xA, GCA, Passing)

## Contexto de negocio

El scraper de FBref (`infrastructure/providers/fbref_scraper.py`) usa `httpx` con un
User-Agent estático de Chrome. FBref detecta el fingerprint TLS de Python/httpx como
bot y devuelve HTTP 403 para todas las URLs. Esto significa que el enrichment de FBref
(xG, xA, progressive passes, PSxG) **nunca se ha ejecutado con éxito en producción**.

Al mismo tiempo, hay métricas avanzadas de creación de juego que API-Football no provee
y que son críticas para valorar mediocampistas creativos (Pedri, Vitinha, Bellingham):
Shot-Creating Actions (SCA), Goal-Creating Actions (GCA), y métricas de pase a campo
contrario. Estas métricas viven en las tablas `/passing/` y `/gca/` de FBref.

Este refactor resuelve ambos problemas en un solo spec: desbloquea el acceso a FBref y
amplía las métricas scraped a las 7 columnas adicionales que ofrecen diferencial analítico
real respecto a los datos de API-Football.

## Restricciones

- Scrapling `StealthyFetcher` es **síncrono únicamente** — no tiene API async nativa. El
  wrapper en executor es obligatorio para no bloquear el event loop de Celery.
- `scrapling install` descarga binarios de Camoufox (Firefox modificado para fingerprint
  spoofing). Este comando debe ejecutarse en el **Dockerfile durante el build**, no en
  runtime, para que los contenedores arranquen sin descarga en frío.
- FBref impone rate limiting agresivo: el `_RATE_LIMIT_SECONDS = 4.0` existente debe
  mantenerse entre cada URL. Con 4 URLs por liga (standard, shooting, passing, gca) × 6
  ligas = 24 requests por run de enrichment. A 4 s/request el ciclo completo tarda ~96 s,
  dentro del timeout de Celery (300 s por defecto).
- Los campos nuevos (`passes_pct`, `passes_into_final_third`, `passes_into_penalty_area`,
  `sca`, `sca_passes_live`, `sca_dribbles`, `gca`) son **season totals**, no per-fixture.
  Se almacenan en `player_stats` distribuidos entre todos los fixtures de esa temporada
  mediante el mecanismo ya existente `update_player_stats_from_fbref` (field == 0 →
  overwrite). Requieren columnas nuevas en esa tabla y una migración Alembic.
- `xa` ya se almacena en `player_stats.xa` pero **no se usa en ninguna fórmula de scoring**
  actual. El wiring de `xa` en `recalculate_scores` es decisión de negocio separada y
  queda **fuera del alcance de este spec**.
- La tabla `stats_passing` de FBref usa `id="stats_passing"` para partidos domésticos y
  `id="stats_passing_dom_lg"` para ligas con equipos de varios países (Champions League).
  El parser debe intentar ambos IDs.
- La tabla `stats_gca` de FBref usa `id="stats_gca"`.
- `passes_pct` es un porcentaje (ej: `"87.3"`) y se almacena como `Numeric(5, 2)` (0–100).
  Los demás campos nuevos son enteros (`SmallInteger`).
- httpx puede eliminarse del scraper una vez que Scrapling reemplaza `_get_html`, pero
  otras partes del sistema podrían usarlo — **no eliminar de `requirements/base.txt`**.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| `StealthyFetcher` (Camoufox, sin browser completo) | `DynamicFetcher` (Playwright/Chromium) | FBref sirve las tablas en HTML estático — no necesita ejecución de JavaScript. `StealthyFetcher` hace TLS fingerprint spoofing con Camoufox a nivel de red sin levantar un browser completo, reduciendo RAM de imagen Docker en ~400 MB y tiempo de arranque del contenedor |
| Wrappear `StealthyFetcher.fetch()` en `asyncio.get_event_loop().run_in_executor(None, fetcher.fetch, url)` | Refactorizar el scraper a API síncrona | El use case `EnrichWithFBrefUseCase` y la Celery task usan `await` — cambiar a sync requeriría refactorizar la cadena de llamadas. El executor es el patrón estándar de Python para I/O bloqueante dentro de async |
| Extender `FBrefPlayerStatsDTO` con los 7 campos nuevos | Crear `FBrefAdvancedStatsDTO` separado | Todos los campos provienen de FBref, representan al mismo jugador/temporada/liga, y se entregan en la misma llamada a `fetch_league_player_stats`. Un DTO separado requeriría modificar `FBrefProviderPort` y `EnrichWithFBrefUseCase` sin ganancia arquitectónica |
| Columnas nuevas en `player_stats` existente | Nueva tabla `player_fbref_advanced` | Los campos son season totals por jugador, exactamente el mismo granulado que `xg`, `xa`, `progressive_passes` ya almacenados en `player_stats`. El método `update_player_stats_from_fbref` ya implementa el patrón "field==0 → overwrite" genérico que funciona con cualquier columna nueva |
| `xa` wiring en `recalculate_scores` fuera del alcance | Incluirlo en este spec | El wiring de `xa` en la fórmula de scoring requiere una decisión de negocio sobre el `ActionType` correspondiente y cómo afecta a las tablas `BASE_POINTS_TABLE` por posición. Es una decisión de dominio independiente que merece su propio spec |
| `scrapling install` en el `RUN` del Dockerfile (post pip install) | Descargar en primera ejecución | Los binarios de Camoufox (~80 MB) no deben descargarse en runtime — el contenedor tardaría 30–60 s extra en arrancar y fallaría sin conexión a internet en prod |
| Mantener `httpx` en `requirements/base.txt` | Eliminar httpx | Otras partes del sistema (o tests) pueden depender de httpx. La eliminación es un cleanup separado |
| Instanciar `StealthyFetcher` una vez por llamada a `_get_html`, no como singleton de clase | Singleton reutilizable | Scrapling's `StealthyFetcher` no garantiza thread-safety entre llamadas concurrentes distintas; instanciar en cada llamada es seguro y el overhead es mínimo comparado con el rate limit de 4 s |

## Integraciones externas

### FBref (web scraping)

- **URLs nuevas por liga:**

  | Tabla FBref | URL pattern | `id` del `<table>` |
  |---|---|---|
  | Standard stats (ya existente) | `/comps/{id}/stats/{League}-Stats` | `stats_standard` |
  | Shooting (ya existente) | `/comps/{id}/shooting/{League}-Stats` | `stats_shooting` |
  | Passing (nuevo) | `/comps/{id}/passing/{League}-Stats` | `stats_passing` o `stats_passing_dom_lg` |
  | GCA (nuevo) | `/comps/{id}/gca/{League}-Stats` | `stats_gca` |

- **Rate limit:** FBref no documenta un límite oficial, pero bloquea requests rápidos.
  Mantener `_RATE_LIMIT_SECONDS = 4.0` entre cada request. Con 4 URLs × 6 ligas = 24
  requests el ciclo completo tarda ~96 s.
- **Autenticación:** ninguna — acceso público con fingerprint spoofing vía Scrapling.
- **Columnas a extraer de `/passing/`:**
  - `data-stat="passes_pct"` → `passes_pct` (float, porcentaje 0–100)
  - `data-stat="passes_into_final_third"` → `passes_into_final_third` (int)
  - `data-stat="passes_into_penalty_area"` → `passes_into_penalty_area` (int)
- **Columnas a extraer de `/gca/`:**
  - `data-stat="sca"` → `sca` (int, Shot-Creating Actions totales)
  - `data-stat="sca_passes_live"` → `sca_passes_live` (int)
  - `data-stat="sca_dribbles"` → `sca_dribbles` (int)
  - `data-stat="gca"` → `gca` (int, Goal-Creating Actions totales)

- **Fallback ante 403 persistente:** si `StealthyFetcher` recibe 403 después de 3
  intentos, el scraper debe lanzar excepción (comportamiento actual mantenido). El
  `EnrichWithFBrefUseCase` ya captura excepciones y retorna `status="failed"`.

### Scrapling (librería Python)

- **Instalación:** `pip install "scrapling[fetchers]"` + `scrapling install` (descarga
  binarios Camoufox).
- **Versión mínima:** sin pin estricto en este spec — usar la última estable disponible
  en PyPI al momento de implementar. Agregar comentario en `base.txt` explicando el
  requisito de `scrapling install`.
- **API usada:**
  ```python
  from scrapling.fetchers import StealthyFetcher
  fetcher = StealthyFetcher()
  page = fetcher.fetch(url, headless=True, network_idle=True)
  html: str = page.html_content  # equivalente a response.text
  ```
- **`network_idle=True`:** espera a que la red esté inactiva antes de retornar el HTML.
  Necesario para páginas que cargan recursos adicionales antes de renderizar las tablas.
