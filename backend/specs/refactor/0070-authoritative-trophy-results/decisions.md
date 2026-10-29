# Resultados autoritativos y títulos pendientes de PSG

## Contexto de negocio

El usuario autoriza corregir y publicar los títulos pendientes, priorizando PSG y la resolución de tandas. La auditoría del 28 de octubre identifica Ligue 1 2025 sin campeón (305/306 fixtures regulares), un playoff de permanencia tratado como final del campeonato y UEFA Super Cup 2025 sin ganador porque el fallback solo busca penaltis desde minuto 120. Intercontinental 2025 no está catalogada ni tiene baremo. Champions y Trophée des Champions ya constan y deben conservarse.

Fuentes oficiales contrastadas: [UEFA Super Cup 2025](https://www.uefa.com/uefasupercup/history/2025/) confirma 2:2 y tanda 4:3; [FIFA Intercontinental 2025](https://www.fifa.com/es/articles/paris-saint-germain-flamengo-copa-intercontinental-final) y [partido oficial PSG](https://www.psg.fr/es/partidas/futbol-masculino/2025/paris-vs-flamengo-2025-12-17) identifican la final con Flamengo, 1:1 y tanda 2:1. Esas fuentes respaldan el resultado, no sustituyen la validación de IDs del proveedor ni aportan minutos de jugadores inventados.

## Restricciones

- Worktree aislado `C:/Users/formu/sfa-psg-trophies`, base e5e8b52; producción usa la release de integridad con extras ausentes de main. No desplegar una imagen construida desde main que elimine esos extras.
- Preservar el corte 0069, posiciones publicadas, fuerzas/ELO, Mundial de selecciones y clubes season-2026. El título Intercontinental físico 2025 debe pertenecer al periodo club season-2025 mediante ID propio, nunca al ID 350 del Mundial de selecciones.
- Capturas API-Football secuenciales y archivadas: status primero, reserva de cuota, presupuesto explícito dentro de 7.500/día compartidas, sin ingestas paralelas. Sin HTTP durante simulación o publicación. No usar una auditoría global como sustituto de estas correcciones.
- No reemplazar destructivamente todos los achievements de una competición. Conservar IDs y created_at de filas equivalentes; reemplazar/retirar únicamente hechos demostrablemente incorrectos con before/after y cierre de bonos.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
| --- | --- | --- |
| Resultado final del fixture y tanda autoritativa separados | Inferir ganador contando PE o penaltis con minuto >=120 | PE/timeline pueden ser parciales y existen tandas directas tras 90 minutos |
| Clasificar campeonato regular separado de playoffs auxiliares | Toda fila stage=final concede el campeonato | Un playoff de permanencia no otorga el título de liga |
| Diff-upsert por claves naturales y cierre de bonos | DELETE de todos los achievements y recreación | Conserva IDs/FKs y títulos ya correctos |
| Política Intercontinental específica, revisada y versionada | Cambiar configuración global v4 o reutilizar World Cup de selecciones | Añadir un título no debe reinterpretar puntuaciones publicadas |

## Domain Model

DDD-Designer fue consultado. Reutilizar CompetitionAchievement: no hacen falta entidades ni agregados nuevos. Añadir DTO frozen `AuthoritativeFixtureResultDTO` con IDs de competición/temporada/fixture/equipos, estado, goles del partido, penaltis separados, ganador, fuente/hash/revisión y estado verified/conflict/missing. La tanda no se suma a home_goals/away_goals ni genera goles de actuación automáticamente.

Para PEN, requerir resultado completo de tanda no empatado o ganador explícito verificable de fuente autoritativa. Reconciliar participantes y marcador previo empatado. No inventar prórroga, minuto 120 ni intentos individuales para obtener el vencedor. Resultado contradictorio queda pendiente y conserva el logro válido existente; no convertir una final irresuelta en semi_final de cero puntos.

Persistir el resultado consultable de manera durable: columnas nullable de penaltis local/visitante y JSONB de procedencia/revisión en Fixture, mediante migración aditiva cuyo número se reserva contra la release productiva real. El archivo original con hash se conserva fuera de git. Ausencia es NULL, no cero. Reusar home_goals/away_goals para resultado antes de tanda y score_source con su semántica existente; no guardar la tanda dentro de goles. Si producción ya ofrece campos equivalentes, reutilizarlos en lugar de duplicarlos.

## Flujo mínimo y cambios concretos

### 1. Evidencia y liga

Capturar por IDs: final Super Cup externa 1377400, clasificación final y calendario regular Ligue 1 2025; recuperar Toulouse–Nantes J34 realmente ausente, validando competition/team/season y estado. No considerar 305 partidos como prueba de campeón, ni relajar globalmente el gate 306. Si el proveedor devuelve un calendario distinto, resolverlo contra la fuente antes de aplicar. Una clasificación final oficial identificada y revisada puede demostrar campeón sin fabricar fixtures, dejando su cobertura documentada.

InferAchievementsRepository no debe seleccionar fases auxiliares de una liga como KO de su título; la clasificación del formato/fase es por competición y evidencia de round, no por nombres de jugadores/equipos. El final de permanencia Nice–Saint Étienne no concede winner/runner_up doméstico. Retirar esos dos hechos incorrectos y sus bonos dependientes únicamente con evidencia y journal; no borrar fixtures ni sus actuaciones. Registrar PSG champion con 12.000 y peso 0,8 de la política v4 existente. Si se reparan otras posiciones finales de esa liga, aplicar las mismas reglas ya vigentes y mostrar todo el cierre, no solo PSG.

### 2. Supercopa y prevención reutilizable

Cambiar `_resolve_fixture_winner`/`_resolve_final_winner` para consumir resultado verificado del port antes de cualquier conteo de acciones. Los repos obtienen goles finales del fixture y tanda durable, no necesitan que existan PE de lanzadores. El fallback antiguo no puede declarar ganador con conteos parciales; solo usar evidencia completa validada y consistente o preservar pending. Filtrar candidatos por estado final y comprobar estructura de final única/ida-vuelta antes de acumular resultados; no sumar tandas de eliminatorias diferentes. No tocar reglas de gol/tanda del scorer como parte de este arreglo.

Aplicar Super Cup winner PSG y runner-up Tottenham con las reglas actuales (winner 2.000, peso 0,45), conservando otros logros correctos. La simulación previa de Dembélé (+7.776,42 liga y +945 supercopa) es orientación del corte auditado, no constante ni delta que se escriba directamente.

### 3. Intercontinental

Descubrir ID/catálogo/fixtures por proveedor y comprobar identidad con FIFA; no confundir con FIFA Club World Cup ni otra copa por alias. Añadir su fuente club 2025 al periodo season-2025 de forma explícita, sin incorporar otros torneos ni Mundial de selecciones. Capturar final y PlayerStats/participación reales de PSG y Flamengo y el contexto mínimo que requiere CalculateAchievementBonusesUseCase. No repartir bonos usando minutos de Champions ni copiar un ranking de otra competición.

Decisión de baremo para este título: política `intercontinental-title-v1`, winner=4.000, weight=0,5, runner_up=0; 2.000 puntos nominales antes de elegibilidad/participación/rendimiento. Es una decisión editorial conservadora para esta copa, no una equivalencia estadística demostrada. Mantener categoría independiente de selecciones y del Mundial de Clubes; no reutilizar sus importes por compartir organizador.

Implementar esa política como entrada de datos operativos revisada/versionada consumida por el import de logros, guardada en manifiesto y detalles de bonos. Los campos existentes de CompetitionAchievement almacenan importe/peso. No mutar config_json v4 ni activar otra versión para toda SFA. El resolver de logros debe reconocer esa política específica y preservar su procedencia en futuras inferencias, sin devolver cero ni sobrescribirla porque la categoría no existe en config v4. No crear motor paralelo: CalculateAchievementBonusesUseCase sigue calculando desde esos valores con las reglas v4 existentes. Si faltan participación/ranking contextual indispensables, mantener ese componente pendiente y terminar primero liga/supercopa; no fabricar puntos para completar la lista de trofeos.

No introducir puntuaciones individuales de nuevos fixtures de Intercontinental sin la ingesta/scoring completa y contexto requeridos. El alcance inmediato es título y cierre de bonos con evidencia suficiente; cualquier import de actuaciones necesario se simula y declara expresamente en el manifiesto.

El modo title-only debe quedar identificado en manifiesto y detalles: puntos de actuaciones no calculados son cero/ausentes, no prueba de rendimiento nulo. Asegurar que scope, agregados SSS y API de total/títulos incluyan los bonos válidos aunque no existan PES para esa competición; reutilizar la proyección existente o extender su inclusión de bonos, sin fabricar eventos, minutos, partidos ni ELO para forzar un JOIN. Probar total global del jugador y título de competición con esa ausencia de PES. La falta de snapshot de fuerza de Flamengo impide puntuar actuaciones, pero no por sí sola acreditar resultado y título con participación demostrada.

Para `intercontinental-title-v1` title-only, no consultar el rank por SSS ausentes (el fallback 12 no es una evaluación real). Reutilizar la rama existente sin performance del UC con una copia local inmutable de configuración (`enable_performance_based_achievement_bonus=False`), exclusivamente para ese cálculo/política. Fórmula: bonus_points × weight × effective_participation existente, con minutos reales verificados y factor de rendimiento neutral 1; no aplicar rating/rank inventados. Registrar policy_id, title_only=true, performance_not_evaluated=true y performance_factor=1 como neutral operativo, nunca como rendimiento medido. No guardar la copia en rules v4 ni cambiar liga/supercopa u otros cálculos.

El rollup actual define matches_played por fixtures distintos con PES; conservar esa semántica: un SSS de solo bonos sin PES tiene event_points=0 y matches_played=0, junto al bono real. La aparición acreditada y sus minutos se conservan en PlayerStats y detalles de participación; no sumar un partido ficticio a la métrica de actuaciones puntuadas. Si otra vista necesita apariciones reales, leer esos datos explícitamente sin reinterpretar matches_played. Probar que un futuro rebuild del rollup conserva el bono title-only y que el modo neutral no se convierte silenciosamente en rank12 al reejecutar el job.

### 4. Arquitectura y publicación

Un `PrepareCompetitionTitleCorrectionUseCase` reúne resultado/fase/política y produce diff + cierre simulado. Un `ApplyCompetitionTitleCorrectionUseCase` persiste únicamente el plan validado. Puertos DTO en domain; repos SQL/API en infrastructure; CLI de operación sin endpoint público ni task nueva; factories en core. Extender puertos existentes donde corresponda y reutilizar inferencia y CalculateAchievementBonusesUseCase, sin invocar la ruta DELETE-all actual.

Antes/after comprende CA, bonos de todos los jugadores afectados (incluidos Nice/Saint Étienne/Tottenham/Flamengo), rollups/totales y honores dependientes; no solo Dembélé. Congelar configuración, datos de participación, scores usados para rank y posiciones. Probar cierre y cero cambios ajenos en clon compatible con la release. Aplicación y reversión usan journal/CAS y exclusivo try-only del protocolo 0069/0065, GUC LOCAL solo tras validación. No modificar journals previos ni desactivar guardas: si el cierre toca bonos protegidos, incorporar su before verificado y una revisión explícita; no saltarlos silenciosamente.

Publicar código compatible primero con flags/fallback conservador; aplicar el lote verificado durante pausa/drenaje breve de escritores. Idempotencia por clave natural: segunda ejecución sin nuevos IDs ni puntos duplicados. Invalidar caches relacionadas después de commit, reanudar servicios y comprobar API/ranking/títulos. Backup e imágenes exactas permiten reversión CAS sin borrar actividad posterior. La autorización del usuario incluye implementación, pruebas y despliegue al superar estos gates; este documento no declara publicación ejecutada.
