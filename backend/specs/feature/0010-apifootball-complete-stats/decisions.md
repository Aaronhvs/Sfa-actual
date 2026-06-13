# API-Football Complete Stats — Fuente única de datos

## Contexto de negocio

El modelo actual de `player_stats` tiene 8 columnas con 0% de cobertura porque venían
exclusivamente de FBref (caído desde enero 2026) o Understat (bloqueado por rate-limiting).
El pipeline de enriquecimiento con fuentes externas (FBref, Understat) añade complejidad
operacional sin fiabilidad garantizada.

API-Football ya es la fuente principal del producto y provee más campos de los que
actualmente capturamos en `fixtures/players`. Activando todos ellos conseguimos:

1. Stats de perfil de jugador ricos y actualizados (pases totales, precisión, tarjetas, etc.)
2. Scoring más completo con señales negativas reales (tarjetas, faltas cometidas)
3. Diferenciación de creativos (passes_completed) sin depender de scraping externo
4. Pipeline simplificado: una sola fuente, sin scrapers, sin bloqueos de IP

## Restricciones

- API-Football plan real: 7.500 requests/día — el backfill de fixtures existentes debe
  respetar esta cuota (priorizar la temporada actual 2024)
- `fixtures/players` no incluye `clearances` ni stats por cuartos — lo que no está en la
  respuesta no se puede capturar
- Columnas a eliminar tienen datos históricos en 0 — al dropearlas no se pierde información real
- La migración Alembic debe ser reversible (downgrade limpio)
- Re-ingesta de fixtures pasados consume cuota: ~1 request por fixture → estimar fixtures
  totales antes de lanzar el backfill

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Fuente única API-Football | Mantener scrapers FBref/Understat como complemento | FBref caído desde ene 2026, Understat bloquea por IP; coste operacional sin retorno |
| Eliminar columnas muertas del modelo | Dejarlas con 0 | Reducir deuda técnica; columnas con 0% cobertura confunden el scoring y los tests |
| Calcular `passes_completed` en tiempo de scoring (`passes_total × accuracy / 100`) | Almacenar campo derivado en DB | Evitar duplicar datos; `passes_total` y `passes_accuracy` son los datos fuente |
| Endpoint `/players/{id}/stats` agrega desde `player_stats` en DB | Llamar a API-Football season stats | Sin coste de cuota; los datos ya están en DB desde la ingesta por partido |
| Backfill como task admin bajo demanda | Backfill automático al desplegar | Control explícito sobre consumo de cuota |
| Pesos negativos para tarjetas y faltas cometidas | Ignorar señales negativas | Las tarjetas ya penalizan al equipo; reflejarlas en scoring mejora la precisión |
| `DRIBBLES_PAST` negativo solo para DF | Negativo para todas las posiciones | Un delantero regateado en campo rival no es un error grave; un defensa sí |

## Integraciones externas

**API-Football v3** — única fuente de datos de partido.

Endpoint relevante: `GET /fixtures/players?fixture={id}`

Campos que se añaden en esta feature (todos de `statistics[0]`):

| Sección API | Campo | DB column | Tipo |
|---|---|---|---|
| `shots` | `total` | `shots_total` | SmallInteger |
| `passes` | `total` | `passes_total` | SmallInteger |
| `passes` | `accuracy` | `passes_accuracy` | SmallInteger (0-100) |
| `dribbles` | `past` | `dribbles_past` | SmallInteger |
| `duels` | `total` | `duels_total` | SmallInteger |
| `fouls` | `committed` | `fouls_committed` | SmallInteger |
| `cards` | `yellow` | `cards_yellow` | SmallInteger |
| `cards` | `red` | `cards_red` | SmallInteger |
| `penalty` | `won` | `penalty_won` | SmallInteger |
| `goals` | `saves` | `saves` | SmallInteger (porteros) |
| `goals` | `conceded` | `goals_conceded` | SmallInteger (porteros) |

Campos eliminados del modelo (siempre 0, sin fuente activa):
`xg`, `xa`, `progressive_passes`, `progressive_carries`,
`recoveries_opp_half`, `pressures_success`, `clearances`, `clearances_goal_line`

Rate limit: 7.500 req/día. El backfill de fixtures existentes se lanza manualmente
desde el endpoint admin y procesa en batches respetando la cuota.
