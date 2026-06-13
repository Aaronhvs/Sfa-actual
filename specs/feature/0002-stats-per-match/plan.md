# Implementation Plan — 0002 Stats-per-match in player_events

**Feature branch:** `feat/0002-stats-per-match`  
**Spec date:** 2026-05-14  
**Scope:** Persistence of per-match stat scores as `player_events` rows + raw DTO expansion.

---

## Overview

Five sequential tasks. Each task corresponds to a single atomic commit.
No task has cross-task dependencies except the ordering noted below.

---

## Task 1 — Expand `PlayerStatsRawDTO` and provider extraction

**Files:**
- `backend/src/sfa/domain/ingestion_ports.py`
- `backend/src/sfa/infrastructure/providers/api_football.py`

### Changes

#### `ingestion_ports.py` — `PlayerStatsRawDTO`

Add three fields to the frozen dataclass (after `blocks`):

```python
fouls_drawn: int
clearances: int
dribbles_attempts: int
```

All three default to `0` — add `= 0` defaults so existing call sites that construct
the DTO positionally (tests, stubs) do not break immediately. Prefer keyword-only
construction going forward.

#### `api_football.py` — `fetch_fixture_players`

In the section that builds `PlayerStatsRawDTO`, add extraction of the three new fields.
The relevant API-Football response structure is:

```
statistics[0].fouls.drawn          → fouls_drawn
statistics[0].tackles.clearances   → clearances
statistics[0].dribbles.attempts    → dribbles_attempts
```

Add before the existing `result.append(...)` call:

```python
fouls = stats.get("fouls") or {}
# dribbles dict already extracted above

result.append(
    PlayerStatsRawDTO(
        ...existing fields...,
        fouls_drawn=fouls.get("drawn") or 0,
        clearances=tackles.get("clearances") or 0,
        dribbles_attempts=dribbles.get("attempts") or 0,
    )
)
```

**Test:** Unit-test `fetch_fixture_players` with a fixture response JSON that contains
the three new fields. Assert they are present on the returned DTO.

---

## Task 2 — Add columns to `PlayerStats` model + Alembic migration

**Files:**
- `backend/src/sfa/infrastructure/models/player_stats/models.py`
- `backend/alembic/versions/<timestamp>_add_raw_stats_columns.py` (new)

### Changes

#### `models.py`

Add three columns after `blocks`:

```python
fouls_drawn: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
clearances: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
dribbles_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
```

Add corresponding `CheckConstraint` entries:

```python
CheckConstraint("fouls_drawn >= 0", name="ck_ps_fouls_drawn"),
CheckConstraint("clearances >= 0", name="ck_ps_clearances"),
CheckConstraint("dribbles_attempts >= 0", name="ck_ps_dribbles_attempts"),
```

#### Alembic migration

```python
def upgrade() -> None:
    op.add_column("player_stats", sa.Column("fouls_drawn", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("player_stats", sa.Column("clearances", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("player_stats", sa.Column("dribbles_attempts", sa.SmallInteger(), nullable=False, server_default="0"))

def downgrade() -> None:
    op.drop_column("player_stats", "dribbles_attempts")
    op.drop_column("player_stats", "clearances")
    op.drop_column("player_stats", "fouls_drawn")
```

**Depends on:** Task 1 (DTO fields must exist before repo reads them).

---

## Task 3 — Update `upsert_player_stats` in repository

**File:** `backend/src/sfa/infrastructure/repositories/ingestion_repository.py`

### Changes

In `upsert_player_stats`, add the three new fields to both the `values(...)` and
`on_conflict_do_update(set_={...})` dicts:

```python
fouls_drawn=stats.get("fouls_drawn", 0),
clearances=stats.get("clearances", 0),
dribbles_attempts=stats.get("dribbles_attempts", 0),
```

**Depends on:** Task 2 (columns must exist in model before the ORM insert runs).

---

## Task 4 — Pass new fields through use-case `upsert_player_stats` call

**File:** `backend/src/sfa/application/use_cases/ingest_competition.py`

### Changes

In the `upsert_player_stats` dict (lines 228–240), add:

```python
"fouls_drawn": ps.fouls_drawn,
"clearances": ps.clearances,
"dribbles_attempts": ps.dribbles_attempts,
```

No other logic changes in this task.

**Depends on:** Task 1 (DTO fields), Task 3 (repo accepts new keys).

---

## Task 5 — Persist STATS `player_events` row (core feature)

**File:** `backend/src/sfa/application/use_cases/ingest_competition.py`

### Changes

Replace the current Phase 3 match-stats block (lines 302–315):

**Current code:**
```python
# Match stats
stats_for_scoring = {
    ActionType.DUELS_WON: ps.duels_won,
    ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
    ActionType.BLOCKS: ps.blocks,
    ActionType.DRIBBLES_WON: ps.dribbles_success,
}
stat_scores = self._scoring.score_match_stats(
    group, stats_for_scoring,
    player_team_pos, rival_pos, stage_factor,
)
for s in stat_scores:
    accum.total_pts += s.total
    _add_to_breakdown(accum.breakdown, "stats", s.total)
```

**New code:**
```python
# Match stats — score and persist as a STATS player_event row
stats_for_scoring = {
    ActionType.DUELS_WON: ps.duels_won,
    ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
    ActionType.BLOCKS: ps.blocks,
    ActionType.DRIBBLES_WON: ps.dribbles_success,
}
stat_scores = self._scoring.score_match_stats(
    group, stats_for_scoring,
    player_team_pos, rival_pos, stage_factor,
)
stats_total = sum(s.total for s in stat_scores)
if stat_scores:
    # All scores in a score_match_stats call share the same CombinedMultiplier
    combined = stat_scores[0].multiplier
    m1_val = float(M1RivalDifficulty(player_team_pos, rival_pos).value)
    m2_val = float(M2CompetitionStage(stage_factor).value)
    await self._repo.upsert_player_event(
        player_id=player_db_id,
        fixture_id=fixture_db_id,
        minute=90,               # sentinel: full-match aggregate
        event_type=EventType.STATS,
        score_before=None,
        score_diff=None,
        psxg=None,
        m1=m1_val,
        m2=m2_val,
        m3=1.0,                  # neutral (no minute context)
        m4=1.0,                  # neutral (no shot context)
        mvisit=1.0,              # neutral (no home/away bonus for stats)
        pts=round(stats_total, 2),
    )
if stats_total > 0:
    accum.total_pts += stats_total
    _add_to_breakdown(accum.breakdown, "stats", stats_total)
```

### Key invariants preserved

| Invariant                          | How satisfied                                                         |
|------------------------------------|-----------------------------------------------------------------------|
| Idempotency                        | `delete_player_events_for_fixture` (line 249) runs before all event writes, including the new STATS row |
| DB check `minute BETWEEN 1 AND 120` | `minute=90` satisfies this                                           |
| DB check `m3 > 0`                  | `m3=1.0`                                                             |
| DB check `m4 BETWEEN 1.0 AND 2.0` | `m4=1.0`                                                             |
| DB check `mvisit IN (1.0, 1.3)`   | `mvisit=1.0`                                                         |
| `score_before`/`score_diff`/`psxg` nullable | already nullable in schema                                  |
| `stats_total == 0` guard           | `if stat_scores:` — players with zero in every stat category get no STATS row, which is correct (they truly have no stat contribution) |
| `accum.total_pts` correctness      | unchanged: sum of all goal/assist/stat points still accumulates      |

**Depends on:** Tasks 1–4 (all prior changes must be in place).

---

## Task ordering (dependency graph)

```
Task 1 (DTO + provider)
    └── Task 2 (model + migration)
            └── Task 3 (repo upsert dict)
                    └── Task 4 (use-case stats dict)
                            └── Task 5 (STATS event row — core)
```

Tasks 1–4 are prep; Task 5 is the observable fix.

---

## Testing checklist

### Unit tests

- [ ] `PlayerStatsRawDTO` accepts the three new fields with defaults of 0
- [ ] `APIFootballProvider.fetch_fixture_players` extracts `fouls_drawn`, `clearances`,
      `dribbles_attempts` from fixture response JSON (mock HTTP)
- [ ] `IngestCompetitionUseCase` integration: a player with `minutes >= 20`, `goals=0`,
      `assists=0`, `dribbles_success=3` produces exactly one `player_events` row of
      type `STATS` after execution
- [ ] Same player with `minutes >= 20` and all stat values = 0 produces no `STATS` row
- [ ] `matches_played` in `sfa_season_scores` equals the number of fixtures where
      `minutes >= 20`, regardless of goal/assist presence

### Manual verification

- [ ] Run ingestion for La Liga season 2024 on dev DB; query:
      `SELECT COUNT(*) FROM player_events WHERE event_type='stats'` — should be non-zero
- [ ] Lamine Yamal: verify he has `player_events` rows for fixtures with 0 goals/assists
- [ ] `sfa_season_scores.matches_played` for Yamal matches actual appearances

---

## Out of scope (deferred to feature 0003)

- `fouls.drawn` scoring (requires DDD-Designer + BASE_POINTS_TABLE expansion)
- `tackles.clearances` scoring for DC/LAT positions
- `penalty.won` detection from fixture events
- GK scoring (no position group defined)
- Frontend changes (separate frontend feature ticket)
