# Detalle de partido en vivo consistente y rediseño para Torneos

## Contexto de negocio

La portada de Torneos puede mostrar un partido en vivo con su marcador actual mientras la página
de detalle lo presenta como finalizado y con otro resultado. Además, el detalle de clubes hereda
íntegramente la composición, los tipos y las clases visuales creadas para el Mundial, por lo que no
se integra con la interfaz compacta y operacional del centro de Torneos.

SFA necesita que la lista y el detalle expresen un único estado del partido y que la ficha de clubes
tenga identidad propia. La nueva ficha debe priorizar lectura rápida del marcador y estado, y ordenar
impacto SFA, estadísticas, cronología y alineaciones con una densidad comparable a la portada de
Torneos y a una aplicación de resultados, sin copiar la marca ni los patrones visuales de FotMob.

## Diagnóstico del codebase

- `TournamentRepository` construye la portada desde `fixtures` persistidos en PostgreSQL.
- `GetTournamentFixtureDetailUseCase` valida el fixture local, pero descarta ese resumen y devuelve
  el `FixtureSummaryDTO` obtenido nuevamente desde API-Football.
- `FixtureDetailRepository` cachea en Redis el resumen externo junto con alineaciones y estadísticas.
  Los TTL dependen del estado externo: 45 segundos en vivo, 120 segundos programado y 6 horas
  finalizado.
- El frontend añade una tercera caché general de 60 segundos y la pantalla de detalle no refresca
  mientras permanece abierta.
- `TournamentMatchPage` solo renderiza `MatchDetailPage` desde `MundialMatchPage`; los contratos de
  Torneos son aliases de los schemas y tipos `Wc*`, y toda la superficie usa clases `wmd-*`.
- La cronología y las alineaciones ya existen. Las estadísticas agregadas vienen de API-Football.
  SFA no recibe un indicador de presión o peligro equivalente al momentum propietario de FotMob.
- SFA sí conserva eventos puntuados por fixture, minuto, equipo y versión de reglas, por lo que puede
  ofrecer una proyección honesta de impacto SFA por tramo sin presentarla como presión ofensiva.

## Restricciones

- Toda operación backend mantiene Router -> Use Case -> Protocol -> Repository.
- El frontend nunca consulta API-Football directamente.
- La portada y la cabecera del detalle deben usar el mismo snapshot persistido para identidad,
  estado y marcador.
- La lectura de detalle no escribe en PostgreSQL ni convierte el endpoint GET en una ingesta.
- API-Football sigue siendo la fuente suplementaria de estadio, árbitro, alineaciones y estadísticas.
- La cronología continúa leyendo primero `fixture_events`; no se duplica persistencia.
- No se inventa momentum de ataque, posesión o peligro. La gráfica se denomina `Impacto SFA por
  tramo` y solo usa eventos SFA ya calculados.
- El impacto por tramo excluye eventos `stats`, porque son agregados de partido sin minuto real.
- Si aún no existen scores del fixture, la sección de impacto muestra un estado pendiente y no ceros
  ficticios.
- El Mundial conserva su ruta, contrato y presentación actuales.
- No se agregan dependencias frontend, tablas ni migraciones.
- React 18, TypeScript estricto, React Router y CSS puro con tokens existentes siguen siendo el stack.
- El oro se reserva para puntos y ranking SFA. Estado en vivo usa un color semántico moderado; no se
  agrega un espectro decorativo ni gradientes heredados del Mundial.
- Radio máximo de 6 px, foco visible, contraste AA, soporte responsive y `prefers-reduced-motion`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| El resumen local validado es canónico para equipos, fecha, fase, jornada, estado y marcador del detalle de Torneos | Mostrar directamente el resumen cacheado de API-Football | Garantiza que la portada y el detalle no se contradigan y conserva el límite de lectura local definido para Torneos |
| API-Football aporta únicamente los datos suplementarios del detalle | Mantener dos snapshots completos y decidir en React | Evita reglas de reconciliación duplicadas y mantiene al frontend ajeno a la procedencia de datos |
| El use case compone un único `FixtureDetailDTO` reconciliado | Reconciliar en el router | La política pertenece a application y puede probarse con fakes sin HTTP ni infraestructura |
| Cuando los estados local y externo difieren, no se mezclan minuto, ganador o etiqueta externa con el marcador local | Conservar esos campos del proveedor aunque el estado difiera | Impide formar una cabecera internamente imposible, por ejemplo marcador local en vivo con etiqueta externa finalizada |
| La etiqueta de estado se deriva del código canónico; el minuto externo solo se usa cuando ambos snapshots coinciden y el estado es live | Persistir ahora nuevos campos de estado largo y minuto | Resuelve la inconsistencia sin migración; la persistencia de reloj live queda fuera de este alcance |
| Versionar la clave Redis del suplemento y mantener TTL por estado sin convertirlo en fuente de cabecera | Reutilizar la caché que contiene snapshots completos antiguos | Evita que una entrada final de seis horas siga contaminando el nuevo contrato después del despliegue |
| El detalle live se refresca periódicamente en frontend con bypass de la caché cliente y se detiene al llegar a estado final | Cargar una sola vez o usar WebSockets | Un polling acotado encaja con el stack y la cadencia actual sin introducir infraestructura en tiempo real |
| Crear una página y componentes propios bajo `components/tournaments/match/` | Seguir parametrizando `MundialMatchPage` | El problema visual es estructural; separar las presentaciones evita condicionales crecientes y futuras regresiones cruzadas |
| Mantener `domain/fixture_detail_ports.py` como contrato genérico y definir schemas/tipos de Torneos reales | Seguir exportando aliases `Wc*` | Conserva reutilización backend sin filtrar el lenguaje del Mundial al contexto de clubes |
| Añadir al response una serie aditiva `sfa_momentum` en tramos de cinco minutos por equipo | Imitar la gráfica de presión de FotMob con eventos básicos | La proyección es auditable, propia de SFA y no promete una métrica que la fuente no entrega |
| Resumen de escritorio con columna principal y rail contextual, y flujo de una columna en móvil | Cuadrícula de tarjetas iguales o paneles anidados | Favorece escaneo operacional, cronología larga y alineaciones sin convertir cada bloque en una tarjeta flotante |
| Navegación de secciones con Resumen, Estadísticas, Cronología, Alineaciones y Rendimiento SFA | Conservar tres tabs donde cronología vive dentro de Alineaciones | Hace predecible la ubicación de cada dato y permite enlaces/teclado sin ocultar conceptos no relacionados |
| Reutilizar datos y utilidades, no la composición visual del Mundial | Reescribir también la página del Mundial | Mantiene el alcance y reduce riesgo sobre una experiencia histórica estable |

## Contrato de lectura

`GET /api/v1/tournaments/fixtures/{fixture_external_id}?season=2026` conserva su ruta y campos
actuales, y aplica cambios aditivos:

- `fixture` representa siempre el mismo snapshot local que alimenta el centro de Torneos;
- `status_label`, `is_live` y el marcador se calculan a partir de ese snapshot canónico;
- `elapsed` es nullable y solo se conserva si el proveedor confirma el mismo estado live;
- `venue`, `referee`, `lineups` y `statistics` son datos suplementarios de API-Football;
- `events` mantiene la cronología persistida y ordenada;
- `sfa_momentum` contiene tramos de cinco minutos con puntos del local y visitante, o una lista
  vacía si el fixture todavía no fue calculado con la versión activa.

La respuesta no expone procedencia interna ni obliga al frontend a reconciliar fuentes.

## Proyección de impacto SFA

La proyección agrupa `player_event_scores.final_points` por fixture, equipo y bandas de cinco
minutos a través del minuto de `player_events`. Solo considera la versión de reglas activa y omite
la acción agregada `stats`. Los tramos se ordenan desde 0 hasta el último minuto disponible y
mantienen valores separados para local y visitante.

Esta serie se presenta como `Impacto SFA por tramo`, no como dominio nuevo ni como una medición de
posesión, probabilidad de gol o peligro. No modifica scores, multiplicadores ni resultados
persistidos.

## Dirección visual

- Cabecera compacta alineada con `TournamentFixtureRow`: competencia y fase arriba; dos filas de
  equipos con escudos; marcador tabular a la derecha; estado live/final y minuto con jerarquía clara.
- Superficies `var(--bg)`, `var(--surface)` y `var(--surface2)`; texto principal blanco y metadatos
  con contraste suficiente. Se eliminan el fondo radial, el espectro multicolor y el hero centrado
  del Mundial.
- El score deportivo permanece blanco. El oro aparece únicamente en puntos/posición SFA.
- Estado live usa una señal verde sobria y semántica; tarjetas y goles conservan sus colores de
  evento. Los colores de equipo se limitan a la serie de impacto y marcadores de identidad.
- Resumen: impacto SFA y cronología como contenido principal; rail lateral con datos del encuentro y
  líderes SFA disponibles.
- Estadísticas: filas comparativas continuas, números grandes y blancos, barras finas y desaturadas,
  sin tarjetas individuales.
- Cronología: eje central compacto, legible y navegable, con eventos local/visitante y minutos
  tabulares.
- Alineaciones: cancha y listas existentes reinterpretadas con la densidad de Torneos, sin fondos
  temáticos del Mundial y con fallback explícito cuando API-Football no publica datos.
- Mobile: una columna, cabecera sin truncar nombres, navegación horizontal desplazable y ninguna
  cancha que fuerce overflow de la página.

## Límites arquitectónicos

- `domain/fixture_detail_ports.py`: DTOs genéricos de detalle y nueva proyección de impacto.
- `application/use_cases/get_tournament_fixture_detail.py`: alcance de temporada y composición del
  snapshot canónico con suplemento externo.
- `infrastructure/repositories/tournament_repository.py`: lectura local canónica, sin escrituras.
- `infrastructure/repositories/fixture_detail_repository.py`: suplemento cacheado, cronología e
  impacto SFA de solo lectura.
- `api/v1/tournaments.py` y `api/v1/schemas/tournaments.py`: contrato HTTP propio de Torneos.
- Frontend: `TournamentMatchPage` y componentes de `components/tournaments/match/`; el contexto
  `MundialMatchPage` deja de ser dependencia de la ruta de clubes.

## Integraciones externas

API-Football mantiene tres consultas en un cache miss de suplemento:

- `fixtures?id={fixture_id}` para estadio, árbitro y validación contextual del suplemento;
- `fixtures/lineups?fixture={fixture_id}` para formaciones, titulares y suplentes;
- `fixtures/statistics?fixture={fixture_id}` para estadísticas agregadas.

La cronología se sirve desde PostgreSQL cuando está persistida. Los fallos o secciones todavía no
publicadas producen datos suplementarios vacíos y estados de interfaz específicos; nunca cambian el
estado canónico del partido.

## Domain Model

No se requiere `@DDD-Designer`. El cambio agrega DTOs de lectura inmutables y una proyección
derivada, sin nuevas entidades, aggregates, value objects, invariantes ni reglas del motor de
scoring.
