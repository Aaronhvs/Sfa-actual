# Plan: Detalle de partido en vivo consistente y rediseño para Torneos

## Archivos a crear

- [x] `frontend/src/components/tournaments/match/TournamentMatchHeader.tsx` - cabecera compacta con competencia, fase, equipos, marcador y estado canónico.
- [x] `frontend/src/components/tournaments/match/TournamentMatchMomentum.tsx` - gráfica accesible de impacto SFA por tramos de cinco minutos y estado pendiente.
- [x] `frontend/src/components/tournaments/match/TournamentMatchStatistics.tsx` - comparación continua de estadísticas con barras finas y valores legibles.
- [x] `frontend/src/components/tournaments/match/TournamentMatchTimeline.tsx` - cronología compacta propia del contexto Torneos.
- [x] `frontend/src/components/tournaments/match/TournamentMatchLineups.tsx` - titulares, suplentes y fallbacks responsive.
- [x] `frontend/src/components/tournaments/match/TournamentMatchPerformance.tsx` - ranking SFA del partido sin estilos heredados del Mundial.
- [x] `backend/tests/repositories/test_fixture_detail_repository.py` - cobertura de caché suplementaria y proyección de impacto SFA.

## Archivos a modificar

- [x] `backend/src/sfa/domain/fixture_detail_ports.py` - agregar DTO frozen de tramo SFA y el campo aditivo en el detalle.
- [x] `backend/src/sfa/application/use_cases/get_tournament_fixture_detail.py` - reconciliar el detalle con el fixture local canónico y adjuntar eventos/impacto.
- [x] `backend/src/sfa/infrastructure/repositories/fixture_detail_repository.py` - separar semánticamente suplemento externo, versionar caché y consultar impacto por fixture.
- [x] `backend/src/sfa/infrastructure/repositories/tournament_repository.py` - asegurar que el lookup local exponga todos los campos canónicos requeridos sin ORM fuera de infra.
- [x] `backend/src/sfa/api/v1/schemas/tournaments.py` - reemplazar aliases `Wc*` por schemas propios y agregar `sfa_momentum`.
- [x] `backend/src/sfa/api/v1/tournaments.py` - mapear estado, etiqueta, live, minuto reconciliado y proyección SFA.
- [ ] `backend/src/sfa/core/dependencies.py` - ajustar wiring únicamente si cambia la firma del repositorio/use case; no crear wiring en routers.
- [x] `backend/tests/use_cases/test_get_tournament_fixture_detail.py` - cubrir discrepancias live/final, marcador, minuto y alcance de temporada.
- [x] `backend/http/tournaments.http` - documentar respuestas programada, live, finalizada, parcial y 404.
- [x] `frontend/src/types/index.ts` - definir tipos propios `TournamentMatch*` y la serie de impacto sin aliases del Mundial.
- [x] `frontend/src/api/client.ts` - tipar el detalle de Torneos, permitir bypass de caché y soportar refresco live controlado.
- [x] `frontend/src/pages/TournamentMatchPage.tsx` - dejar de renderizar `MundialMatchPage`, componer la ficha propia y manejar polling/estados.
- [x] `frontend/src/utils/tournaments.ts` - centralizar etiquetas y clasificación de estados utilizadas por lista y detalle.
- [x] `frontend/src/index.css` - agregar estilos `trm-*` con tokens SFA y responsive; no alterar visualmente el Mundial.

## Checklist de implementación

### Preparación y contrato

- [x] Ejecutar `pytest tests/` antes de modificar código y registrar cualquier fallo preexistente.
- [x] Ejecutar `npm run build` antes de modificar frontend y registrar cualquier fallo preexistente.
- [x] Confirmar con una respuesta real del fixture reportado los valores simultáneos en PostgreSQL, API-Football, Redis y endpoint público.
- [ ] Documentar la matriz de estados soportados: programado, primer tiempo, descanso, segundo tiempo, prórroga, penaltis, interrumpido, suspendido, finalizado, aplazado y cancelado.
- [x] Mantener la ruta pública `/torneos/partido/:fixtureId?season=:season` y el endpoint existente sin cambios incompatibles.

### Backend: consistencia live

- [ ] Extender el port de detalle con un método de lectura de impacto SFA y un DTO frozen por tramo, sin importar SQLAlchemy en domain/application.
- [ ] Hacer que `GetTournamentFixtureDetailUseCase` conserve el fixture local obtenido durante la validación y lo use como resumen canónico del response.
- [ ] Definir una función de composición pura que copie equipos, fecha, fase, jornada, estado y marcador desde el fixture local.
- [ ] Derivar `status_label` e `is_live` desde el mismo catálogo de estados canónicos utilizado por el router.
- [ ] Conservar `elapsed` y flags de ganador externos solo cuando el estado externo coincide con el local; devolverlos nulos ante discrepancia.
- [ ] Verificar que una discrepancia local `2H 2-0` contra suplemento `FT 3-0` responda `2H 2-0` y nunca `Finalizado`.
- [ ] Verificar el caso inverso local `FT` contra suplemento live para evitar regresiones de estado.
- [ ] Renombrar/versionar la clave Redis del suplemento para invalidar snapshots completos previos al despliegue.
- [ ] Mantener TTL corto para suplementos live y TTL largo para suplementos finales, sin permitir que el objeto cacheado reemplace el resumen canónico.
- [ ] Mantener la validación de fixture, temporada y `participant_kind=club` antes de cualquier solicitud externa.
- [ ] Mantener fallos de secciones suplementarias como arrays vacíos/nullable sin degradar el resumen local válido.

### Backend: impacto SFA por tramo

- [ ] Consultar la versión activa de reglas y sumar `final_points` por equipo y bandas de cinco minutos para el fixture solicitado.
- [ ] Excluir `action_type=stats` y cualquier evento sin minuto deportivo representable.
- [ ] Resolver local/visitante usando las apariciones o equipo asociado al evento, y rechazar filas que no correspondan a ninguno de los dos participantes.
- [ ] Retornar los tramos ordenados y con ambos valores explícitos, sin completar ausencia de cálculo con datos inventados.
- [ ] Añadir `sfa_momentum` de forma aditiva al schema y response de Torneos.
- [ ] Confirmar que esta proyección no escribe scores, no recalcula y no modifica el dominio de scoring.

### Backend: schemas, HTTP y pruebas

- [ ] Sustituir los aliases `TournamentMatch* = Wc*` por schemas Pydantic propios con `from_attributes` donde corresponda.
- [ ] Mantener sin cambios el contrato y router del Mundial.
- [ ] Mapear el detalle reconciliado en `api/v1/tournaments.py` sin lógica de negocio adicional.
- [ ] Actualizar `backend/http/tournaments.http` con un fixture live y assertions manuales de estado/marcador.
- [ ] Ampliar el fake del use case para implementar el Protocol completo, sin `MagicMock`.
- [ ] Probar happy path, fixture inexistente, temporada anterior, detalle suplementario ausente y cronología vacía.
- [ ] Probar las dos direcciones de discrepancia local/externa y la regla de `elapsed` nullable.
- [ ] Probar impacto con varios eventos en el mismo tramo, ambos equipos, tiempo añadido, acción `stats` y versión inactiva.
- [ ] Probar que una entrada Redis anterior no altera estado ni marcador canónicos.

### Frontend: separación del Mundial

- [ ] Definir interfaces `TournamentMatchDetail`, `TournamentMatchFixture`, `TournamentMatchTeam`, `TournamentMatchEvent`, `TournamentMatchLineup` y `TournamentMatchMomentumBucket`.
- [ ] Cambiar `fetchTournamentFixtureDetail` para devolver tipos de Torneos y permitir lectura fresca sin reutilizar la caché de 60 segundos.
- [ ] Eliminar la dependencia de `TournamentMatchPage` sobre `MundialMatchPage`.
- [ ] Mantener `MundialMatchPage`, sus tipos `Wc*` y sus clases `wmd-*` funcionalmente intactos.
- [ ] Implementar carga inicial, skeleton estructural, error recuperable, secciones parciales y estados vacíos específicos.
- [ ] Mientras `fixture.is_live` sea true, refrescar con bypass de caché en un intervalo documentado; limpiar siempre el temporizador al desmontar o cambiar de fixture.
- [ ] Detener el polling al recibir un estado final y evitar solicitudes duplicadas cuando una anterior sigue en curso.
- [ ] Mantener navegación hacia atrás por historial con `/torneos` como fallback.

### Frontend: cabecera y navegación

- [ ] Construir una cabecera compacta basada en la jerarquía de `TournamentFixtureRow`, no en el hero del Mundial.
- [ ] Mostrar competencia, fase/jornada, fecha local, escudos, nombres completos, marcador tabular y estado en una lectura única.
- [ ] Mostrar estado live y minuto con señal semántica moderada; mostrar `Final` solo para estados finales canónicos.
- [ ] Mantener marcador deportivo en blanco y reservar oro para valores SFA.
- [ ] Añadir navegación accesible para Resumen, Estadísticas, Cronología, Alineaciones y Rendimiento SFA.
- [ ] Asegurar roles, `aria-selected`, foco visible, navegación por teclado y targets táctiles mínimos.

### Frontend: contenido operacional

- [ ] Diseñar Resumen con columna principal para impacto/cronología y rail para sede, árbitro, formaciones y líderes SFA cuando existan.
- [ ] Etiquetar la gráfica exclusivamente como `Impacto SFA por tramo` e incluir una explicación breve de que representa puntos de acciones calculadas.
- [ ] Representar local y visitante alrededor de una línea base con colores de equipo desaturados y leyenda inequívoca.
- [ ] Mostrar un estado `Impacto SFA pendiente de cálculo` cuando la serie esté vacía.
- [ ] Diseñar estadísticas como lista continua con números blancos, labels legibles y barras finas; no crear una tarjeta por métrica.
- [ ] Separar Cronología de Alineaciones y ordenar eventos por minuto/tiempo añadido.
- [ ] Reinterpretar cancha, titulares y suplentes con clases `trm-*`, tamaños estables y nombres sin solapamiento.
- [ ] Mantener enlaces a perfiles solo cuando exista `player_id` y mostrar puntos solo cuando no sean null.
- [ ] Diseñar Rendimiento SFA como ranking compacto del partido, no como galería de cards.

### Sistema visual, responsive y accesibilidad

- [ ] Usar exclusivamente variables de `frontend/src/index.css`; no hardcodear la paleta oficial en componentes.
- [ ] Eliminar del contexto Torneos el espectro multicolor, fondos radiales, glow y decoraciones del Mundial.
- [ ] Usar Barlow Condensed para nombres/números, Space Mono para estado/minuto/fecha e Inter para texto auxiliar.
- [ ] Mantener radio entre 0 y 6 px y evitar cards dentro de cards.
- [ ] Comprobar contraste AA de texto secundario, estados live, barras y foco.
- [ ] Definir layout estable para 1440 px, 1024 px, 768 px, 430 px y 390 px.
- [ ] En móvil, apilar el rail, permitir scroll horizontal solo en navegación y evitar overflow global de cancha/cronología.
- [ ] Aplicar transiciones menores a 300 ms solo sobre `transform` y `opacity`, con feedback `:active` y fallback `prefers-reduced-motion`.
- [ ] Confirmar que nombres largos, marcadores de dos dígitos, prórroga y tiempo añadido no cambian el ancho de la cabecera.

### Validación final

- [ ] Ejecutar `pytest tests/` y verificar coverage total igual o superior a 80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores.
- [ ] Ejecutar `npm run build` sin errores de TypeScript.
- [ ] Ejecutar `git diff --check` sin errores de whitespace.
- [ ] Verificar con Playwright un fixture live en escritorio y móvil durante al menos dos ciclos de refresco.
- [ ] Verificar con Playwright un fixture finalizado y confirmar que no continúa el polling.
- [ ] Verificar un fixture sin estadísticas, otro sin alineaciones y otro sin scores SFA.
- [ ] Comparar simultáneamente portada y detalle para confirmar igualdad de estado, marcador, equipos y temporada.
- [ ] Realizar comprobación de píxeles/screenshot para ausencia de solapamientos, truncamientos ilegibles y overflow horizontal.
- [ ] Confirmar que `/mundial/partido/:fixtureId` no presenta cambios visuales ni contractuales.

## Agent Routing Brief

**DDD Designer needed:** no

El trabajo amplía DTOs de lectura y una proyección derivada de scores existentes. No crea entidades,
aggregates, value objects, invariantes ni reglas de puntuación. La implementación debe permanecer en
el flujo Router -> Use Case -> Protocol -> Repository y puede ejecutarse sin modelado DDD previo.

## Verificación

1. Abrir en paralelo la portada de Torneos y el detalle de un fixture live; ambos deben mostrar el
   mismo estado, marcador y equipos durante cada actualización.
2. Forzar en los fakes un snapshot local live y un suplemento final; el endpoint debe conservar el
   snapshot local y omitir minuto/ganador incompatibles.
3. Consultar el endpoint de un fixture calculado; `sfa_momentum` debe coincidir con la suma de
   eventos puntuados por equipo y tramo para la versión activa.
4. Abrir un fixture sin cálculo; la interfaz debe mostrar el estado pendiente sin dibujar ceros.
5. Recorrer todas las secciones por teclado en 1440 px y 390 px, sin pérdida de foco ni overflow.
6. Verificar que la ruta del Mundial continúa renderizando su diseño anterior.
