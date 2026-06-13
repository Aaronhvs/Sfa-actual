# Stats M2 Damping — Reduce stage_factor inflation on STATS events

## Contexto de negocio

El sistema SFA calcula puntos por partido en dos caminos:

1. **Eventos de acción** (`score_event`) — goles, asistencias, tarjetas. Usan M2 completo.
2. **Evento STATS** (`_score_stats_event`) — tackles, duelos, pases, intercepciones, etc. También usan M2 completo.

El problema: M2 (`stage_factor` de la fase de competición) se aplica con el mismo peso en STATS que en goles y asistencias. Esto genera inflación extrema en partidos de alta fase: en una semifinal de Europa League (`stage_factor=2.0`), un jugador sin goles ni asistencias puede acumular 3400+ pts solo por stats defensivos.

**Caso real observado:** Elliot Anderson, Forest vs Aston Villa, EL semi → 3411 pts de STATS puro con M2=2.0.

La jerarquía de competiciones debe preservarse, pero la amplificación debe ser menor para acciones de soporte (tackles, duelos, pases) que para acciones de impacto directo (goles, asistencias). El balance actual penaliza a jugadores que sí marcan en estas fases respecto a jugadores puramente defensivos con muchas acciones acumulativas.

## Restricciones

- Los goles y asistencias (`_score_individual_event`) NO deben cambiar — siguen usando M2 completo.
- La solución debe ser reproducible por `rules_version` — el parámetro debe persistir en `config_json` JSONB.
- No puede requerir migración de esquema de DB — `config_json` ya es JSONB extensible.
- Backward-compat obligatoria: configs v1 almacenadas en DB sin la nueva clave deben seguir funcionando con `stats_m2_attenuation=1.0` (sin cambio).
- El recálculo afecta solo `player_event_scores` (tipo `stats`) y `sfa_season_scores` — nunca `player_events`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Añadir `stats_m2_attenuation: float` a `ScoringConfig` | Pasar el factor como parámetro a `score_match_stats()` | `ScoringConfig` es el contenedor canónico de parámetros por version; pasar por método rompe la interfaz sin ganancia y no persiste en DB |
| Nombre `stats_m2_attenuation` | `stats_stage_factor_weight`, `m2_stats_factor` | "Attenuation" describe la semántica exacta: reducir el impacto de M2. Es coherente con la nomenclatura del sistema |
| Default `1.0` en v1, `0.5` en v2 | Default `0.5` en ambas | v1 backward-compat obligatoria; v2 es donde se introduce el balance |
| Aplicar fórmula en `_score_stats_event()` del use case | Aplicar en `SFAScoringService.score_match_stats()` | El use case ya maneja la lógica extendida (DR, bifurcación M1, MC bonuses); es el lugar correcto para este cálculo contextual |
| M2 atenuado también para midfield bonuses | M2 completo para MC bonuses | Los MC bonuses son estadísticos (pases, rating, tackles) — no son acciones directas; deben recibir el mismo tratamiento que el resto de stats |
| Actualizar la rules_version activa en DB (no crear nueva) | Crear nueva rules_version v3 | El cambio es una corrección de balance en v2, no un cambio de modelo; crear nueva version requeriría borrar todos los scores previos y hacer ingestion completa |

## Domain Model

No aplica — no se crean entidades de dominio nuevas. Solo se extiende `ScoringConfig` con un campo de configuración y se ajusta la lógica de cálculo en el use case.

## Fórmula

```
effective_stage_factor = 1.0 + (stage_factor - 1.0) × stats_m2_attenuation
m2_stats = M2CompetitionStage(effective_stage_factor)
```

| `stage_factor` | `stats_m2_attenuation` | `effective_stage_factor` | Cambio vs antes |
|---|---|---|---|
| 1.0 (liga regular) | 0.5 | 1.0 | Sin cambio |
| 1.4 (cuartos CL) | 0.5 | 1.2 | −14% |
| 1.7 (semis CL) | 0.5 | 1.35 | −20.6% |
| 2.0 (semis EL) | 0.5 | 1.5 | −25% |

Para `stats_m2_attenuation=1.0`: `effective_stage_factor == stage_factor` siempre (backward-compat total).

## Integraciones externas

Ninguna. Cambio puramente interno al dominio de scoring y al use case de recálculo.
