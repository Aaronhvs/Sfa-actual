# 0030 - World Cup Match Detail

## Context

The World Cup dashboard lists fixtures, but fixture cards are not interactive. Users
need a match detail containing venue information, lineups and a compact statistical
comparison.

API-Football exposes this information through fixture detail, fixture lineups and
fixture statistics endpoints. The existing World Cup read model already calls
API-Football through `WorldCupRepository` and caches responses in Redis.

## Scope

- Make every World Cup fixture card open `/mundial/partido/:fixtureId`.
- Display score/status, date, venue, city and referee.
- Display coach, formation, starters and substitutes for both teams.
- Display a normalized home/away statistical comparison.
- Preserve Spanish team labels in the frontend.
- Provide explicit empty states when API-Football has not published a section.

## Decisions

### D1. Extend the existing World Cup read side

The feature extends `WorldCupRepositoryProtocol`, `WorldCupRepository`,
`APIFootballProvider`, `wc_router.py` and `wc_schemas.py`. It does not introduce a
second fixture-detail bounded context.

### D2. Read through API-Football and Redis

Match detail is fetched on demand and cached by fixture external ID. No SQLAlchemy
model or migration is required. This avoids duplicating volatile live-match data and
keeps the implementation consistent with `/wc/fixtures` and `/wc/standings`.

Cache TTL:

- live or unfinished match: 60 seconds
- finished match: 15 minutes
- scheduled match: 15 minutes

### D3. One backend endpoint

`GET /api/v1/wc/fixtures/{fixture_id}` returns a composed response. The repository
may perform up to three API-Football requests on a cache miss:

- `fixtures?id={fixture_id}`
- `fixtures/lineups?fixture={fixture_id}`
- `fixtures/statistics?fixture={fixture_id}`

The frontend never calls API-Football directly.

### D4. Stable domain DTOs

The domain receives provider-independent DTOs for:

- fixture metadata and venue
- team lineup, coach and formation
- lineup players
- normalized statistics

Unknown or unavailable values remain nullable. The provider adapter owns parsing
API-Football payload shapes.

### D5. Statistical normalization

Statistics are returned as labels plus home/away display values. Numeric percentages
are also exposed when parsable so the frontend can render comparison bars. Missing
metrics do not become zero unless API-Football explicitly returns zero.

### D6. Frontend route instead of modal

A dedicated route supports browser navigation, refresh and sharing:

`/mundial/partido/:fixtureId`

The page uses the existing tournament tokens and returns to the previous World Cup
dashboard state through browser history, with `/mundial` as fallback.

### D7. No scoring changes

This is a read-only presentation feature. It does not alter ingestion, player event
scores, season scores, ELO, achievements or recalculation.

### D8. Tactical pitch and SFA score enrichment

The summary view replaces redundant general information with one tactical pitch per
team. API-Football `grid` values determine player placement; when grid data is absent,
the written lineup remains the fallback.

The repository enriches lineup players by matching API-Football `external_id` against
`players.external_id`, then sums `player_event_scores.final_points` for the fixture
and active rules version. It exposes nullable `player_id` and `sfa_points`. A null
score means the match has not been processed; zero remains a valid calculated score.

Provider payloads stay Redis-cached, while SFA score enrichment is queried from
PostgreSQL on each detail request so recalculations appear immediately.

## Failure handling

- Unknown fixture: backend returns `404`.
- API-Football failure: existing provider retry behavior applies and the router
  returns a service error.
- Missing lineups/statistics: endpoint returns empty arrays and the frontend renders
  an explanatory empty state.

## Verification

- Provider parsing tests cover complete and partial API payloads.
- Use case tests cover successful detail and not-found behavior using a concrete fake.
- Frontend TypeScript build must pass.
- Manual API verification uses a known World Cup fixture ID.
