# Plan: Scrapling — Fix FBref 403 + Advanced Metrics

## Archivos a crear

- [ ] `backend/migrations/versions/XXXX_add_fbref_advanced_metrics_to_player_stats.py`
      — migración Alembic que añade 7 columnas nullable a `player_stats`:
      `passes_pct NUMERIC(5,2)`, `passes_into_final_third SMALLINT`,
      `passes_into_penalty_area SMALLINT`, `sca SMALLINT`, `sca_passes_live SMALLINT`,
      `sca_dribbles SMALLINT`, `gca SMALLINT`

## Archivos a modificar

- [ ] `backend/requirements/base.txt` — añadir `scrapling[fetchers]` con comentario
      indicando que requiere `scrapling install` en el Dockerfile
- [ ] `backend/enviroments/production/Dockerfile` — añadir `RUN scrapling install`
      inmediatamente después del `pip install`
- [ ] `backend/enviroments/development/Dockerfile` — mismo cambio que producción
- [ ] `backend/src/sfa/domain/enrichment_ports.py` — extender `FBrefPlayerStatsDTO`
      con 7 campos nuevos
- [ ] `backend/src/sfa/infrastructure/providers/fbref_scraper.py` — reemplazar
      `_get_html` (httpx) por `StealthyFetcher` wrapeado en executor; añadir URLs y
      parsers para `/passing/` y `/gca/`; extender `fetch_league_player_stats` para
      poblar los nuevos campos del DTO
- [ ] `backend/src/sfa/infrastructure/models/player_stats/models.py` — añadir las 7
      columnas nuevas al modelo SQLAlchemy `PlayerStats`
- [ ] `backend/src/sfa/application/use_cases/enrich_with_fbref.py` — añadir los 7
      campos nuevos al dict `stats_to_update` que se pasa a
      `update_player_stats_from_fbref`

---

## Checklist de implementación

### Paso 1 — Dependencias: `requirements/base.txt`

- [ ] Añadir al final de `backend/requirements/base.txt`:
  ```
  scrapling[fetchers]>=0.2.0  # requiere `scrapling install` en Dockerfile para binarios Camoufox
  ```
- [ ] No eliminar `httpx` — puede ser usado por otros módulos.

### Paso 2 — Docker: añadir `scrapling install` en ambos Dockerfiles

- [ ] En `backend/enviroments/production/Dockerfile`, modificar el bloque `RUN` de pip
      para que quede:
  ```dockerfile
  RUN python -m pip install --upgrade pip && \
      pip install -r /requirements/production.txt && \
      scrapling install
  ```
- [ ] Aplicar el mismo cambio en `backend/enviroments/development/Dockerfile`:
  ```dockerfile
  RUN python -m pip install --upgrade pip && \
      pip install -r /requirements/local.txt -r /requirements/test.txt && \
      scrapling install
  ```
- [ ] Verificar que el build de Docker termina sin errores y que el directorio de
      binarios de Camoufox existe en la imagen resultante.

### Paso 3 — Domain DTO: extender `FBrefPlayerStatsDTO`

- [ ] En `backend/src/sfa/domain/enrichment_ports.py`, añadir los siguientes campos
      al dataclass `FBrefPlayerStatsDTO` (todos con default = 0 / 0.0 para
      retrocompatibilidad con tests existentes):
  ```python
  # Passing table
  passes_pct: float = 0.0               # % pases completados (0–100)
  passes_into_final_third: int = 0       # pases al último tercio
  passes_into_penalty_area: int = 0      # pases al área
  # GCA table
  sca: int = 0                           # Shot-Creating Actions totales
  sca_passes_live: int = 0              # SCA desde pases en juego
  sca_dribbles: int = 0                 # SCA desde regates
  gca: int = 0                          # Goal-Creating Actions totales
  ```
- [ ] Los campos nuevos van **después** de `psxg_total` para no romper constructores
      posicionales existentes en tests.

### Paso 4 — Infra model: columnas nuevas en `PlayerStats`

- [ ] En `backend/src/sfa/infrastructure/models/player_stats/models.py`, añadir
      antes de `__table_args__`:
  ```python
  passes_pct: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True, default=None)
  passes_into_final_third: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  passes_into_penalty_area: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  sca: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  sca_passes_live: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  sca_dribbles: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  gca: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
  ```
- [ ] Añadir `CheckConstraint` a `__table_args__` para cada campo entero no negativo:
  ```python
  CheckConstraint("passes_into_final_third >= 0", name="ck_ps_passes_into_final_third"),
  CheckConstraint("passes_into_penalty_area >= 0", name="ck_ps_passes_into_penalty_area"),
  CheckConstraint("sca >= 0", name="ck_ps_sca"),
  CheckConstraint("sca_passes_live >= 0", name="ck_ps_sca_passes_live"),
  CheckConstraint("sca_dribbles >= 0", name="ck_ps_sca_dribbles"),
  CheckConstraint("gca >= 0", name="ck_ps_gca"),
  ```
- [ ] No añadir `CheckConstraint` para `passes_pct` (nullable, puede ser None).

### Paso 5 — Migración Alembic

- [ ] Desde el entorno de desarrollo con la DB corriendo, ejecutar:
  ```bash
  alembic revision --autogenerate -m "add_fbref_advanced_metrics_to_player_stats"
  ```
- [ ] Verificar que el archivo generado contiene `op.add_column` para las 7 columnas
      con los tipos correctos (`sa.Numeric(5, 2)` para `passes_pct`, `sa.SmallInteger()`
      para las demás).
- [ ] Verificar que `downgrade()` contiene los 7 `op.drop_column('player_stats', ...)`.
- [ ] Aplicar la migración: `alembic upgrade head`.

### Paso 6 — Infra provider: reemplazar `_get_html` con Scrapling

- [ ] En `backend/src/sfa/infrastructure/providers/fbref_scraper.py`:
  - Eliminar `import httpx` y el dict `_HEADERS`.
  - Añadir imports:
    ```python
    import asyncio
    from functools import partial
    from scrapling.fetchers import StealthyFetcher
    ```
  - Reemplazar el método `_get_html` completo por:
    ```python
    async def _get_html(self, url: str) -> str:
        loop = asyncio.get_event_loop()
        for attempt in range(3):
            try:
                fetcher = StealthyFetcher()
                fetch_fn = partial(fetcher.fetch, url, headless=True, network_idle=True)
                page = await loop.run_in_executor(None, fetch_fn)
                if page.status != 200:
                    raise RuntimeError(f"FBref returned status {page.status} for {url}")
                return page.html_content
            except Exception as exc:
                if attempt == 2:
                    raise
                wait = 15.0 * (attempt + 1)
                logger.warning(
                    "FBref request failed (attempt %d), retrying in %.0fs: %s",
                    attempt + 1, wait, exc,
                )
                await asyncio.sleep(wait)
        raise RuntimeError("Unreachable")  # pragma: no cover
    ```
  - **Nota:** `page.status` y `page.html_content` son los atributos de la respuesta de
    Scrapling. Si la API de la versión instalada difiere, ajustar según la documentación
    (`page.status_code`, `page.content`, etc.) — verificar en la instalación real.

### Paso 7 — Infra provider: añadir URLs para `/passing/` y `/gca/`

- [ ] En `fbref_scraper.py`, añadir dos nuevos dicts de URLs a nivel de módulo, junto
      a `LEAGUE_STATS_URLS` y `LEAGUE_SHOOTING_URLS`:
  ```python
  LEAGUE_PASSING_URLS: dict[str, str] = {
      "La Liga":          "https://fbref.com/en/comps/12/passing/La-Liga-Stats",
      "Premier League":   "https://fbref.com/en/comps/9/passing/Premier-League-Stats",
      "Bundesliga":       "https://fbref.com/en/comps/20/passing/Bundesliga-Stats",
      "Serie A":          "https://fbref.com/en/comps/11/passing/Serie-A-Stats",
      "Ligue 1":          "https://fbref.com/en/comps/13/passing/Ligue-1-Stats",
      "Champions League": "https://fbref.com/en/comps/8/passing/Champions-League-Stats",
  }

  LEAGUE_GCA_URLS: dict[str, str] = {
      "La Liga":          "https://fbref.com/en/comps/12/gca/La-Liga-Stats",
      "Premier League":   "https://fbref.com/en/comps/9/gca/Premier-League-Stats",
      "Bundesliga":       "https://fbref.com/en/comps/20/gca/Bundesliga-Stats",
      "Serie A":          "https://fbref.com/en/comps/11/gca/Serie-A-Stats",
      "Ligue 1":          "https://fbref.com/en/comps/13/gca/Ligue-1-Stats",
      "Champions League": "https://fbref.com/en/comps/8/gca/Champions-League-Stats",
  }
  ```

### Paso 8 — Infra provider: parsers para `/passing/` y `/gca/`

- [ ] Añadir método `_parse_passing_table(self, html: str) -> dict[str, dict]` a
      `FBrefScraper`. Retorna `{player_name: {"passes_pct": float, "passes_into_final_third": int, "passes_into_penalty_area": int}}`.
  - Buscar la tabla con `soup.find("table", {"id": "stats_passing"})`.
  - Si no la encuentra, intentar `soup.find("table", {"id": "stats_passing_dom_lg"})`.
  - Si ninguna existe, loguear warning y retornar `{}`.
  - Por cada fila, extraer:
    - `_cell_text(tr, "player")` → clave del dict
    - `_to_float(_cell_text(tr, "passes_pct"))` → `passes_pct`
    - `_to_int(_cell_text(tr, "passes_into_final_third"))` → `passes_into_final_third`
    - `_to_int(_cell_text(tr, "passes_into_penalty_area"))` → `passes_into_penalty_area`

- [ ] Añadir método `_parse_gca_table(self, html: str) -> dict[str, dict]` a
      `FBrefScraper`. Retorna `{player_name: {"sca": int, "sca_passes_live": int, "sca_dribbles": int, "gca": int}}`.
  - Buscar la tabla con `soup.find("table", {"id": "stats_gca"})`.
  - Si no existe, loguear warning y retornar `{}`.
  - Por cada fila, extraer:
    - `_cell_text(tr, "player")` → clave
    - `_to_int(_cell_text(tr, "sca"))` → `sca`
    - `_to_int(_cell_text(tr, "sca_passes_live"))` → `sca_passes_live`
    - `_to_int(_cell_text(tr, "sca_dribbles"))` → `sca_dribbles`
    - `_to_int(_cell_text(tr, "gca"))` → `gca`

### Paso 9 — Infra provider: extender `fetch_league_player_stats`

- [ ] En `fetch_league_player_stats`, después de la llamada a la tabla de shooting
      (y su `asyncio.sleep`), añadir:
  ```python
  passing_by_player: dict[str, dict] = {}
  passing_url = LEAGUE_PASSING_URLS.get(league)
  if passing_url:
      passing_html = await self._get_html(passing_url)
      await asyncio.sleep(self._RATE_LIMIT_SECONDS)
      passing_by_player = self._parse_passing_table(passing_html)

  gca_by_player: dict[str, dict] = {}
  gca_url = LEAGUE_GCA_URLS.get(league)
  if gca_url:
      gca_html = await self._get_html(gca_url)
      await asyncio.sleep(self._RATE_LIMIT_SECONDS)
      gca_by_player = self._parse_gca_table(gca_html)
  ```
- [ ] En el loop de construcción de `FBrefPlayerStatsDTO`, añadir lookup a
      `passing_by_player` y `gca_by_player` por `name`, y poblar los nuevos campos:
  ```python
  passing = passing_by_player.get(name, {})
  gca_data = gca_by_player.get(name, {})
  result.append(FBrefPlayerStatsDTO(
      # ... campos existentes ...
      passes_pct=passing.get("passes_pct", 0.0),
      passes_into_final_third=passing.get("passes_into_final_third", 0),
      passes_into_penalty_area=passing.get("passes_into_penalty_area", 0),
      sca=gca_data.get("sca", 0),
      sca_passes_live=gca_data.get("sca_passes_live", 0),
      sca_dribbles=gca_data.get("sca_dribbles", 0),
      gca=gca_data.get("gca", 0),
  ))
  ```

### Paso 10 — Application use case: incluir nuevos campos en el enriquecimiento

- [ ] En `backend/src/sfa/application/use_cases/enrich_with_fbref.py`, en el bloque
      donde se construye `stats_to_update`, añadir los 7 campos nuevos:
  ```python
  stats_to_update = {
      "xg":                       dto.xg,
      "xa":                       dto.xa,
      "progressive_passes":       dto.progressive_passes,
      "progressive_carries":      dto.progressive_carries,
      "passes_pct":               dto.passes_pct,
      "passes_into_final_third":  dto.passes_into_final_third,
      "passes_into_penalty_area": dto.passes_into_penalty_area,
      "sca":                      dto.sca,
      "sca_passes_live":          dto.sca_passes_live,
      "sca_dribbles":             dto.sca_dribbles,
      "gca":                      dto.gca,
  }
  ```
- [ ] El método `update_player_stats_from_fbref` en `EnrichmentRepository` ya itera
      genéricamente sobre el dict `stats` usando `getattr(PlayerStats, field)` — no
      requiere cambios, siempre que los nombres de clave coincidan exactamente con los
      nombres de columna del modelo.
- [ ] **Verificar** que `passes_pct` usa el mismo patrón `field == 0` en el CASE WHEN.
      Para un campo nullable (`Numeric`, default `None`), el CASE WHEN `col == 0` no
      coincidirá con `NULL` — esto es correcto: si la columna es `None` (primera vez),
      el UPDATE la sobreescribirá directamente. Sin embargo, el CASE WHEN actual en
      `update_player_stats_from_fbref` usa `(col == 0, val), else_=col`. Para `None`
      inicial, `col == 0` es `False` y `else_` devuelve `None` → el campo no se actualiza.
      **Solución:** para `passes_pct`, el modelo debe usar `default=0.0` y `nullable=False`
      en lugar de `nullable=True` (ajustar Paso 4 en consecuencia), o bien el repositorio
      debe manejar el caso nullable con `OR col IS NULL` en el CASE WHEN. **Decisión:**
      cambiar `passes_pct` a `nullable=False, default=0.0` — el valor 0.0 indica "sin dato"
      de la misma forma que los demás campos int con default 0. Ajustar el Paso 4 y la
      migración Alembic para reflejar esto.

### Paso 11 — Tests: FBrefScraper con Scrapling mockeado

- [ ] En `backend/tests/`, localizar o crear `tests/infrastructure/providers/` y añadir
      `test_fbref_scraper.py`.
- [ ] Mockear `StealthyFetcher.fetch` (o el `run_in_executor`) para retornar HTML de
      fixture con las 4 tablas: `stats_standard`, `stats_shooting`, `stats_passing`,
      `stats_gca`. El HTML de fixture puede ser un string mínimo con un `<table>` por
      tipo, con las columnas `data-stat` necesarias.
- [ ] Verificar que `fetch_league_player_stats("La Liga")` retorna una lista de
      `FBrefPlayerStatsDTO` con los 7 campos nuevos correctamente poblados.
- [ ] Verificar que si la tabla `stats_passing` no existe en el HTML, el campo
      `passes_pct` del DTO es `0.0` y no se lanza excepción.
- [ ] Verificar que si `stats_passing_dom_lg` existe (fallback para Champions League),
      el parser la usa correctamente.

### Paso 12 — Tests: `EnrichWithFBrefUseCase` con campos nuevos

- [ ] Localizar `tests/use_cases/test_enrich_with_fbref.py` (o crear si no existe).
- [ ] Actualizar el `FakeFBrefProvider` para que retorne `FBrefPlayerStatsDTO` con los
      7 campos nuevos con valores no-zero (ej: `passes_pct=87.3`, `sca=42`, `gca=7`).
- [ ] Actualizar el `FakeEnrichmentRepository` para capturar el `stats` dict pasado
      a `update_player_stats_from_fbref`.
- [ ] Asserción: el dict `stats_to_update` debe contener las 7 claves nuevas con los
      valores correctos del DTO.

### Paso 13 — Verificación de calidad

- [ ] Ejecutar `pytest tests/` — sin regresiones, coverage ≥ 80%.
- [ ] Ejecutar `flake8 src/ tests/` — sin errores nuevos.
- [ ] Ejecutar `isort --check-only src/ tests/` — sin errores.

---

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no introduce nuevas entidades de dominio ni value objects. Los cambios
de dominio se limitan a:

1. Añadir 7 campos con tipos primitivos a `FBrefPlayerStatsDTO` (dataclass frozen
   existente) — extensión de datos, no nuevo concepto de negocio.
2. Los campos nuevos (SCA, GCA, passes_pct) son métricas observadas del mundo real,
   no abstracciones de dominio que requieran invariantes o reglas de construcción
   complejas.

El cambio más crítico (Scrapling `StealthyFetcher` + executor) vive íntegramente en
la capa de infraestructura. No hay ActionType nuevo, no hay fórmula de scoring nueva,
no hay Port nuevo.

---

## Verificación end-to-end

1. **Build Docker sin errores:**
   ```bash
   docker build -f enviroments/production/Dockerfile -t sfa-test .
   ```
   El build debe completar `scrapling install` sin error. Verificar:
   ```bash
   docker run --rm sfa-test python -c "from scrapling.fetchers import StealthyFetcher; print('OK')"
   ```

2. **Migración aplicada:**
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'player_stats'
     AND column_name IN ('passes_pct', 'passes_into_final_third', 'passes_into_penalty_area',
                         'sca', 'sca_passes_live', 'sca_dribbles', 'gca');
   ```
   Debe retornar 7 filas.

3. **Scraper no recibe 403:**
   Ejecutar directamente desde Python (con Scrapling instalado localmente) o desde el
   contenedor:
   ```python
   from sfa.infrastructure.providers.fbref_scraper import FBrefScraper
   import asyncio
   result = asyncio.run(FBrefScraper().fetch_league_player_stats("La Liga"))
   print(len(result), result[0])
   ```
   Debe retornar > 200 jugadores sin lanzar excepción. El primer DTO debe tener
   `xg > 0` (confirma que la tabla standard se parseó) y `sca > 0` para jugadores
   de campo.

4. **Enriquecimiento persiste campos nuevos:**
   Después de ejecutar la Celery task de enrichment para La Liga:
   ```sql
   SELECT player_id, passes_pct, sca, gca
   FROM player_stats
   WHERE season = '2024-2025'
     AND (passes_pct > 0 OR sca > 0)
   LIMIT 10;
   ```
   Debe retornar filas con valores no-zero.

5. **Pedri / Vitinha spot-check:**
   ```sql
   SELECT p.name, ps.passes_pct, ps.sca, ps.gca,
          ps.passes_into_final_third, ps.sca_passes_live
   FROM players p
   JOIN player_stats ps ON ps.player_id = p.id
   WHERE p.name ILIKE '%Pedri%' OR p.name ILIKE '%Vitinha%'
     AND ps.season = '2024-2025';
   ```
   Pedri debe mostrar `passes_pct > 80`, `sca > 40`, `gca > 5` (valores típicos
   de un mediocampista creativo top de La Liga).
