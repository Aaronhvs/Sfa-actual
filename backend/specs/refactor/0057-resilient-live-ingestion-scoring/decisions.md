# Resilient Live Ingestion And Final Fixture Scoring

## Contexto de negocio

La ingesta automatica de la temporada 2026/2027 dejo de producir nuevos puntos aunque Celery
Beat continuaba sano. El incidente combina tres fallos: una frecuencia de dos minutos que agota
la cuota de API-Football, retries improductivos cuando la cuota diaria ya esta agotada y una
recalculacion completa encolada por cada competencia ingerida.

Ademas, la ingesta puede persistir `player_events` mientras el fixture sigue `1H` o `2H`. El replay
ELO crea snapshots exclusivamente para fixtures finales (`FT`, `AET`, `PEN`), pero el repositorio
de scoring intenta leer eventos de cualquier status. Un unico partido vivo sin snapshot bloquea
el recalculo completo de la temporada y deja pendientes todos los partidos posteriores.

El fix debe restaurar el procesamiento incremental sin debilitar la temporalidad ELO ni inventar
contexto para partidos vivos. Celery Beat permanece detenido en produccion hasta ejecutar el
runbook de despliegue y recuperacion definido en `plan.md`.

## Restricciones

- API-Football tiene cuota diaria y puede comunicar su agotamiento dentro de una respuesta HTTP
  exitosa; esa condicion no es transitoria antes del reset diario y no debe tener retry HTTP ni
  retry Celery.
- Los errores transitorios, como timeout, HTTP 429 de ventana corta o indisponibilidad temporal,
  conservan la politica de retry acotada existente.
- El intervalo normal de `ingest_today` sera 10 minutos. Sigue siendo configurable mediante
  `INGEST_INTERVAL_MINUTES`, con default 10 y el mismo valor explicito en produccion.
- ELO y scoring comparten la lista autoritativa de estados finales: `FT`, `AET`, `PEN`.
- La ausencia de snapshot ELO en un fixture final sigue siendo un error. No se permite fallback a
  ELO actual, fuerza neutral, standings ni snapshots sinteticos.
- La ingesta por competencia conserva su comportamiento actual cuando se ejecuta de forma manual;
  solo el orquestador por lote puede diferir la recalculacion.
- No se crean tablas, modelos SQLAlchemy, entidades de dominio ni endpoints nuevos.
- La recuperacion debe ser idempotente: repetirla sobre los mismos fixtures no duplica eventos,
  scores, snapshots ni totales de temporada.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Cambiar el default y la configuracion productiva de `INGEST_INTERVAL_MINUTES` a 10 | Mantener 2 minutos | Reduce el consumo base y evita ciclos superpuestos frecuentes sin perder seguimiento util de partidos vivos |
| Representar el agotamiento diario con una excepcion explicita compartida por el port de ingestion y el provider | Detectarlo por texto en cada task | Permite distinguir una condicion no reintentable de errores transitorios sin acoplar Celery al payload de API-Football |
| Ante limite diario, detener el lote, registrar resultado `quota_exhausted` y no invocar `self.retry` | Esperar 65 segundos o reintentar la task | La cuota no se recupera dentro del ciclo y los retries forman la tormenta observada |
| Mantener retry acotado para 429 de ventana corta, timeout y fallos HTTP transitorios | Desactivar todos los retries | El incidente solo justifica cortar la cuota diaria; los fallos recuperables deben seguir tolerados |
| Anadir `enqueue_recalculation` al helper interno de ingesta, con default `True`; `ingest_today` y catch-up lo usan en `False` | Quitar toda recalculacion automatica de la ingesta | Preserva los callers manuales y permite que el lote controle un unico efecto posterior |
| Acumular las competiciones/pools afectados y encolar exactamente un `apply_elo_pools_then_recalculate_task` al terminar el lote | Encolar una task por competencia | Un replay ELO de temporada y un full recalculation son operaciones de pool, no de competencia individual |
| Si la cuota se agota despues de ingestas exitosas, encolar una sola recalculacion para el progreso ya confirmado antes de cerrar el lote | Descartar todo el progreso parcial | Los commits de ingesta ya son independientes; consolidarlos evita dejar datos validos sin score hasta el dia siguiente |
| Filtrar `PlayerEventScoreRepository.get_events_for_recalc` por `Fixture.status IN ('FT','AET','PEN')` | Crear snapshots ELO para `1H`/`2H` o ignorar globalmente snapshots faltantes | Alinea el universo de scoring con ELO y evita puntuar un partido cuyo resultado aun puede cambiar |
| Conservar la validacion de snapshots despues del filtro final | Omitir eventos finales sin snapshot | Un fixture final incompleto debe fallar de forma visible para proteger M1 y la trazabilidad temporal |
| Crear una task diaria de catch-up que reutiliza la ingesta dirigida sobre una ventana movil de tres dias y encola una sola recalculacion | Ejecutar manualmente un full recalc o consultar toda la temporada | Recupera status, stats y eventos perdidos tras cuota/caida con costo acotado e idempotencia existente |
| Programar catch-up una vez al dia despues del reset UTC de API-Football y permitir ejecucion manual con la misma funcion | Aumentar retries de `ingest_today` | Separa recuperacion de la vigilancia live y ofrece una operacion repetible para produccion |
| Proteger cada orquestacion con un lock no bloqueante por season y tipo de ciclo | Permitir que Beat acumule lotes/recalculos | Si un ciclo anterior sigue activo, el siguiente termina como `already_running` en vez de crear backlog |

## Flujo objetivo

1. Beat dispara `ingest_today_task` cada 10 minutos.
2. La task adquiere un lock no bloqueante para la temporada; si existe otro ciclo, termina sin retry.
3. Consulta las fechas live establecidas y selecciona fixtures de la whitelist.
4. Ingiere las competencias secuencialmente con recalculacion diferida.
5. Si hay una excepcion de cuota diaria, detiene nuevas llamadas y no hace retry.
6. Si al menos una ingesta termino, resuelve una vez los pools afectados y encola una sola task
   `apply_elo_pools_then_recalculate_task`.
7. ELO genera snapshots solo para fixtures finales.
8. Scoring lee eventos solo de esos mismos fixtures finales y mantiene error estricto si falta un
   snapshot final.
9. El catch-up diario revisa los ultimos tres dias, reingiere de forma dirigida y ejecuta el mismo
   cierre de lote con una sola recalculacion.

## Limites arquitectonicos

- `domain/ingestion_ports.py`: excepcion tipada de cuota diaria; no contiene detalles de HTTP o
  Celery.
- `infrastructure/providers/api_football.py`: clasifica limite diario frente a errores
  transitorios y cierra el retry HTTP para el primero.
- `tasks/ingest_today_task.py`: adaptador de entrada y orquestador del lote; no calcula scores ni
  accede a modelos ORM.
- `tasks/ingestion_tasks.py`: conserva el wiring de ingesta y expone la opcion interna para diferir
  el unico recalculo del lote.
- `infrastructure/repositories/player_event_score_repository.py`: aplica el filtro SQL de estados
  finales antes de validar cobertura temporal.
- `celery_app.py`: configura los schedules de vigilancia y catch-up.

No se requiere `core/dependencies.py` porque no se agregan routers ni wiring HTTP. Las Celery tasks
mantienen late imports, ownership de sesion y commits en los adaptadores existentes.

## Recuperacion e idempotencia

El catch-up usa una ventana movil de tres fechas UTC, incluye fixtures live que deban actualizar su
status y fixtures finales que necesiten completar stats/eventos. La persistencia existente por
external ID y los upserts de eventos/scores son la base de idempotencia. El cierre siempre reproduce
el pool ELO completo y reconstruye los totales desde `player_event_scores`, por lo que dos ejecuciones
con la misma entrada deben producir los mismos conteos y totales.

La recuperacion del incidente se realiza primero con Beat detenido: desplegar, ejecutar catch-up
manual para cubrir el 20-23, esperar el unico recalculo, auditar conteos y solo entonces volver a
encender Beat.

## Integraciones externas

- API-Football `/fixtures?date=YYYY-MM-DD` para vigilancia y descubrimiento de catch-up.
- Los endpoints ya usados por `IngestCompetitionUseCase` para fixtures, stats y eventos dirigidos.
- Redis/Celery como broker. El lock puede usar el mecanismo compartido ya disponible; no se agrega
  persistencia de negocio para coordinar tareas efimeras.

## Domain Model

No aplica. El cambio agrega una excepcion tecnica de integracion y politicas de orquestacion. No
introduce entidades, aggregates, value objects futbolisticos ni cambios en formulas de scoring.
