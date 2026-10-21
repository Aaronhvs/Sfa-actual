# 0067 — Buscar nombres completos conservando el nombre mostrado

Fecha: 2026-10-21. Architecture-Engineer; skill `backend/.claude/skills/sfa-spec/SKILL.md` aplicada. El catálogo de raíz ya reserva 0066 para ranking aunque ese spec no esté en este worktree; se continúa con 0067. Base leída: worktree `C:/Users/formu/sfa-positions-apply`, HEAD 90d659a.

## Contexto de negocio

El ranking solo busca `Player.name`, que puede ser abreviado por el proveedor. «X. Espart» no contiene «Xavi» aunque esa identidad tenga nombre completo en otro payload. Solucionar búsqueda por los nombres reales conservados del proveedor para todos los jugadores, sin cambiar display, inventar expansiones de iniciales ni añadir UI. Es independiente de la corrección posicional de Espart, que continúa en 0065.

## Restricciones y datos actuales

Player guarda `name`, no firstname/lastname/aliases. APIFootballProvider obtiene `/players` para fechas de nacimiento, pero `_parse_player_birth_date` solo devuelve external_id y birth_date. No asumir que PlayerStats o el nombre abreviado permiten reconstruir nombres completos. Revisar payloads conservados y los campos realmente presentes antes de hacer GET adicional; no afirmar disponibilidad de campos que no existen en la respuesta. No consultar upstream durante GET /ranking.

Identidad por player.id + external_id verificado, nunca join por nombre/homónimo. Un alias no es globalmente único: dos personas pueden compartirlo. Los textos entrantes son datos de identidad, no instrucciones. La entrega no cambia posiciones, scores, reglas, display ni el mínimo/positividad de 0066. Deuda de cobertura global se informa separada; gate del incremento mantiene suite completa, ≥80 % de módulos nuevos/líneas cambiadas e integración SQL real.

## Decisiones tomadas

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| Aliases persistidos por ID y procedencia | Hardcode Xavi/Espart u otros nombres | Solución general y trazable sin inferir iniciales. |
| Mantener Player.name como display | Sustituirlo por nombre largo | Evita alterar nombres aprobados y presentación del ranking. |
| EXISTS correlacionado por player_id | JOIN de aliases en agregado de scores | Varios aliases no multiplican puntos, filas, count ni páginas. |
| Usar payloads conservados y luego enriquecimiento acotado del proveedor existente | Llamar API al buscar o escanear todos los fixtures por petición | Búsqueda estable, rápida y sin consumo de cuota por visitas. |

### Persistencia mínima

#### Delta: alias público revisado cuando el perfil no aporta nombre completo

Comprobación real aportada: perfil API 568001 devuelve `name=X. Espart`, firstname y lastname null. Esos campos permanecen null; no inventar nombre completo civil ni atribuir al API datos que no entregó. La [ficha oficial del FC Barcelona](https://www.fcbarcelona.es/es/futbol/primer-equipo/jugadores/141001/xavi-espart), consultada durante esta revisión, publica el nombre deportivo Xavi Espart. Puede registrarse **como alias público revisado**, con fuente `official-club-reviewed`, URL, responsable/fecha de revisión y referencia a la afirmación del usuario como contexto adicional. La afirmación del usuario no se presenta como dato del proveedor ni reemplaza la comprobación de identidad.

El importador/DTO acepta esta clase genérica de alias revisado para cualquier identidad, además de nombres explícitos del proveedor: entrada operativa con player_id/external_player_id comprobados, alias, source_kind/source_ref y actor/reviewed_at. No hay diccionario en código ni condicional por Espart. La identidad externa 568001 sigue siendo de API-Football; `official-club-reviewed` describe autoridad del alias y **no** convierte 568001 en ID del club (la página tiene su propio ID). Registrar identity_provider por separado o dejar explícito ese contrato del campo para evitar confundir namespaces. La vinculación revisada se apoya en identidad/club/contexto coherentes, no en un join automático por nombre ni únicamente en dorsal, que cambia con el tiempo. Nombres públicos compartidos siguen permitidos entre jugadores distintos.

Un alias revisado aceptado persiste por la misma ruta idempotente y predicado EXISTS; respuestas posteriores con iniciales o null no lo borran. Corregir/revocar un alias erróneo requiere operación revisada trazable por fila/procedencia, no reescribir Player.name ni datos deportivos. La base general de perfiles/aliases y su backfill continúa cuando haya nombres reales disponibles; resolver este caso mediante un dato oficial revisado no equivale a declarar que los perfiles de todo el catálogo están completos.

Añadir tabla `player_name_aliases` en siguiente migración libre (0057 si sigue disponible): ID, player_id FK, provider, external_player_id, alias original, normalized_alias, source_ref y captured_at. UNIQUE por player_id/provider/normalized_alias e índice por player_id; alias puede repetirse entre jugadores. Normalización única y versionada: espacios colapsados, trim y comparación case/accent-insensitive compatible con `unaccent` ya usado por ranking. Conservar texto original, sin destruir signos/apellidos compuestos. Guardar solo textos no vacíos; limitar longitud razonable y rechazar identidad incompatible. Normalización de presentación no decide matching de identidad.

Aliases válidos: nombre completo explícito del proveedor; concatenación de firstname + lastname cuando ambos campos existan; variantes de `name` realmente observadas para esa misma identidad. Un firstname aislado puede encontrarse como substring del nombre completo: no crear tokens/filas de todos los nombres ni generar sobrenombres que el proveedor no dio. No producir «Xavi» desde «X.» ni convertir cualquier jugador cuyo apellido sea Espart en la misma identidad. Si faltan nombres completos, registrar estado de enriquecimiento pendiente; no presentar un alias inventado como dato recuperado.

Upsert idempotente conserva aliases anteriores válidos cuando otra respuesta vuelve a traer solo abreviatura; ausencia no borra ni reemplaza completos. Registrar procedencia de la respuesta efectivamente usada y fecha real, sin copiar información personal no necesaria. La tabla es un read model/registro de textos de identidad, no un nuevo aggregate de fútbol.

### Flujo hexagonal y adquisición

Crear DTO frozen de nombres con external_id y strings opcionales, port de lectura/provisión de nombres y port de almacenamiento de aliases. Use case `EnrichPlayerNameAliasesUseCase` verifica crosswalk y registra aliases; repositories usan execute/flush sin commit, el adaptador CLI/tarea controla transacción. DI exclusivamente core/dependencies.py. No SQL desde application ni wiring en router.

Extraer nombres de payloads ya conservados que tengan identidad verificable. Para faltantes necesarios, reutilizar el endpoint `/players` ya consumido por birthdates mediante parser de identidad compartido o método provider específico, validando contrato/paginación real y campos con muestra de respuesta. No cambiar el DTO de nacimiento de manera incompatible ni permitir que ese enriquecimiento escriba birth_date/posición sin su propio flujo. Un comando genérico por IDs o selección missing_aliases/backfill sirve para Espart y cualquier jugador; puede empezar por jugadores actuales relevantes y procesar el resto por tandas reanudables. No requiere nuevo scheduler ni endpoint de búsqueda adicional.

GET adicionales: status/headers y presupuesto actual de cuenta 7.500/día, reserva 100, solicitudes secuenciales con pacing ≥1 s, sin ingestas paralelas propias; reutilizar la ventana operativa de 0065 con restauración de servicios. Respuesta de equipo puede cubrir varios IDs si el endpoint real la ofrece y valida paginación; deduplicar por ID. Errores/429/cuota desconocida detienen y conservan checkpoint; no recuperar perfiles masivamente ni repetir por cada búsqueda. Guardar salida de cobertura y datos efectivamente disponibles, sin contratar proveedor nuevo.

### Consulta de ranking

Normalizar la consulta en tokens de forma general: trim, espacios, acentos y mayúsculas equivalentes; puntos de iniciales y puntuación separadora se tratan como límites de palabra. Todos los tokens deben coincidir **en el mismo alias completo o el mismo nombre display**, sin exigir el orden de entrada. No satisfacer «Xavi Espart» con «Xavi García» de un alias y «Juan Espart» de otro, ni expandir «X.» a un nombre que no se conoce. Mantener coincidencia parcial de texto para que Xavi pueda encontrar un nombre conservado Xavier; esto es búsqueda parcial, no un alias inventado. Usar una única normalización de aplicación para alias normalizado y query; documentar equivalencia del fallback SQL sobre display y probar acentos/espacios/puntuación reales. No habilitar fuzzy matching, corrección ortográfica o diccionario de apodos.

Centralizar el predicado de nombre de jugador, parametrizado con columna player_id y nombre display del nivel SQL correspondiente: display contiene query **OR EXISTS alias de ese player_id contiene query**. Usar el mismo case/accent-insensitive actual y normalizar espacios de entrada; conservar búsqueda por equipo/aliases de equipo existentes. Las ramas que envuelven el select en subquery deben correlacionar al player_id de esa subquery, sin introducir Player sin JOIN/cartesian product.

Aplicar el predicado compartido en scope, season física y all-history y en las relaciones reutilizadas por count. La misma búsqueda normalizada activa `min_matches=0` de 0066, pero positivos/use_total/honors y demás filtros siguen vigentes. Resolver aliases antes de offset/limit; conservar orden/ranks y semántica actual de búsqueda, sin cambios de puntuación. Un jugador con tres aliases coincidentes aparece una vez; un alias compartido devuelve a ambos IDs si son elegibles. Sin query no añadir joins ni trabajo innecesario al ranking normal. No es necesario construir un índice trigram/expression sobre unaccent si EXPLAIN de escala real no lo justifica; no declarar IMMUTABLE a una función dependiente de configuración para permitir indexación.

La API conserva su contrato: retorna `name` abreviado igual que antes, sin campos/frontend extra. No ampliar por defecto búsqueda a todas las pantallas; este incremento cubre ranking y sus listas/count.

### Backfill inicial y continuidad sin consumo inesperado

Persistir también display/nickname realmente recibidos y nombres completos cuando futuras ingestas entreguen campos explícitos; el payload de fixture stats suele contener solo name, por lo que esa ruta no puede fabricar firstname/lastname. La base general debe operar desde el primer release, aunque cobertura de perfiles largos sea progresiva. Priorizar catálogo puntuable, cachés/perfiles ya conservados y consulta de equipo+temporada paginada cuando el contrato real la soporte; validar número de páginas y guardar checkpoint por página/IDs. No lanzar miles de llamadas individuales de perfil. La primera entrega puede cubrir Espart mediante su ID y una tanda genérica acotada, más un informe de faltantes y comando reanudable para el resto. No iniciar GET en esta implementación hasta que el coordinador confirme ventana de operación diaria de producción; es coordinación de cuota/ingestas ya autorizada, no solicitud de aprobación rutinaria nueva al usuario.

## Verificación y publicación

Regresiones genéricas con IDs arbitrarios: display «X. Espart» + alias proveedor «Xavi/Xavier … Espart …» permite query «Xavi», conservando display; alias acentuado/mayúsculas/espacios; duplicados de alias y homónimos; ausencia sin expansión falsa; reingesta abreviada no borra completo. Tests scope/season/all-history, count/lista/páginas/posición, min0 y puntos negativos, use_total/honors y equipo. Integración PostgreSQL con varios aliases no cambia sumas ni multiplica resultados; consulta parametrizada y plan de ejecución aceptable.

Migración expand primero, código compatible y backfill después; backup/restauración y manifest de release sobre fuente actual que ya tiene 0065/0066/0055/0056. Añadir tabla al protocolo shared y protección de TRUNCATE conforme al mecanismo vigente si se requiere consistencia del fingerprint/publicación; el enriquecimiento no debe saltarse la exclusión de escritores. No cambiar hashes de artefactos/batches históricos para añadir aliases. Comprobar smoke real «Xavi» y abreviatura, mismos puntos/display, y todos los cambios posicionales/0066 intactos. Si no hay dato completo durable aún, completar el backfill de esa identidad antes de declarar resuelto el ejemplo del usuario. Rollback de código conserva aliases como datos aditivos; no borrar datos ni tocar scores para revertir búsqueda.

## Agent Routing

Sin nuevas entidades/VO complejos/aggregates ni reglas futbolísticas; solo DTO y read model de textos. No requiere nueva delegación DDD. La corrección táctica/temporal permanece bajo invariantes existentes de 0065.
