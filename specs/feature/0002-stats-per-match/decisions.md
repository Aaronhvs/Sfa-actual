# ADR 0002 — Stats-per-match row in player_events

**Status:** Accepted  
**Date:** 2026-05-14  
**Author:** Architecture Engineer (SFA)

---

## Context

Phase 3 of `IngestCompetitionUseCase` calls `SFAScoringService.score_match_stats()` and adds
the result to `_PlayerAccum.total_pts`, but never writes a row to `player_events`.
This creates three observable defects:

1. Players with 0 goals + 0 assists have no `player_events` row for a fixture.
2. `matches_played` in `sfa_season_scores` only reflects fixtures with goal/assist events.
3. The per-fixture breakdown (regates, duelos, tackles) is invisible in the frontend.

---

## Decision 1 — Persist a STATS event row for every qualifying fixture

**Chosen approach:** After computing `stat_scores`, write a single aggregated
`player_events` row of type `EventType.STATS` per player-fixture.  
The row carries the sum of all stat-score points for that match.

**Rejected alternative — one row per ActionType:** Would multiply rows, complicate
frontend queries, and offer no business benefit because the per-action breakdown
is already stored in `player_stats` / `sfa_season_scores.breakdown`.

**Constraints satisfied:**
- `PlayerEvent.minute` has a DB check `BETWEEN 1 AND 120`. We will use `minute=90`
  as the canonical sentinel for a match-stats event (full-match aggregate, no exact
  minute exists). This is accurate enough and avoids a schema migration.
- `score_before`, `score_diff`, `psxg` can be `NULL` — already nullable in the model.
- Multiplier columns `m1`/`m2`/`m3`/`m4`/`mvisit`: for a STATS row we store the
  M1 and M2 values actually used in `score_match_stats()` and set m3=1.0, m4=1.0,
  mvisit=1.0 (neutral, matching the existing scoring logic). The DB check on `m3 > 0`
  is satisfied; `m4 BETWEEN 1.0 AND 2.0` is satisfied; `mvisit IN (1.0, 1.3)` is
  satisfied.
- `upsert_player_event` currently uses a plain `INSERT` with no unique constraint on
  `(player_id, fixture_id, event_type)`. The existing
  `delete_player_events_for_fixture` call at the top of the per-player loop already
  wipes stale data, so idempotency is preserved — no schema change needed for this.

---

## Decision 2 — No new ActionType values for this feature

`fouls.drawn`, `tackles.clearances`, and `penalty.won` are NOT added to
`ActionType` or `BASE_POINTS_TABLE` in this feature.  Reasons:

- They are absent from the current scoring document (v2.0).
- Adding them requires a product decision on point values before engineering.
- This feature's goal is persistence, not scoring expansion.

`dribbles.attempts` will be extracted to `PlayerStatsRawDTO` (see Decision 4) as a
raw field for future analytics but will not be scored.

A dedicated follow-up feature (`0003-new-stat-actions`) should handle DDD-Designer
involvement and BASE_POINTS_TABLE expansion.

---

## Decision 3 — `matches_played` correctness

`accum.matches_played` is already incremented unconditionally for every player with
`minutes >= 20` (line 224 of `ingest_competition.py`). The bug is that
`upsert_season_score` is only reached when `accum.total_minutes >= 90` (Phase 4
filter). No change is needed to the counter itself; the new STATS row ensures
`total_pts > 0` for stat-heavy players who never scored/assisted, which does not
affect the `>= 90 min` gate. `matches_played` is therefore already correct once
the player clears the season-score threshold — confirmed.

---

## Decision 4 — Minimal DTO expansion (provider layer only)

Add three fields to `PlayerStatsRawDTO` that the API already returns at no extra cost:

| New field           | API-Football path                    | Purpose                        |
|---------------------|--------------------------------------|--------------------------------|
| `fouls_drawn`       | `fouls.drawn`                        | Raw storage, not scored yet    |
| `clearances`        | `tackles.clearances`                 | Raw storage, not scored yet    |
| `dribbles_attempts` | `dribbles.attempts`                  | Raw storage, not scored yet    |

`penalty_won` is skipped: the API field (`penalty.won`) is unreliable (often null
even when a penalty was conceded to the player) and should be derived from fixture
events instead — deferred to feature 0003.

These fields must be:
- Added to `PlayerStatsRawDTO` (frozen dataclass in `ingestion_ports.py`)
- Extracted in `APIFootballProvider.fetch_fixture_players()` (`api_football.py`)
- Stored via `upsert_player_stats` dict under keys
  `fouls_drawn`, `clearances`, `dribbles_attempts`
- Persisted in new `PlayerStats` columns (migration required)

**No scoring impact in this feature.**

---

## Decision 5 — No new `EventType` enum value

`EventType.STATS` already exists (`infrastructure/models/enums.py` line 19).
No enum change is required.

---

## Decision 6 — `upsert_player_event` signature is unchanged

The existing signature already accepts all the fields needed for a STATS row.
The call site in the use case changes; the repository and port remain identical.

---

## Decision 7 — `score_match_stats()` returns per-action SFAScore list

The use case currently sums `s.total` across all returned `SFAScore` objects and
adds to `accum.total_pts`. The new behaviour adds one step: sum all `s.total`
values into `stats_pts`, then call `upsert_player_event` once with that total.
The `m1`, `m2`, `m3`, `m4`, `mvisit` stored in the row correspond to the
`CombinedMultiplier` of the **first non-zero** SFAScore (all scores in a
`score_match_stats` call share the same multiplier object since M1/M2 are computed
once per call). This is architecturally sound and avoids inventing a new method.

---

## Layers touched

| Layer                          | File                                               | Change type      |
|--------------------------------|----------------------------------------------------|------------------|
| Domain DTO                     | `domain/ingestion_ports.py`                        | Add 3 DTO fields |
| Domain scoring                 | `domain/scoring/services.py`                       | No change        |
| Domain scoring value objects   | `domain/scoring/value_objects.py`                  | No change        |
| Infra enum                     | `infrastructure/models/enums.py`                   | No change        |
| Infra model — PlayerEvent      | `infrastructure/models/events/models.py`           | No change        |
| Infra model — PlayerStats      | `infrastructure/models/player_stats/models.py`     | Add 3 columns    |
| Infra repository               | `infrastructure/repositories/ingestion_repository.py` | Update upsert_player_stats dict |
| Infra provider                 | `infrastructure/providers/api_football.py`         | Extract 3 fields |
| Application use case           | `application/use_cases/ingest_competition.py`      | Persist STATS row |
| DB migration                   | `alembic/versions/` (new file)                     | Add 3 columns    |
