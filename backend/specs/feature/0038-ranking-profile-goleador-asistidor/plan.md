# Plan: Filtro de Perfil Goleador/Asistidor en el Ranking

## Archivos a crear

Ninguno. Toda la feature se implementa modificando archivos existentes.

## Archivos a modificar

- [ ] `src/sfa/infrastructure/repositories/sfa_score_repository.py` — nueva función
  `_stat_profile_filter`, nueva subquery `stat_agg` (usada por los métodos `*_total*`), y
  dispatch de filtro en los 4 métodos de ranking.
- [ ] `src/sfa/api/v1/ranking.py` — actualizar `description` del Query param `bonus_label`.
- [ ] `frontend/src/components/ranking/FilterBar.tsx` — agregar 2 `<option>` nuevas al
  `<select>` de Perfil (fuera del alcance de arquitectura backend, pero requerido para que el
  filtro sea usable end-to-end).

## Checklist de implementación

- [ ] Agregar función pura `_stat_profile_filter(profile_label: str | None, goals_col, assists_col)`
  junto a `_bonus_label_filter` (cerca de la línea 41 de `sfa_score_repository.py`). Retorna
  `goals_col >= 1` si `profile_label == "Goleador"`, `assists_col >= 1` si
  `profile_label == "Asistidor"`, `None` en cualquier otro caso.
- [ ] En `get_ranking`: reemplazar la llamada única a `_bonus_label_filter` por un dispatch que
  elija entre `_bonus_label_filter(...)` (Promesa/Veterano) y
  `_stat_profile_filter(bonus_label, agg.c.sum_goals, agg.c.sum_assists)` (Goleador/Asistidor),
  aplicando el resultado no-`None` sobre `stmt` igual que hoy.
- [ ] En `get_ranking_all_seasons`: aplicar el mismo dispatch que en `get_ranking`, usando
  también `agg.c.sum_goals`/`agg.c.sum_assists` del subquery `agg` ya existente en ese método.
- [ ] En `get_ranking_total`: cuando `bonus_label in {"Goleador", "Asistidor"}`, construir una
  subquery `stat_agg` que agregue `sum(_jint("goal") + _jint("goal_penalty"))` y
  `sum(_jint("assist") + _jint("corner_assist"))` por `player_id` respetando `score_filters`
  (mismo criterio de scope que usa `agg` en `get_ranking`). Unir `inner` con `stat_agg` vía
  `outerjoin` y aplicar `_stat_profile_filter` con `.where()` — mismo patrón que ya existe para
  `b1_agg`/`bonus_filter` en este método.
- [ ] En `get_ranking_total`, dentro del branch `if position is not None:` (query `exact_stmt`,
  líneas ~592-632): aplicar el mismo `outerjoin` + `.where()` de `stat_agg` que ya se hace hoy
  con `b1_agg`/`bonus_filter`, para que el conteo exacto por posición también respete el filtro
  Goleador/Asistidor.
- [ ] Repetir los dos pasos anteriores en `get_ranking_total_all_seasons` (incluyendo su branch
  `position is not None` en `exact_stmt`, líneas ~1035-1075).
- [ ] Actualizar el `description` del Query param `bonus_label` en
  `src/sfa/api/v1/ranking.py` (línea ~25) para reflejar los 4 valores válidos: "Filtro de
  perfil: Promesa, Veterano, Goleador o Asistidor".
- [ ] Agregar casos nuevos en `http/ranking.http` (o el archivo `.http` correspondiente a
  ranking) para `bonus_label=Goleador` y `bonus_label=Asistidor`, incluyendo variantes con
  `position`/`competition_id` combinados.
- [ ] Agregar 2 `<option>` nuevas ("Goleador"/"Asistidor") al `<select>` de Perfil en
  `frontend/src/components/ranking/FilterBar.tsx` (líneas ~52-60), mismo patrón que las
  opciones existentes de Promesa/Veterano.
- [ ] Escribir/actualizar tests en `tests/use_cases/test_get_ranking.py` (o el archivo
  equivalente) cubriendo: filtro `bonus_label=Goleador` devuelve solo jugadores con
  `goals >= 1` en el scope, `bonus_label=Asistidor` devuelve solo jugadores con
  `assists >= 1`, y que `total`/`total_pages` coinciden con el conteo real filtrado (incluyendo
  el caso con `position` seteado, que pasa por el branch `exact_stmt`).
- [ ] Verificar `pytest tests/` pasa con coverage ≥80%.
- [ ] Verificar `flake8 src/ tests/` sin errores.
- [ ] Verificar `isort --check-only src/ tests/` sin errores.

## Agent Routing Brief

**DDD Designer needed:** no

Es un filtro nuevo sobre un endpoint de lectura existente (`GET /ranking`), que reutiliza datos
(`goals`, `assists`) ya calculados y expuestos por el dominio actual. No introduce entidades,
value objects ni invariantes de negocio nuevas — es un umbral simple (`>= 1`) sobre columnas
agregadas existentes, análogo en complejidad al filtro `bonus_label` ya presente.

## Verificación

1. `GET /ranking?season=<season>&bonus_label=Goleador&page=1&limit=15` y
   `GET /ranking?season=<season>&bonus_label=Goleador&page=2&limit=15` — confirmar que
   `total`/`total_pages` coinciden con el número real de jugadores con `goals >= 1` en esa
   temporada, y que no hay páginas vacías mientras existan jugadores válidos en páginas
   siguientes.
2. Repetir el paso 1 con `bonus_label=Asistidor` verificando `assists >= 1`.
3. Repetir ambos casos combinando `position=<pos>` y `competition_id=<id>` para ejercitar el
   branch `exact_stmt` de `get_ranking_total`/`get_ranking_total_all_seasons`.
4. Confirmar que un jugador con `goals >= 1` y `assists >= 1` simultáneamente aparece en ambos
   filtros (`Goleador` y `Asistidor`) sin necesidad de ajuste adicional, validando que no son
   mutuamente excluyentes.
5. Confirmar que `bonus_label=Promesa`/`bonus_label=Veterano` siguen funcionando exactamente
   igual que antes (regresión sobre el filtro existente).
