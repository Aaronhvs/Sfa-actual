# Operación 0069: season-2025

## Alcance y procedencia

Destino autorizado: reconstruir el periodo 2025/2026 con la configuración activa v4, no reproducir v3. Los pares se resuelven con `SeasonRepository.resolve_scope('season-2025')`. Incluyen Mundial 350/2026 y excluyen los clubes de season-2026. El corte inventariado contiene 2.840 fixtures y 21 competiciones; son datos del manifiesto, no constantes del clasificador.

Implementación aislada: `C:/Users/formu/sfa-season-integrity`, basada en main ef5e070. Producción contiene correcciones publicadas adicionales: el candidato operativo se compone sobre e60a2ac, imagen `sfa-matchday-mvp:20261026-ebb1a11`, conservando su motor y sus posiciones publicadas. No desplegar main completo encima de ese runtime.

## Archivos y base aislada

En el VPS: `/home/ubuntu/sfa-change-backups/season-integrity-20261026/`.

- `production-before.dump`: copia completa consistente, restaurada en `sfa_integrity_2025_test`.
- `manifest.json`, `requests.jsonl`, capturas `*-events.json`, `*-players.json`, `*-fixture.json`: evidencia GET adquirida secuencialmente, nunca durante apply/replay.
- `plans-final-v2.json`: plan definitivo, parser event-integrity-v2.
- `journal/`: intención y snapshots antes/después de cada revisión.
- `publication-journal/`: fingerprint antes/después del corte completo.
- `integrity_before_2025`: archivo SQL exacto de raw, Stats, versiones 3/4, rollups, bonos y honores, más dependencias congeladas.
- `integrity_after_2025`: resultado preparado, solo proyección v4 en serving.
- `integrity_published_2025`: after real con IDs de producción y mapa de nuevas PE; se crea atómicamente junto al corte.

La restauración completa encontró una FK preexistente inválida: 30 bonos huérfanos de clubes season-2026 ya presentes en producción. No se reparan como efecto secundario. Las tablas objetivo y sus imágenes before se restauraron y compararon exactamente. Conservar el dump y ese diagnóstico.

## Preparación y cierre

Los scripts se ejecutan con el código del candidato, `PYTHONPATH=src`, URL de la base aislada y clave API vacía. Nunca imprimir credenciales.

1. `scripts/reconcile_season_event_integrity.py prepare --directory ARCHIVE --plan-file plans-final-v2.json`.
2. `apply` con el mismo plan: CAS por fixture, journal durable y transacciones acotadas.
3. `normalize-context`: equipo del fixture, is_away y diferencia algebraica; no club actual del jugador.
4. `recalculate`: una transacción sobre los pares exactos, UCs existentes de scoring v4, bonos y honores. Rechaza bases no terminadas en `_test`. Usa exclusivo try-only y capacidad LOCAL del protocolo 0065; no recalcula ELO.
5. Auditar elegibilidad, identidad PE/PES, rollups, bonos, posición/contexto, psxg y datos fuera de scope. Preparar de nuevo: no debe quedar ninguna revisión aplicable; warnings/pending conservados son admisibles y se enumeran.
6. Congelar/exportar before/after y dependencias con tipos y conteos verificados. Las tablas privadas CTAS no son migraciones del esquema de producto.

No borrar datos para igualar totales: los conflictos entre API events y API players, identidades desconocidas y timelines incompatibles permanecen explícitos. Una respuesta vacía no acredita una ausencia. Los raw de porteros permanecen aunque v4 excluya su puntuación.

## Publicación y reversión

Primero ensayar en la base aislada: CAS fallido, publicación con rollback antes del commit, promoción completa y reversión exacta con rollback. Medir duración y comprobar que `sfa.position_publication` no queda activado al terminar. La suite opt-in `test_season_integrity_publication_postgres.py` solo acepta la base aislada exacta.

Antes del corte: verificar hashes y suite del candidato, preparar imagen sin activarla, pausar beat, drenar y parar worker. Importar los esquemas privados ya verificados y comparar su procedencia; no importar tablas public ni restaurar el dump sobre producción.

`scripts/publish_season_integrity_projection.py --directory ARCHIVE` simula y hace rollback por defecto. Para producción se requiere `--production`; `--commit` confirma el corte. El UC adquiere exclusivo try-only antes de cualquier lectura. Busy implica rollback y nueva transacción; nunca upgrade ni espera exclusiva encolada.

El adaptador comprueba before completo, dependencias before/after/live, nuevas apariciones no autorizadas, versiones, FKs y scores que referencian eventos. Reserva IDs nuevos con secuencias, conserva IDs existentes por clave lógica y rechaza colisiones fuera del scope. Usa exclusivamente la capacidad LOCAL de publicación 0065 después de CAS/journal y la desactiva antes de comprobar el resultado. No deshabilita triggers/FKs, no usa replication_role ni resetea secuencias. Toda protección que retenga una fila provoca fallo de comparación y rollback.

Los lectores conservan el corte anterior hasta commit. La transacción publica la proyección ya preparada; no calcula puntos. Verifica after real exacto y conserva su mapa antes del commit; después escribe la marca committed. Invalida solo caches relacionadas, activa los servicios del candidato y comprueba salud, ranking 2025 y funcionamiento de season-2026.

Revertir usa `--revert` y el mismo protocolo: CAS contra after publicado, restauración exacta before y verificación. Si hay cambios/referencias posteriores, abortar y preparar una nueva reparación; no eliminarlos. Los schemas privados before/after/published se conservan durante la ventana de recuperación. No rebobinar secuencias. No repetir una publicación cuyo estado se desconozca: comparar DB con before/published y sus fingerprints.

## Validación registrada

- Baseline de main limpio: 785 passed, 25 skipped.
- Rama de reparación antes del ensayo PostgreSQL completo: 830 passed, 30 skipped (pruebas de integración opt-in).
- Ensayo v1 previo: coherencia de 52 goles Mbappé, 26 Dembélé, cero eventos elegibles sin puntuar; resultado provisional sustituido por replay v2 desde before exacto.
- Parser v2: 2.840 capturas preparadas; 967 fixtures con revisiones, 2.103 operaciones y 160 normalizaciones de contexto. Bloqueos: 123 sin PlayerStats, 5 correspondencias ambiguas y 5 timelines con marcador incompatible; warnings localizados adicionales se conservan por componente.
- El recálculo lento anterior fue cancelado y revertido íntegramente en la base aislada para reutilizar el protocolo LOCAL 0065; no fue una publicación productiva.
- Replay v2 completo: cero cambios aplicables. Resultado: 93.256 PES v4, cero raw elegibles sin puntuar; 4.005 exclusiones GK esperadas. Mbappé 52/52/52, Dembélé 26/26/26 y Raúl García 11/11/11 (Stats/raw/PES).
- Suite del runtime productivo más el parche: 1.253 passed, 43 skipped; cobertura nueva 89,65 %. Ensayo completo de publicación, rollback antes del commit, promoción real en clon, restauración exacta y rollback de la restauración; datos fuera del scope conservados. La suite tardó 604,45 s incluyendo varios cortes y fingerprints completos, no un solo cutover.
- Se conservan 250 bonos de porteros sin rollup de puntuación: exclusión existente del motor. El validador acepta exclusivamente ese caso; una entrada equivalente de un jugador de campo bloquea la publicación.
- Preflight productivo: solo cambiaron last_updated de 999 rollups Mundial350/2026/v4, cero cambios materiales. El archivo original se conserva en integrity_before_initial_2025; integrity_before_2025 es una copia operativa separada. Tras pausar escritores se admite únicamente ese delta de timestamps bajo exclusivo y comparación exacta de todo el resto, con journal; después se repite el CAS completo. Cualquier cambio material aborta el corte.

## Cierre productivo: 28 de octubre de 2026

Publicado y verificado por HTTPS. Código main f587460; release operativo baf739d, imagen `sfa-season-integrity:20261026-baf739d`, construida sobre la imagen probada para conservar exactamente Python y dependencias. API, worker y beat reanudados y saludables.

La copia operativa adoptó 459 nombres sin cambios de identidad, posición, edad ni rol efectivo; 32 identificadores de logros y sus 711 bonos se reconciliaron por claves naturales con equivalencia semántica completa. Solo se modificó staging durante esa preparación. Se conservaron original inmutable, mapa y journal; los importes de after no cambiaron. La simulación de adopción terminó en rollback y pasó el CAS completo antes del corte real.

El corte atómico tardó 127,47 segundos. Journal de publicación: `season-2025-publish-f45318a208854be1b73b00981750e327`. Después del commit: 93.256 puntuaciones v4, suma de eventos 37.571.653,97; cero eventos elegibles sin puntuar, cero divergencias de identidad, cero descuadres de rollups y bonos. El top 10 de season-2026 conserva jugadores y puntos respecto al instante anterior al corte. Los ocho MVP destacados siguen respondiendo. La petición explícita de v3 para season-2025 devuelve indisponibilidad 409, sin ranking parcial; el archivo permanece disponible para restauración.

Comprobación pública: Mbappé puesto 4, 91.571,08 puntos y 52 goles; Dembélé puesto 26, 60.464,88 puntos y 26 goles. No se cambiaron reglas ni se intentó ajustar el resultado al Balón de Oro.

Artefactos definitivos en el directorio operativo: `production-data-final.json`, `public-verification-final.json`, `deployment.jsonl`, `top50-before-after.csv`, `pending-evidence.csv`, snapshots y journals. Quedan incidencias de evidencia: 19 diferencias Stats/raw de goles y 219 de asistencias; 123 fixtures sin PlayerStats del proveedor, cinco correspondencias ambiguas y cinco timelines bloqueados. El estado es **recalculado y publicado con incidencias pendientes**, no reconciliación absoluta del proveedor.
