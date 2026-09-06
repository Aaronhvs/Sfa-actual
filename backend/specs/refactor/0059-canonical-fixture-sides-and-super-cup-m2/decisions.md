# Canonical fixture sides and UEFA Super Cup M2

## Context

API-Football can correct the home/away orientation, date or competition metadata of an existing
fixture. `IngestionRepository.upsert_fixture` currently updates only stage, matchday, status and
score on conflict, leaving stale fixture identity behind. Player events and player stats are
rebuilt from the latest provider payload, so they can disagree with the persisted fixture.

Production fixture `1552735` demonstrates the failure: API-Football reports Rennes as home and
PSG as away, while SFA kept PSG as home. The temporal ELO values themselves are sound, but the
scoring read model selected them through `PlayerEvent.is_away`, causing PSG and Rennes strengths
to be swapped for 40 events.

The UEFA Super Cup also has `stage_factor=2.00`. It is a single-match competition with
`competition_factor=1.05` and an independent `domestic_cup_minor` winner bonus. Comparable
supercups use factors from 1.00 to 1.30, so 2.00 duplicates trophy importance in every action.

## Decisions

1. Treat API-Football fixture identity as canonical on every upsert. On conflict update
   competition, home team, away team, season, kickoff, stage, matchday, status and official score.
2. Resolve an event's side from `PlayerEvent.team_id` against the fixture teams. Keep `is_away`
   only as a legacy fallback when `team_id` is null.
3. Fail closed when a non-null event team does not belong to the fixture or when its persisted
   `is_away` flag contradicts the canonical fixture side. Reingestion must repair the source data
   before scoring proceeds.
4. Normalize only `UEFA Super Cup/final` to `M2=1.30`. The value preserves international-final
   importance while matching the upper bound used by other supercups. Trophy value remains in
   the separate achievement bonus.
5. Apply the M2 change through a new idempotent SQL migration. Do not rewrite migration 0014.
6. Repair fixture `1552735` by targeted API reingestion, then replay the complete club ELO pool
   and scoring for season 2026. This rebuilds all downstream snapshots deterministically.
7. Audit all season-2026 events before and after repair. The postcondition is zero side
   inconsistencies and calculation details showing PSG ELO greater than Rennes ELO for PSG events.
8. Before a strict club ELO replay, seed teams discovered after the season bootstrap. Carry the
   prior-season closing ELO forward when available; otherwise use the approved 1000-point default
   with explicit provenance. Keep strict baseline validation after this idempotent bootstrap.

## Architecture

No new domain entity, endpoint or provider is required. Fixture corrections remain in existing
output adapters and migration data. Late entrant policy is isolated in an application use case
called by the existing ELO task orchestration. DDD Designer is not required because no scoring
value object or formula is added.

## Rollback

Stop automatic ingestion, restore the previous application image, set the UEFA Super Cup final
factor back to 2.00 only if product explicitly rejects 1.30, reingest the affected fixture and
replay season 2026. Do not manually edit snapshots or event scores.
