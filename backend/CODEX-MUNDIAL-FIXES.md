# Mundial 2026 - Fixes beta

## Pendientes

- [ ] **Scoring DEL/EXT sin xG/xA real**: para Mundial solamente, evaluar subir `passes_completed` en la config activa/beta. Contexto: la DB no tiene `expected_goals` ni `expected_assists`; `XG_NO_GOAL` se deriva de `shots_on - goals` y `XA_NO_ASSIST` de `passes_key - assists`. Como DEL/EXT tienen `passes_completed=1`, quedan con poco piso cuando no convierten o asisten. Propuesta inicial: `DEL 1 -> 2`, `EXT 1 -> 3`, mantener `MCO=2` y `MF=7`. Validar impacto con recalc local antes de produccion.

- [ ] **Detalle de partido por jugador mas explicativo**: cambio aplicable a todas las competiciones. En las tarjetas/filas de partidos del jugador, mostrar mejor como los multiplicadores afectan el puntaje: rival superior/inferior, valor M1, contexto de campo local/visitante/neutral, minuto/estado del partido si aplica, y una lectura humana tipo "rival superior", "rival menor", "alta presion", etc. La idea es que el usuario entienda por que una accion vale mas o menos, no solo ver el total.

- [ ] **Mas estadisticas visibles por partido**: cambio aplicable a todas las competiciones si los datos existen. Mostrar conteos de stats de partido del jugador: pases completados, pases totales/precision si esta disponible, tiros al arco, tiros totales, pases clave, regates, duelos, tackles/intercepciones, bloqueos, faltas recibidas/cometidas, tarjetas, etc. Evitar inventar xG/xA real; si se muestra "pre-asist." o xA proxy, aclarar que sale de pases clave sin asistencia.

- [ ] **Click desde partido del jugador hacia detalle Mundial**: solo Mundial. Cuando una fila/tarjeta de partido del jugador sea de World Cup, al hacer click debe navegar a la pagina del resultado del partido (`/mundial/partido/{fixture_external_id}` o ruta equivalente) para ver marcador, cronologia/eventos, formaciones y stats completas.

- [ ] **Banderas faltantes en movil Mundial**: revisar mapping/render responsive de banderas para selecciones que no se ven en mobile: Costa de Marfil / Ivory Coast, Curazao / Curaçao, Nueva Zelanda / New Zealand, Sudafrica / South Africa, Bosnia / Bosnia & Herzegovina. Probable causa: alias de nombre del equipo no coincide con codigo ISO/flag usado por frontend. Validar en fixtures, ranking y detalle de partido.

- [ ] **Ranking Mundial: busqueda por seleccion/pais**: en el filtro/buscador del ranking Mundial, permitir que al escribir una seleccion como "Argentina" aparezcan jugadores de esa seleccion, no solo jugadores cuyo nombre coincide. Aunque exista limite de 100 resultados, el backend/frontend debe buscar por equipo/pais y devolver al menos los jugadores coincidentes dentro del limite. Revisar si aplica tambien al ranking general o solo Mundial.

- [ ] **Mundial: seccion Paises/Selecciones despues de grupos**: en la pagina principal del Mundial, despues del bloque de grupos, agregar una lista/seccion "Paises" o "Selecciones". Debe ordenar dinamicamente las selecciones por total de puntos SFA acumulados por sus jugadores en el Mundial. Al hacer click en una seleccion debe navegar al perfil del equipo.

- [ ] **Perfil de seleccion Mundial: totalizar goles**: en el perfil del equipo/seleccion, mostrar la suma total de goles acumulados por sus jugadores/equipo en el Mundial. Validar fuente: puede salir de fixtures/resultados del equipo o agregacion de player stats/events, pero debe ser consistente con el marcador oficial.

- [ ] **Alineaciones Mundial espejadas/invertidas**: auditar render de alineaciones en detalle de partido. Ejemplo reportado: Colombia vs Uzbekistan, la alineacion de Colombia parece correcta en nombres/formacion pero espejada; Luis Diaz aparece por izquierda/derecha opuesta. Revisar si el problema viene de coordenadas API-Football, orientacion home/away, o transform CSS del campo. No corregir a mano sin entender si aplica solo a un equipo/lado o a todas las alineaciones.

- [ ] **Corrector/enriquecimiento de posiciones en Mundial**: verificar si esta corriendo el corrector de posiciones y si respeta contexto de seleccion. Ejemplos reportados: Messi aparece como MC pero deberia ser EXT/DEL en Argentina; Kimmich es MC por club pero con Alemania juega de lateral. Evaluar overrides manuales por competicion/seleccion para Mundial, sin romper posicion historica de clubes.

- [ ] **Local: temporadas de clubes no visibles**: auditar por que en local no se ven las temporadas de clubes. Verificar si es dato faltante, filtro frontend, cache, API local, seed/migracion o mismatch de season/rules_version. No asumir que es bug de Mundial.

- [ ] **Clubes: aplicar banderita como Mundial**: agregar flag/banderita en superficies de clubes con el mismo estilo visual usado en Mundial, probablemente por pais del equipo/liga/jugador segun contexto. Definir regla exacta antes de implementar para evitar flags incorrectas en clubes multinacionales.

- [ ] **Metodologia: documentar B1**: agregar el bonus B1 por edad excepcional en la pagina de metodologia. Debe explicar rango joven 17-20, veteranos 35+, que solo aplica a goles/asistencias, tabla +200/+400/+600, y aclarar si esta activo solo para Mundial beta.

- [ ] **Ranking Mundial: filtro por posicion**: agregar filtro por posicion en Mundial igual que en ligas normales para ver mejores por posicion (`DEL`, `EXT`, `MCO`, `MC`, `LAT`, `DC`, etc.). Debe funcionar con ranking Mundial y mantener combinacion con busqueda/temporada si aplica.
