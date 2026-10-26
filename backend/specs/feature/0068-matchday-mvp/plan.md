# Plan:0068 — MVP de la jornada

## Archivos y componentes

- [x] Crear `domain/matchday_mvp.py`: DTOs frozen/ports, RoundKey/policy y selección jugador-fixture/desempate/reasons. Sin scoring nuevo ni aggregate. [DDD]
- [x] Crear use cases `get_tournament_mvps.py` y `get_latest_tournament_mvps.py`, con Protocol/Fakes completos, resolución de temporada/scope/versión idéntica a ranking y catálogo/existencia separados.
- [x] Crear repository MatchdayMvpRepository para captura batched: fixtures, puntos, stats/contexto/eventos/ELO y proyección exacta de rankingcompetición. Extraer/reusar helper leads sin modificar su comportamiento.
- [x] Crear schema matchday MVP y respuestas exactas; añadir rutas tournaments.py y DI core/dependencies.py. Registrar latest estática primero y errores404/409/validación. Actualizar `http/tournaments.http` o archivo específico con ambos endpoints.
- [x] Implementar Redis cache port/adaptador opcional120s por huella robusta y policy/versión; fallback DB ante caída, captura coherente y sin consultas API/mutaciones de datos.

## Checklist verificable

- [x] Comparar tipos/frontend contrato de ambos endpoints y conservar todos los campos/IDs/nulls; competición existente sin datos200[], inexistente404; latest incluye8destacadas en orden explícito.
- [x] Agregar puntos Decimal por jugador/fixture con todos los scores de una sola versión, incluidosSTATS, sólo FT/AET/PEN. No mínimo/positivo0066, honors/bonos ni suma multifixture del jugador.
- [x] Resolver equipo/side por stats/eventos verificados y contexto de fixture; no Player.team_id. Goals/assists fuente única preferida stats, fallback canónico, sin duplicar tandas/STATS ni multiplicar joins.
- [x] Validar score_before home:away y corroborar score_diff antes de behind/level; null+diff0 imputado no genera level, contradicción no inventa razón ni cambia la acción destacada. DI pasa preferred_rules_version_id activo como ranking.
- [x] Aplicar empate puntos→goals+assists→playerid asc→fixture.externalid asc. Seleccionar evento gol/assist mayor final_points para behind/level previo; bigrival≥50 temporal, away y knockout del fixture. Ausencia no inventa razones.
- [x] Política de ligas/fase liga con stage admitido; excluir preliminares regular/null, no confundir knockout matchday16/32/64 con jornada. Keys estables y orden numérico/fases.
- [x] Implementar legs explícitos o pairing local estricto de dosfixtures/loc.alternas/cronología distinta; más de2/contradicción/incompleto queda sin grupo soportado. Keys stage+leg y tests calendario/status/orden input. No agrupar todo knockout por fecha.
- [x] Final/single solo bajo formato explícito; supercopas válidas permitidas en detalle, no latest8. Rechazar etapasfinal masivas malrotuladas como Copa22/FA90 sin fabricar finales.
- [x] pending/complete según calendario persistido conocido con finales exactos; aplazados/cancelados pendientes, grupos sin scores se omiten. Latest selecciona ronda más reciente con candidato aunque provisional; partido aplazado de ronda antigua no altera orden de rondas.
- [x] Posición coincide con helperranking(scope,competition_id) publicado0065 y lectura actual; tests aceptadaMCO/override y transferencia. No usar Player.position ni sfa_current_position aislado.
- [x] Cache detecta updateinplace y redistribución con suma constante, finalización/reversión de fixture, reglas/policy/posición; fallo Redis sigue respondiendo. No COUNT/MAXsolo ni manifiestos enormes por fila.
- [x] Tests unit/use case con Fakes completos y todos los casos del contrato; integración PostgreSQL de sumas/joins/versiones/proyección/huellas, esquema y rutas HTTP. Sin nueva ingesta/recalc para preparar pruebas productivas.
- [x] Suite baseline worktree760/20skip registrada; suite final sin fallos, cobertura nuevo/diff≥80 %, lint/isort y deuda global explícita; benchmark frío/caliente y EXPLAIN sin N+1 porfixture/jugador.
- [x] Commit exclusivo desde worktree limpio y patch sobre release productiva real c8e4ca0/sfa-leads-positions preservando extras existentes, no main completo. Smoke endpoints/frontend live, ganador contra SQL y enlaces external_id; reportar fases omitidas por datos ambiguos. No cargar cambios de otros worktrees.

## Agent Routing Brief

**DDD Designer needed:** yes.

DDD ya consultado para RoundKey y reglas de clasificación/cobertura, sin entidades ni aggregate nuevo. Política arquitectónica admite pairing local estricto para legs por instrucción del coordinador; los resultados conservan su base inferida y limitaciones, no se califican metadata oficial. Implementación puede comenzar tras leer este plan completo; el producto es backend read model de dos endpoints, sin workflow de publicación de puntos ni otro proveedor.

## Validation before deployment

- Clean baseline: 760 passed, 20 skipped; production-image baseline: 1188 passed, 28 skipped.
- Full candidate with isolated PostgreSQL: 800 passed, 10 skipped; all 30 new tests pass.
- New coverage: domain 98.68%, use cases 96.49% / 100%, repository 100%, cache 97.56%, schemas 100%.
- Independent SQL confirms all 10 La Liga winners. Round 10: Mbappe, 3317.99 points, fixture 1570426.
- Latest includes eight competitions in the requested order. Read-only benchmark: cold 3.42s / warm 0.81s; 52 / 9 queries, bounded per competition.
- EXPLAIN: fingerprint 104.85ms, performance aggregation 81.68ms. No additional index/migration justified.
- Changed files pass lint/isort. No pending files from the primary workspace included.

## Deployment complete

Final release: 1218 passed, 28 skipped, zero failures. Both public endpoints and desktop/mobile history verified. See verification.md for release IDs, evidence and data limits.
