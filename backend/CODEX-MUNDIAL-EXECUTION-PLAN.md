# Mundial 2026 - Plan de ejecucion de fixes beta

Este documento agrupa los fixes finales reportados para cerrar la beta del Mundial.
La regla general es: no mezclar cambios estructurales sin spec, no romper clubes, y validar
todo primero en local antes de llevar a VPS/produccion.

## Orden recomendado

1. Backend/spec con Claude: invocar `@Architecture-Engineer` desde `backend/`.
2. Frontend/diseno: antes de construir, leer/aplicar `high-end-visual-design`.
3. Frontend/implementacion: usar `impeccable craft`, con shape brief confirmado.
4. Recalculo local: correr seed/enrichment/recalculate solo despues de validar migraciones/config.
5. Produccion: backup DB, pull/build, migraciones, seed/enrichment, recalc, smoke tests.

## Parte A - Para Claude / Architecture-Engineer

Ejecutar esto desde `backend/` en Claude:

```text
@Architecture-Engineer

Necesito crear un spec de cierre para la beta Mundial 2026 de SFA.

Contexto:
- El proyecto es SFA backend, FastAPI + SQLAlchemy async + PostgreSQL + Celery + Redis.
- Seguir estrictamente backend/CLAUDE.md.
- Architecture-Engineer nunca debe escribir codigo, solo producir decisions.md + plan.md usando /sfa-spec.
- Si algo toca dominio de scoring o posiciones con reglas nuevas, evaluar si hace falta @DDD-Designer.
- Ya existe CODEX-MUNDIAL-FIXES.md con la lista de fixes reportados.
- Produccion esta en VPS, por lo que todo debe ser compatible con rollout seguro: backup, migraciones idempotentes, build, recalc y smoke tests.

Objetivo del spec:
Planificar los fixes finales de Mundial 2026 sin romper el sistema de clubes.

Fixes a cubrir:

1. Scoring Mundial DEL/EXT sin xG/xA real
- Solo Mundial beta.
- La DB no tiene expected_goals ni expected_assists.
- XG_NO_GOAL se deriva de shots_on - goals.
- XA_NO_ASSIST se deriva de passes_key - assists.
- Propuesta a validar: passes_completed DEL 1 -> 2, EXT 1 -> 3, mantener MCO=2 y MF=7.
- Debe recalcularse localmente y compararse impacto antes de produccion.

2. Explicabilidad de detalle de partido por jugador
- Cambio aplicable a todas las competiciones.
- Mostrar mejor M1, rival superior/inferior, local/visitante/neutral, minuto, estado del partido, alta presion si aplica.
- Mostrar conteos del partido: pases completados, pases totales/precision, tiros al arco, tiros totales, pases clave, regates, duelos, tackles/intercepciones, bloqueos, faltas, tarjetas.
- No inventar xG/xA real. Si se muestra proxy, nombrarlo claramente como pase clave sin asistencia o remate al arco sin gol.

3. Click desde partido del jugador hacia detalle Mundial
- Solo para World Cup.
- Si una fila/tarjeta de partido del jugador es Mundial, click debe navegar a /mundial/partido/{fixture_external_id}.
- El detalle debe mostrar marcador, cronologia, formaciones y stats.

4. Cronologia/eventos en vivo
- Ya existen fixture_events, fetch_fixture_events, save_fixture_events y get_fixture_events.
- Validar si falta frontend/endpoint/schema para mostrar cronologia completa.
- Soportar goles, tarjetas, sustituciones y eventos disponibles por API-Football.
- Evitar duplicados en re-ingestas.

5. Celery beat para Mundial activo
- Actualmente ingest_today_task corre cada 30 minutos.
- Proponer bajar a 10 minutos durante Mundial.
- Mantener ACTIVE_COMPETITIONS limitado a (1, 2026).
- Confirmar que ingesta encola recalculate con scoring active version.
- Definir rollback: volver a 30 minutos despues del Mundial o hacerlo configurable por env var.

6. Banderas faltantes en mobile Mundial
- Equipos reportados: Ivory Coast/Costa de Marfil, Curaçao/Curazao, New Zealand/Nueva Zelanda, South Africa/Sudafrica, Bosnia & Herzegovina/Bosnia.
- Probable causa: alias de nombre vs codigo ISO/flag frontend.
- Validar en fixtures, ranking, detalle de partido, perfil de equipo.

7. Busqueda ranking Mundial por seleccion/pais
- En ranking Mundial, escribir Argentina debe mostrar jugadores de Argentina.
- Debe buscar por player name y team/country.
- Respetar limite actual, pero no ignorar matches por seleccion.

8. Seccion Paises/Selecciones en pagina Mundial
- Despues de grupos, agregar "Paises" o "Selecciones".
- Orden dinamico por puntos SFA acumulados por jugadores de esa seleccion.
- Click lleva al perfil del equipo.

9. Perfil de seleccion Mundial
- Mostrar total de goles.
- Fuente debe ser consistente con marcador oficial: preferir fixtures/resultados del equipo para goles del equipo, y dejar claro si se agrega tambien goles de jugadores.

10. Alineaciones espejadas
- Auditar render de alineaciones.
- Ejemplo reportado: Colombia vs Uzbekistan, Colombia aparece en espejo, Luis Diaz en lado contrario.
- No corregir manualmente sin entender si el problema viene de coordenadas API, orientacion home/away o CSS.

11. Corrector/enriquecimiento de posiciones Mundial
- Verificar si corre el corrector de posiciones.
- Messi aparece como MC pero deberia EXT/DEL para Argentina.
- Kimmich puede ser MC por club, pero lateral con Alemania.
- Evaluar overrides manuales por competicion/seleccion sin romper clubes.

12. Local: temporadas de clubes no visibles
- Auditar si es dato faltante, filtro frontend, cache, API local, seed/migracion o mismatch de season/rules_version.
- No tratarlo como bug Mundial.

13. Banderitas en clubes
- Aplicar estilo de flag similar a Mundial en superficies de clubes.
- Definir regla exacta: pais del club, liga o jugador, para evitar flags incorrectas.

14. Metodologia
- Documentar B1.
- Explicar rangos 17-20 y 35+, solo goles/asistencias, tabla +200/+400/+600, y que esta activo solo Mundial beta si corresponde.

15. Ranking Mundial filtro por posicion
- Igual que ligas normales.
- Debe combinar con busqueda por jugador/seleccion.

Entregable:
- Crear un spec nuevo con decisions.md y plan.md.
- Incluir Agent Routing Brief.
- Dividir el plan por fases: quick wins seguros, backend API/data, frontend UX, scoring/recalculo, produccion.
- Cada item debe tener criterio de completitud verificable.
- Incluir comandos de verificacion local y smoke tests.
```

## Parte B - Para frontend con high-end-visual-design + impeccable craft

Antes de editar frontend:

```bash
cd frontend
node .agents/skills/impeccable/scripts/load-context.mjs
```

Luego usar este brief para `high-end-visual-design` y despues `impeccable craft`.

```text
Primero aplicar high-end-visual-design.
Luego ejecutar impeccable craft para construir/pulir las superficies Mundial.

Shape brief:
- Producto: SFA, ranking y seguimiento del Mundial 2026.
- Registro: product UI, no landing page.
- Usuario: fan/analista que quiere entender por que un jugador sube en el ranking mientras sigue partidos en vivo.
- Estetica: mantener identidad SFA actual, futbol premium, oscuro, denso, escaneable, con energia de torneo. No redisenar toda la marca.
- Objetivo UX: que el usuario entienda el puntaje sin leer metodologia larga.

Superficies frontend:
1. Ranking Mundial
- Agregar filtro por posicion.
- Buscar por jugador y seleccion/pais.
- Mantener limite y performance.

2. Mundial home
- Despues de grupos, agregar seccion Paises/Selecciones ordenada por puntos SFA acumulados.
- Cards compactas, escaneables, con bandera, nombre, puntos, goles, rank.

3. Perfil de seleccion
- Mostrar total de goles, puntos SFA acumulados, mejores jugadores, partidos.

4. Detalle de partido Mundial
- Cronologia clara arriba o cerca de formaciones.
- Eventos: minuto, tipo, jugador, asistencia si existe, equipo.
- Cuidar mobile.

5. Detalle de partido en perfil de jugador
- Mostrar explicabilidad de multiplicadores: rival superior/inferior, M1, local/visitante/neutral, alta presion.
- Mostrar stats reales del partido: pases completados/totales, tiros al arco/totales, pases clave, regates, duelos, tackles/intercepciones, bloqueos, faltas, tarjetas.
- Si es Mundial, click a /mundial/partido/{fixture_external_id}.

6. Banderas
- Resolver flags faltantes mobile.
- Reusar helper/mapping central, no parches por componente.

Guardrails:
- No nested cards.
- No romper densidad desktop ni mobile.
- No usar textos largos explicativos dentro de la UI.
- No inventar xG/xA real.
- Verificar con screenshots desktop y mobile.
```

## Parte C - Lo que puede ejecutar Codex directamente

Estas tareas son de bajo riesgo y no requieren nuevo spec si se hacen como ajustes chicos:

1. Cambiar Celery beat de 30 a 10 minutos para Mundial, o mejor hacerlo configurable por env var.
2. Verificar que `ingest_today_task` sigue limitado a `ACTIVE_COMPETITIONS={(1, 2026)}`.
3. Añadir/ajustar tests de schedule si existe cobertura para `celery_app`.
4. Auditar query local de xG/xA y dejar evidencia de que no existen columnas reales.
5. Agregar B1 a metodologia si la pagina ya tiene estructura simple y no requiere nuevo endpoint.
6. Fix de flags si ya existe un mapping central claro en frontend.
7. Smoke tests locales:
   - Ranking Mundial carga.
   - Filtro por posicion funciona.
   - Busqueda por Argentina trae jugadores argentinos.
   - Detalle partido muestra cronologia.
   - Perfil jugador navega a detalle Mundial.

## Parte D - Riesgos y orden de rollout

### Riesgo alto

- Cambios de scoring DEL/EXT: requieren recalculo y comparativa antes/despues.
- Overrides de posicion por seleccion: pueden afectar rankings y clubes si no se modelan bien.
- Alineaciones espejadas: puede ser CSS/orientacion/API, auditar antes.

### Riesgo medio

- Nuevos endpoints/agregaciones de selecciones por puntos SFA.
- Busqueda ranking por team/country.
- Cronologia en vivo si hay duplicados o eventos incompletos.

### Riesgo bajo

- Celery 30 -> 10 min con whitelist Mundial.
- Metodologia B1.
- Flags si hay mapping central.

## Verificacion local minima

```bash
cd backend
docker compose -f docker-compose-development.yml exec -T api pytest tests/use_cases -q
docker compose -f docker-compose-development.yml exec -T api pytest tests/domain -q
```

Smoke API esperado:

```text
GET /api/v1/wc/fixtures
GET /api/v1/wc/fixtures/{fixture_external_id}
GET /api/v1/ranking?season=2026&competition_id=350
GET /api/v1/ranking?season=2026&competition_id=350&position=EXT
GET /api/v1/ranking?season=2026&competition_id=350&name=Argentina
```

## Produccion

1. Backup DB.
2. Confirmar rama/commit.
3. Build/restart API y worker.
4. Migraciones si aplica.
5. Seed/enrichment si aplica.
6. Recalculo Mundial `season=2026`, `competition_id=350`, active rules version.
7. Smoke tests por HTTP.
8. Revisar logs worker.
9. Validar UI desktop/mobile.
