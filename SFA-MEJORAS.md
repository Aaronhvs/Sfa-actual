# SFA: ideas de mejora y orden de trabajo

Fecha: 2026-10-03.
Estado: propuestas para discutir. No hay formulas, pesos ni bonus aprobados.
Alcance: revision del codigo local; no es una auditoria de datos actuales del VPS.
La revision inicial no modifico puntuaciones ni produccion.

## Trabajo aprobado, retomado el 6 de octubre

- Carga del top 10: implementar spinner local sin desmontar podio ni animar datos antiguos.
- Comparador: implementar vistas por pestanas, impacto SFA primero y actuaciones destacadas.
- Equipos: implementar primera edicion descriptiva experimental ELO + SFA observado.
  No es todavia el modelo independiente de fuerza de plantilla propuesto abajo.
  Pesos iniciales visibles 80/20; sin bonus colectivos; nunca alimenta M1.
- M1 enriquecido, contexto clasificatorio y bonus/ajustes de efectividad quedan
  pendientes de discusion. No se autorizo modificar reglas ni recalcular puntos.

## Objetivo

Hacer visible el impacto contextual de los jugadores sin convertir el ranking en una
suma de premios repetidos. Separar tres tipos de trabajo:

- Experiencia visual: puede mejorar sin cambiar ningun punto.
- Metricas descriptivas: explican actuaciones; inicialmente no alteran el ranking.
- Reglas de puntuacion: necesitan simulacion, version nueva y aprobacion explicita.

## 1. Carga de los diez jugadores al paginar

### Diagnostico

En `frontend/src/pages/RankingPage.tsx`, el podio y la lista ya tienen estados
separados. Sin embargo, la clave de la lista usa la pagina solicitada y la direccion
de navegacion antes de recibir la respuesta. Eso remonta y anima los jugadores de
la pagina anterior mientras se espera a los nuevos. El estado ocupado solamente
reduce la opacidad y muestra texto; no ofrece el indicador pedido.

### Propuesta

- Mantener podio, filtros y cabecera inmoviles durante la paginacion.
- Reservar la altura de la lista y mostrar una rueda discreta centrada solo ahi.
- No animar ni presentar los jugadores antiguos como si fueran los nuevos.
- Separar pagina solicitada de pagina confirmada; animar despues del resultado.
- Evitar saltos de scroll, respuestas fuera de orden y parpadeos en cargas rapidas.
- Ante error, recuperar la lista confirmada y ofrecer reintento local.
- Respetar movimiento reducido y comunicar carga con `aria-busy`/estado accesible.

Aceptacion: paginas 1/2/3, busqueda durante carga, red lenta, fallo de red, ultima
pagina, movil y navegacion directa a una pagina. El podio no debe desmontarse.
Coste relativo: bajo. No requiere recalcular ni consultar API-Football.

## 2. Ranking de equipos: resultados y calidad de plantilla

### Que queremos medir

Separar fuerza demostrada del club (resultados/ELO) de calidad y actualidad de su
plantilla. `frontend/src/pages/TeamsPage.tsx` todavia muestra "Proximamente".

No sumar los puntos totales de todos los jugadores: favorece mas partidos, mas
jugadores y posiciones que generan mas puntos. No sumar tambien historia del club
sin justificarlo: ELO ya conserva resultados historicos.

### Modelo candidato, no aprobado

Para cada jugador, usar actuaciones conocidas antes de la fecha de corte:

```text
B_reciente = 90 * sum(peso_fecha * puntos_base) / sum(peso_fecha * minutos)
confianza = minutos_ponderados / (minutos_ponderados + k_minutos)
B_estimado = confianza * B_reciente + (1 - confianza) * B_previo
Q_jugador = normalizar_por_posicion(B_estimado)
Q_plantilla = promedio_ponderado(Q_jugador, pesos_de_participacion)
F_equipo = alpha * ELO_normalizado + (1 - alpha) * Q_plantilla_normalizada
```

Las escalas ELO y plantilla deben ser comparables y usar referencias documentadas.
`alpha`, decaimiento temporal y `k_minutos` se eligen con validacion, no por gusto.
Un ejemplo 70/30 seria solo una hipotesis de ensayo, no una formula final.

- Puntos base: acciones sin multiplicadores de contexto ni bonus colectivos.
- Historico del jugador: prior con menor influencia a medida que hay muestra nueva;
  calcularlo bajo reglas comparables, no mezclar versiones de scoring sin control.
- Si no hay historico fiable, usar referencia de posicion y declarar incertidumbre.
- Plantilla: ponderar participacion prevista usando solo informacion disponible;
  representar porteria, defensa, medio y ataque, no escoger once goleadores.
- Diferenciar fuerza de plantilla habitual y fuerza de una alineacion confirmada.
  No suponer lesiones o disponibilidad que no estan documentadas.
- En un traspaso, la calidad previa acompana al jugador para estimar su nuevo club;
  los puntos historicos del antiguo club no se trasladan al nuevo.
- No considerar semillas manuales de 1000 como evidencia de debilidad real.
  Mostrar procedencia ELO y cobertura; con poca cobertura no inventar precision.

Primera version: ranking descriptivo con fuerza compuesta, ELO, forma de plantilla,
tendencia, fecha y cobertura, sin conectarlo a M1.

Validacion: predecir partidos posteriores con cortes cronologicos; comparar ELO
solo contra ELO + plantilla, medir calibracion/error y retirar componentes que
no aporten. Probar transferencias, inicio de temporada y ligas con distinta cobertura.

## 3. Dificultad del rival con mas contexto

### Hallazgo

`M1RivalDifficulty` compara fuerza propia y rival. Mide desventaja relativa, no
nivel absoluto del oponente. Dos equipos fuertes igualmente parejos pueden tener
el mismo M1 que dos equipos debiles igualmente parejos.

### Propuesta

Distinguir dos preguntas: "que tan fuerte es el rival" y "que desventaja tiene mi
equipo frente a el". Probar un M1 que combine ambas con limites conservadores.
Primero mostrar ambas medidas como informacion, despues decidir su peso en puntos.

- Utilizar snapshots prepartido, nunca ELO posterior ni SFA del propio encuentro.
- No repetir fase/competicion ni localia: corresponden a M2 y Mvisit.
- Revisar limites: la normalizacion ELO a 0-100 puede saturar diferencias.
- Mantener tratamiento separado de acciones decisivas y estadisticas acumulativas.
- Guardar componentes, entradas, procedencia y version para explicar cada calculo.

Riesgo central: SFA final -> fuerza del equipo -> M1 -> SFA final es un circuito de
realimentacion. Usar partidos anteriores no elimina por si solo esa dependencia.
Para M1 usar una medida base independiente del M1 compuesto y de premios colectivos;
el ranking descriptivo y la fuerza de scoring no tienen por que ser el mismo dato.
Evaluar tambien cuanto altera el propio jugador la fuerza de su equipo y su premio.

Dependencia: validar primero el modelo de equipos. Cambio de scoring de alto riesgo.

## 4. Gol o asistencia que cambia una clasificacion

### Hallazgo

M3 conoce minuto y diferencia del marcador del partido, no el global de una
eliminatoria. `Fixture` no representa identificador de cruce, manga ni desempates.
Ademas, el calculo actual limita el minuto a 90: descuento y prorroga requieren
tratamiento explicito antes de premiar ese contexto.

### Propuesta de primera version: describir antes de bonificar

Clasificar cada accion utilizando marcador oficial, timeline reconciliada y reglas:

- Da ventaja definitiva: establece una ventaja que no se pierde hasta el final.
- Rescata un empate: empata y el equipo termina empatando.
- Cambia la situacion de la eliminatoria: pasa de eliminado a provisionalmente
  clasificado, o fuerza prorroga; son etiquetas distintas.
- Resulta decisiva para el pase: comprobar desenlace completo, no afirmar que un
  gol al 90 asegura clasificar si aun hay partido, descuento o desempate pendiente.

Un 3-0 del partido puede ser irrelevante si el global ya estaba resuelto. Un 1-0
puede ser crucial si cambia el global de 1-1 a 2-1. No usar solo minuto o marcador local.

Implementacion necesaria: cruce/mangas, global previo, reglamento de desempate,
prorroga/tanda, eventos anulados y autogoles. Para grupos, tabla y desempates son
una ampliacion distinta. Si faltan datos, mostrar "no evaluable", no cero impacto.

Si posteriormente se otorgan puntos, integrar el contexto en un unico M3 revisado
con limite, no apilar bonus de minuto + empate + clasificacion + multiplicador nuevo.
El bonus colectivo premia el logro; M3 premia la accion. Medir el solapamiento y
su efecto indirecto: mas SFA tambien puede cambiar el reparto del bonus colectivo.

## 5. Comparador enfocado en impacto SFA

### Diagnostico

`ComparePage.tsx` presenta ocho grupos y deja Contexto SFA despues de muchas
estadisticas convencionales. Algunas definiciones actuales son proxies:

- Rival dificil usa `M1 >= 1.15`: describe desventaja relativa, no elite absoluta.
- Momento clave usa `M3 >= 1.6` en eventos puntuados, no una comprobacion del desenlace.
- Actuacion elite usa 2500 puntos fijos, sin ajustar posicion ni minutos.
- Esas "apariciones" son partidos con eventos seleccionados, no todos los partidos
  disputados contra rivales fuertes. Hay que renombrar y definir el denominador.

### Jerarquia visual candidata

1. Identidad, equipo en la temporada elegida, posicion, periodo, minutos y cobertura.
2. Puntos SFA de actuaciones, bonus colectivos por separado y rendimiento por 90
   con advertencia de muestra. No presentar todas las tasas como igualmente fiables.
3. Partidos con impacto clave, porcentaje de oportunidades aprovechadas, puntos en
   esos partidos, contribuciones ante rivales fuertes y acciones que rescatan resultados.
4. Mejor partido, gol mas valioso y evolucion temporal, con acceso a la evidencia.
5. Goles, asistencias, remates, pases, duelos y defensa como detalle secundario.

Lista continua, sin dos columnas de categorias. Valores blancos grandes, etiquetas
legibles, barras mas finas y colores de equipo moderados con identidad textual.
Para reparto comparativo, segmentos proporcionales unidos; no sugerir "probabilidad"
con un porcentaje de reparto. Para valores negativos o no comparables, otra escala.
No convertir ausencia de datos en cero. Comparacion por rol para calidad/percentiles;
entre posiciones distintas, mostrar perfiles sin proclamar ganador universal.

### Nueva metrica: partidos con impacto clave SFA

Contar una vez por jugador/partido si tiene una accion elegible con contexto
verificable: rival de nivel alto absoluto con partido disputado, ventaja definitiva,
empate rescatado o cambio de clasificacion. Etiquetas pueden coexistir; el total es
la union de partidos, no la suma de etiquetas.

Mostrar por separado:

- Cantidad de partidos con impacto clave.
- Partidos/oportunidades elegibles y minutos: no usar un porcentaje sin denominador.
- Tasa de respuesta en cada contexto, con umbrales de muestra pendientes.
- Lista de acciones que justifican el dato y estado de cobertura por categoria.

Definir que es "partido disputado" y "rival fuerte" antes de publicar. No utilizar
M1 relativo como unico criterio. "Importante" no significa simplemente jugar una final.
La primera version sera descriptiva; para defensas/porteros necesitaran definiciones
propias y datos suficientes. No llamarla indice universal usando solo goles/asistencias.

## 6. Efectividad y posible bonus

9 goles / 10 remates = 90%; 9 / 30 = 30%. Describe conversion, pero no distingue
calidad de las ocasiones ni demuestra por si solo mayor impacto. Un 1/1 tampoco
es comparable directamente a una temporada completa.

### Propuesta

- Empezar con conversion descriptiva, remates/minutos y confianza de la muestra.
- Numerador y denominador deben cubrir exactamente los mismos partidos y tipos
  de accion; separar penales, tandas y autogoles. Sin remates desglosados de penal,
  no afirmar que se calculo una conversion no penal fiable.
- Conservar "dato ausente" separado de cero. Hoy el proveedor convierte algunos
  disparos ausentes en cero: corregir ese contrato antes de usarlo para premios.
- Probar suavizado hacia una referencia por posicion/rol:

```text
conversion_ajustada = (goles + k_remates * conversion_referencia) / (remates + k_remates)
```

`k_remates` es un parametro a calibrar; muestras pequenas quedan cerca de la referencia.
Mostrar tambien la tasa observada; la ajustada no debe parecer un dato real medido.

Con xG por ocasion fiable se puede estudiar goles frente a ocasiones esperadas,
pero los proxies agregados actuales no equivalen a xG/PSxG observado por disparo.
No usarlos como certeza sobre dificultad individual ni fingir cobertura completa.

Para otras posiciones: estudiar tasas de duelos/regates/paradas y relacionarlas con
rol, riesgo y calidad de oportunidades. Precision de pase alta no implica aportar
mas si todos los pases son faciles. No copiar conversion de delanteros a defensas.

Mi recomendacion: sin bonus en primera version. El gol ya recibe puntos y existen
otros ajustes de remate; agregar conversion puede premiar dos veces la misma accion
y favorecer perfiles de pocos tiros. Si se ensaya, acotarlo y auditar efectos por rol,
volumen, cobertura y ranking antes de aprobarlo.

## Orden sugerido para discutir

| Paso | Trabajo | Motivo | Cambia puntos |
| --- | --- | --- | --- |
| 1 | Spinner y paginacion local | Molestia concreta, cambio pequeno y aislado | No |
| 2 | Definiciones/cobertura y comparador SFA inicial | Hace visible el valor propio de SFA | No |
| 3 | Contexto de eliminatorias y minutos extendidos | Base necesaria para impacto clasificatorio fiable | No inicialmente |
| 4 | Ranking de equipos experimental | Validar fuerza ELO + plantilla sin afectar scoring | No |
| 5 | Efectividad ajustada descriptiva | Tras resolver cobertura de remates | No |
| 6 | Ensayar M1/M3 nuevos y eventual bonus | Solo con modelos/datos validados | Si, version nueva |

No son seis cambios que deban entrar juntos. El esqueleto visual del comparador y
el prototipo de equipos pueden avanzar en paralelo. El paso 2 empieza con metricas
disponibles y no finge clasificacion/efectividad avanzada antes de los pasos 3/5.

## Decisiones pendientes

- Equipos: fuerza de plantilla, merito deportivo o ambos en un ranking compuesto?
- Impacto clave: solo goles/asistencias inicialmente o esperar criterios por posicion?
- Contexto: describir desenlace real o premiar presion conocida al ocurrir la accion?
- Efectividad: dato explicativo o cambio de puntos? Recomiendo primero lo explicativo.
- Ventanas de forma, priors, pesos, umbrales y caps: decidir tras simulacion, no fijar ahora.

## Plan tecnico y control de calidad

- Datos temporales y procedencia: snapshots con fecha de corte, reglas/modelo y cobertura.
- Dominio: clasificadores de contexto y formulas; use cases para coordinar; repositories
  para lectura/agregacion; wiring en `core/dependencies.py` segun arquitectura existente.
- Agregados servidos por backend/caches invalidables, no reconstruir toda la temporada
  en cada render del comparador. Medir latencias y evitar degradar la carga inicial.
- Prototipos offline reproducibles; no consultar futuro al reconstruir un partido.
- Testear transferencias, cobertura parcial, goleador 1/1, cero real vs dato ausente,
  gol anulado, empate global, prorroga, tanda, goles del mismo minuto y cargas concurrentes.
- Comparar resultados/puntos por posicion, minutos y competicion; mostrar impacto marginal
  y jugadores mas afectados antes de una aprobacion de scoring.
- Cada propuesta pasa de "idea" a "aprobada" por separado. No desplegar ni recalcular
  solamente por haber creado este documento.

## Referencias del codigo revisado

- `frontend/src/pages/RankingPage.tsx`: estados de lista/podio y clave de animacion.
- `frontend/src/pages/TeamsPage.tsx`: pantalla pendiente.
- `frontend/src/pages/ComparePage.tsx`: jerarquia y definiciones de metricas actuales.
- `backend/src/sfa/domain/scoring/value_objects.py`: M1, M2, M3 y M4.
- `backend/src/sfa/domain/scoring/services.py`: timeline del marcador.
- `backend/src/sfa/infrastructure/models/fixtures/models.py`: datos del partido.
- `backend/src/sfa/infrastructure/models/fixture_team_strengths/models.py`: ELO temporal.
- `backend/src/sfa/infrastructure/models/player_stats/models.py`: minutos y remates.
- `backend/src/sfa/application/use_cases/calculate_elo_ratings.py`: snapshots prepartido.
- `backend/src/sfa/application/use_cases/calculate_team_strengths.py`: fuerza desde tablas.
- `backend/src/sfa/application/use_cases/calculate_scores_for_rules_version.py`: calculo versionado.
- `backend/src/sfa/application/use_cases/calculate_achievement_bonuses.py`: reparto colectivo.
- `backend/src/sfa/application/use_cases/infer_competition_achievements.py`: inferencia de logros.
- `backend/src/sfa/application/use_cases/enrich_with_understat.py`: enriquecimiento agregado.
