# Piloto autorizado: temporada 2026/2027

El alcance de esta publicación es exclusivamente `season-2026`: los pares físicos
de club de 2026 que componen ese award period. Excluye la competición 350, el
Mundial y los periodos anteriores. La cohorte se obtiene por IDs de una captura
inmutable, sin nombres especiales: seis XI recientes válidos, soporte de al menos
75 %, primaria de temporada coincidente, sin GK, conflictos ni referencias
aceptadas que puedan ser degradadas. La primera captura contiene 261 candidatos.

Una decisión histórica `curated_fixture_scoring_role` solo autoriza las casillas
compatibles de su allowlist. La categoría representativa `scope_scoring_classification`
se publica por separado para el ranking y la ficha de ese periodo. No modifica
`Player.position` ni crea automáticamente una referencia habitual. Las vistas
filtradas por competición requieren tres observaciones propias concordantes.
Una casilla de titular no acredita el rol durante noventa minutos; la cobertura
del calendario completo sigue siendo desconocida.

El compilador exige paridad completa de eventos, detalles, rollups, bonos y
ranking. Cierra los bonos que dependen del orden entre compañeros, aunque un
compañero no sea reclasificado. El journal incluye sus before/after y los de las
explicaciones invalidadas. La versión 2 del manifiesto valida scope e identidades
también al cargarse; la lectura de manifiestos individuales v1 conserva su hash.

La fuente se compara fila por fila, incluyendo raws derivados con ELO y reglas,
en READ ONLY/REPEATABLE READ. La huella congela conjuntos, valores, configuración
y motor. Publicación y compensación usan una sesión exclusiva desde su primera
lectura, con adquisición inmediata o Busy; todos los writers usan shared desde
la primera lectura. No se hace upgrade ni se espera a una sesión hija shared.
Las guardas SQL son una segunda defensa: conservan filas revisadas y registran
los intentos incompatibles, permitiendo actuaciones nuevas legítimas.

Las revisiones directas y validadas del proveedor se arbitran por instante real
`fetched_at`; versiones equivalentes pueden compartir evidencia semántica. Se
retienen los originales. Un empate incompatible se rechaza en Python y SQL,
independientemente del orden de importación. No se llama al proveedor al preparar,
publicar o revertir este lote. Las heurísticas estadísticas de posición quedan
retiradas; los casos sin evidencia no se convierten en correcciones automáticas.

Validación reproducible:

```text
python -m pytest tests/
python scripts/check_position_transaction_clone.py
python scripts/check_season_position_publication_clone.py <manifest>
POSITION_VALIDATION_CLONE=1 python -m pytest tests/repositories/test_position_read_integration.py
```

Los scripts de mutación de pruebas comprueban el prefijo del nombre del clon.
El ensayo incluye failpoint, CAS obsoleto, idempotencia, conservación frente a
writers, protección de identidades OLD, reversión exacta y rechazo tras cambios
posteriores. El publicador y compensador operativo están en
`scripts/publish_season_position_correction.py`; ambos exigen el manifiesto o batch
exacto. El adapter de entrada es el único dueño de commit.

Para desplegar: backup restaurado, imagen/source manifest congelados, beat
suspendido y worker drenado, migraciones 0053 y 0054 comprobadas en clon, soporte
compatible en API y workers, captura final y nuevo manifiesto sobre producción,
publicación con CAS y smoke. Reanudar worker y beat según su estado previo. Un
Busy o una huella distinta exige rollback/sesión nueva o nueva preparación; nunca
forzar un manifiesto anterior. Conservar los filtros positivos/mínimo de partidos
de 0066 y comprobar listas, totales, búsquedas y Mundial.

La reversión usa el batch en la imagen compatible. Solo restaura before-images
si todas las after-images siguen iguales; deja evidencia e historia durables,
supersede las decisiones y retira la proyección cambiando el estado del batch.
Si existen cambios posteriores requiere otra compensación revisada, sin pisarlos.
El dump completo se reserva para recuperación operacional, no para borrar actividad
posterior a una publicación.
