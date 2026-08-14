# Centro de torneos y detalle de competicion

## Contexto de negocio

La portada de Torneos debe funcionar como centro de seguimiento de la temporada y no como el
detalle de una unica competicion. El usuario necesita descubrir rapidamente que partidos se juegan
hoy o en la fecha disponible mas cercana, reconocer la jerarquia de las competiciones y entrar a
una vista dedicada de cada liga o copa.

## Restricciones

- Toda lectura nueva mantiene Router -> Use Case -> Port -> Repository.
- La portada consume datos persistidos en SFA y no consulta API-Football en tiempo de lectura.
- La portada no descarga el calendario completo de cada competicion.
- Sin fecha explicita se selecciona hoy si existen partidos; en caso contrario, la proxima fecha
  futura y, como ultimo recurso, la fecha pasada mas reciente.
- Con fecha explicita se respeta el dia solicitado aunque no tenga partidos.
- Las fechas disponibles se calculan sobre `fixtures.played_at` en UTC. El frontend sigue mostrando
  fecha y hora en la zona local del visitante.
- La jerarquia visual de competiciones es una regla de presentacion y no altera factores del motor.
- El top 3 lateral reutiliza `GET /ranking`; no se modela un premio de jornada nuevo.
- Los filtros del detalle operan sobre el calendario ya cargado de una sola competicion.
- No se agregan tablas ni migraciones.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Agregar `GET /tournaments/dashboard` | Consultar el detalle de todas las ligas desde React | Evita N+1 requests y transferir miles de fixtures para construir una sola fecha. |
| Devolver grupos por competicion | Devolver una lista plana | El layout central necesita encabezados, orden y navegacion por torneo. |
| Resolver la fecha mas cercana en el use case | Resolverla en React | La regla queda consistente para todos los clientes. |
| Mantener prioridad de torneos en frontend | Guardar prioridad en PostgreSQL | Es jerarquia editorial, no un atributo canonico del torneo. |
| Crear ruta `/torneos/:competitionId` | Mantener detalle dentro de la portada | Permite una portada escaneable y una ficha profunda con URL compartible. |
| Derivar columnas deportivas desde fixtures finalizados | Ampliar `standing_snapshots` ahora | Permite J/G/E/P/GF/GC/DG sin migracion y conserva puntos/posicion oficiales del snapshot. |
| Mostrar top 3 de temporada | Calcular destacado diario | El ranking existente es auditable; el destacado diario requeriria un agregado nuevo. |

## Contratos de lectura

`GET /tournaments/dashboard?season=2026&date=2026-08-15` devuelve:

- temporada resuelta;
- fecha seleccionada;
- fechas anterior y siguiente con partidos;
- grupos de competicion con sus fixtures de la fecha.

Si `date` no se envia, el use case aplica la regla de fecha mas cercana. Si no existen fixtures para
la temporada, devuelve grupos vacios y fechas nulas sin convertir la pagina completa en error.

`GET /tournaments/{competition_id}?season=2026` conserva su contrato actual. El frontend deriva
las estadisticas de tabla auxiliares a partir de fixtures `FT`, `AET` y `PEN`, mientras posicion y
puntos siguen viniendo del ultimo snapshot disponible.

## Domain Model

No se requiere DDD Designer. Se agregan DTOs de lectura inmutables para el dashboard y se amplia el
port de torneos. No aparecen entidades, aggregates ni reglas nuevas del motor de scoring.

## Integraciones externas

Ninguna nueva. Los escudos usan el proveedor de medios ya adoptado por el frontend y los jugadores
del panel lateral provienen del endpoint de ranking de SFA.
