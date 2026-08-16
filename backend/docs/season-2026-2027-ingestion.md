# Season 2026/2027 ingestion runbook

API-Football identifies the 2026/2027 club season as `2026`.

## Deployment order

1. Deploy the API, Celery worker and Celery beat from the same image.
2. Import the 2026 fixture calendars and teams without player-event processing.
3. Seed the canonical ClubElo baseline for season `2026` using the cutoff derived
   from the first club fixture.
4. Ingest the already played UEFA Super Cup and the Community Shield with their
   target fixture IDs.
5. Confirm ELO replay and scoring complete, then leave Celery beat enabled.

This order matters because scoring is fail-closed when an active club does not have
a canonical ELO seed. Fixture and event ingestion commits before the replay task,
but production should not intentionally leave failed replay jobs in the queue.

## Automatic coverage

`sfa.tasks.ingest_today_task` checks yesterday and today every configured ingestion
interval. It only processes approved `(league_id, season)` pairs and only sends live
or recently completed fixture IDs through the expensive event/player phase.

The active 2026 set contains:

- UEFA Super Cup and the five domestic supercups/configured season openers.
- La Liga, Premier League, Bundesliga, Serie A and Ligue 1.
- Champions League, Europa League and Conference League.
- Copa del Rey, FA Cup, EFL Cup, DFB-Pokal, Coppa Italia and Coupe de France.

World Cup 2026 is intentionally no longer in the automatic whitelist.

## Match detail

Current club fixtures are exposed at:

`GET /api/v1/tournaments/fixtures/{fixture_external_id}?season=2026`

The endpoint validates that the fixture exists locally as a club fixture for the
current season before using API-Football. Timeline events come from ingestion storage
with a provider fallback, while lineups and match statistics use the shared Redis
cached fixture-detail adapter.

No database migration is required; the existing `fixture_events` table is reused.
