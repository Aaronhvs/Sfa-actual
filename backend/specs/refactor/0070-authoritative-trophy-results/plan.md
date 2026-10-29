# Plan: resultados autoritativos y títulos pendientes de PSG

## Archivos a crear

- [ ] Contrato/DTO de resultado final y plan de corrección de título en domain; adaptación de ports existentes cuando baste.
- [ ] `application/use_cases/prepare_competition_title_correction.py` y `apply_competition_title_correction.py`, repositorio de corrección y CLI privado con journal/CAS/revert.
- [ ] Migración aditiva de penaltis/procedencia de Fixture (número reservado contra runtime real), política de datos intercontinental-title-v1 y tests/runbook de operación.

## Archivos a modificar

- [ ] `infer_achievements_ports.py`, `infer_achievements_repository.py` e `infer_competition_achievements.py`: resultado durable, finales válidas, separación de playoffs y diff-upsert sin DELETE-all.
- [ ] Provider/DTO de fixtures y modelo Fixture: conservar score.penalty y procedencia sin alterar goles ordinarios ni insertar lanzamientos sintéticos.
- [ ] Catálogo/scope de competición y selección de políticas de títulos: Intercontinental separada, sin cambio global de config v4 ni confusión con World Cup.
- [ ] Repositorio de achievements y cierre CalculateAchievementBonusesUseCase: preservar IDs equivalentes y cerrar los pares/rangos afectados. Factories solo en core/dependencies.py.

## Checklist de implementación

1. [ ] Leer plan completo y skills sfa-use-case/sfa-repository/sfa-scoring/sfa-test y sfa-celery-task únicamente si se modifica una task. Ejecutar baseline completo y registrar runtime/commit/schema real; construir desde la release que conserva extras, no reemplazarla por main limpio.
2. [ ] Archivar status y fuentes acotadas por IDs, una llamada cada vez con cuota compartida y reserva comprobada. Revisar 1377400, standings/calendario Ligue1 y final Intercontinental. Conservar respuestas/hash y diferenciar missing/conflict de cero; sin HTTP durante apply.
3. [ ] [DDD] Aplicar invariantes ya dictaminadas: partido/tanda separados, PEN con ganador autoritativo, fases de campeonato separadas de permanencia y pending conservador. DTO frozen; no nuevas entidades.
4. [ ] Persistir penaltis y procedencia de manera aditiva y compatible. Probar nulls, orden home/away, tanda tras90 y tras120, empate/no dato/conflicto, sin goles o minutos sintéticos ni cambios del scorer.
5. [ ] Reparar evidencia de liga, recuperar fixture ausente si procede y registrar champion PSG según clasificación final validada. Excluir playoffs auxiliares del inferidorKO; planear retirada exacta de los dos logros falsos y sus bonos con before/after.
6. [ ] Resolver Super Cup por resultado verificado y generar winner/runner-up; no degradar final irresuelta a semi_final ni perder resultados previamente correctos. Upsert diferencial preserva IDs/created_at; ningún DELETE-all.
7. [ ] Incorporar ID/scope/política Intercontinental después de validar identidad y participación contextual. Aplicar winner4000×0,5/runner0 con política versionada archivada, sin modificar config v4; future inference no la convierte en cero. Si falta evidencia, dejar componente pendiente explícito sin frenar liga/supercopa verificadas.
   - [ ] Title-only usa la rama existente sin performance con copia local inmutable de configuración y participación real; no consulta ranking fallback ni rating. Marcar rendimiento no evaluado/factor neutral1 y policy_id. SSS sin PES conserva event_points0/matches_played0 según contrato actual, bono real y apariciones/minutos en Stats/detalles. Probar rebuild/repetición y que no se filtra la copia local a liga/supercopa/config persistida.
8. [ ] Simular cierre íntegro de bonos, pares, rollups/honores dependientes con UCs existentes. Comparar todos los jugadores, títulos ya correctos y exclusiones; no escribir deltas hipotéticos fijos ni importar actuaciones incompletas.
9. [ ] Probar: fixture faltante no prueba campeón, final standings autoritativa, permanencia no título, tanda90 con PE vacías, tanda120, fuente contradictoria, final no terminada, final ida/vuelta, doble ejecución, IDs estables, títulos correctos conservados, política nueva sin mutar v4 y guardas publicadas.
10. [ ] Ensayar migración/corrección/bonos/revert en PostgreSQL clon con before real, journal y CAS de dependencias; comprobar cero cambios de ELO, posiciones, config v4, Mundial de selecciones y clubes2026. Probar falla intermedia, Busy y rechazo de cambios posteriores al revertir.
11. [ ] Ejecutar suite completa, flake8/isort y cobertura requerida por CI (≥80%, deuda baseline documentada sin ocultarla). Validar SQL real y smoke de ranking/títulos. Revisar diff de release aislado para no incluir trabajo ajeno ni revertir0069.
12. [ ] Con backup/artefactos y gates aprobados, desplegar release compatible, pausar/drenar escritores para CAS/aplicación breve, invalidar caches y reanudar servicios. Verificar puntos/títulos y segunda ejecución vacía; registrar pendientes reales y hashes finales. No detenerse en otro preview cuando el lote validado pueda aplicarse.

## Verificación

PSG conserva Champions/Trophée y obtiene los títulos acreditados con bonos calculados desde evidencia. Nice/Saint Étienne dejan de figurar como ganador/subcampeón de Ligue1 por la permanencia. Super Cup funciona sin PE de tanda y sin minuto120 artificial. Intercontinental no duplica Mundial de clubes/selecciones y sus cifras tienen política identificable. Ningún título sin evidencia obtiene puntos. Revert restaura antes exacto si no hay cambios posteriores.

## Agent Routing Brief

**DDD Designer needed:** yes; ya consultado para esta solicitud. Dictamen: reutilizar CompetitionAchievement y DTO frozen de resultado/procedencia; invariantes de tanda, fases de liga y baremo versionado están incorporadas. No requiere otro agregado/plataforma. La implementación debe aplicar esos invariantes y consultar de nuevo solo si amplía el modelo o metodología.
