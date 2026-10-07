# Public descriptive team ranking

## Business Context

Publish an honest read-only team comparison using ingested observations, not a
predictive strength model or a new scoring input. Backend only; no deployment.

## Constraints

- Hexagonal router -> use case -> repository; immutable read DTOs.
- No score, ELO, M1, ingestion, database schema or frontend changes.
- `stats.base_points` already incorporates M1/M2/rating and cannot be advertised
  as independent base performance. Use individual event final points explicitly.
- Do not infer availability, injuries, starting XI or a verified current roster.
- Local configured PostgreSQL hostname is not resolvable. Live validation was
  subsequently completed through SSH using isolated staged code on the VPS.

## Decisions

| Decision | Alternative | Reason |
|---|---|---|
| `team-observed-merit-v1`, descriptive only | Independent base-strength claim | Existing stats base points contain contextual multipliers |
| 80% ELO percentile, 20% observed squad percentile | Calibrated prediction | Transparent policy weights, not fitted coefficients |
| Position/season midrank percentiles of individual points per 90 | Raw SFA totals | Reduce exposure and positional scale bias |
| Shrink player percentile toward 50 by minutes/(minutes+450) | Unadjusted short samples | Conservative evidence adjustment |
| Minutes-weighted observed squad mean | Invented best XI | No lineup/availability evidence |
| Latest ten completed fixtures per team per physical season | Unbounded history | Bounded recent observed performance |
| Verified PlayerStats.team_id on fixture sides | Player.team_id | Historical attribution, transfers remain with actual appearance |
| One coherent rules version chosen by current appearance coverage, then prior coverage; active version breaks ties | Mix scoring versions | Avoid duplicate scoring and incompatible units |
| Previous physical season only if current component absent | Blend or transfer historical players into current roster | Explicit bounded fallback, no fabricated current membership |
| Normalize over whole participant population before filters/pages | Filter-local percentile | Stable score under search, competition and pagination |
| Renormalize present component weights and disclose effective weights | Fill unknown with zero/average | Preserve meaningful unknowns |
| Aggregate SQL reads, then small in-memory team/player calculations | Per-team queries | Fixed query count, no N+1 |

## API Contract

`GET /api/v1/teams/ranking`: optional mutually exclusive `scope=season-2026`
or `season=2026` (physical starting season, also YYYY-YY); default latest fixture
season for participant kind. Only season scopes are supported, not award-period
World Cup rollups. `participant_kind=club|national` defaults to club;
`competition_id`, case-insensitive literal `name`, `page>=1`, `1<=limit<=50`.

Envelope: `season`, `scope`, `total`, `pagination`, `model`, `ranking`.
Item: `rank`, `id`, `name`, `team_logo_url`, `competition_id`, `competition`,
`score`, `elo_raw`, `elo_score`, `squad_score`, `effective_elo_weight`,
`effective_squad_weight`, `elo_season`, `elo_source`, `squad_season`,
`observed_players`, `scored_players`, `observed_appearances`,
`scored_appearances`, `coverage`, `availability` (always null).
Model metadata includes weights, window, shrinkage, rules version, population,
sources, exclusions, fallback and attribution policy and caveats.
`experimental=true`; `model.as_of` is the query timestamp, `model.data_cutoff`
is the latest scored fixture in the population. `squad_data_cutoff` is per team;
`elo_data_cutoff=null` because the season summary has no reliable update date.
Competition filter means observed participation in requested physical season;
Display competition prefers a recognized domestic league with verified fixture
participation in the requested physical season; fallback is catalog competition.
The five names are La Liga, Premier League, Bundesliga, Serie A and Ligue 1;
the actual schema has no competition type. No ID-based guessing (ID 10 is Champions
League). Multiple domestic leagues resolve by distinct fixture count, last fixture
date, then competition ID. This is display attribution only; all observed
competition memberships and population normalization remain unchanged.
`national` and `national_team` both resolve to canonical stored `national_team`.
No-data returns 200 empty. Invalid parameters 422. Null-score teams sort last.
Rank is within the filtered result; scores are population-stable.

## Data And Mathematics

Population is teams participating in requested-season fixtures or possessing
requested-season strength rows of matching participant kind. Only that population
can receive previous-season fallback. ELO rows with actual raw ELO and recognized
ELO source are selected deterministically by competition ID (duplicate season
summaries are not summed or maximized). Summary timestamps are not reliable
update dates and are not advertised as such.

Select recent completed fixtures with played_at <= request timestamp. Aggregate
event scores before joining appearance minutes to avoid multiplication. Only
appearances with positive minutes, matching season and verified fixture side
count. Missing score rows do not imply zero performance. An appearance with a
stats score establishes individual scoring coverage; sum final individual event
points for that appearance. Never read season achievement/collective bonuses.
Normalize players by catalog position (not historical position), separately per
season. A transferred player contributes once to the percentile cohort (points
and minutes combined across observed teams); their historical appearances remain
with their actual teams. Midrank:
100*(number_lower + (number_equal-1)/2)/(N-1); singleton 50.
Shrunk percentile: 50 + (percentile-50)*minutes/(minutes+450).
Squad mean weights each scored player's minutes; denominator includes only scored
minutes. Coverage = scored appearances / all observed appearances; not a roster
completion probability. ELO percentile uses selected current/fallback raw ELO over
the same population. Unrounded scores determine ordering; team ID breaks ties.

Limitations: final SFA contains M1 and individual bonuses, position labels may be
current, missing data can bias selection, prior/current ELO and partial/single
component scores are not calibrated comparisons, summaries have unknown freshness.
This read model MUST NEVER feed M1 or score recalculation.

## External Integrations

None. Team logo uses the existing API-Football external-ID URL convention when
an external team ID exists; otherwise null.

## Baseline

Initial pytest collection: 58 errors from ambient DEBUG=release. With process-only
DEBUG=false: 593 passed before changes; no source configuration modified.

## Verification Results (2026-10-06 Chile)

Follow-up review: correct stale/overwritten team catalog display association and
national participant alias. Regression tests and repeated VPS read-only validation
completed; the public fixture is refreshed. The September
20 observed-data cutoff is not a claim of up-to-date/live match ingestion.

Final follow-up results:
- Complete suite: 639 passed in 10.90 seconds (46 new ranking tests).
- Targeted tests with coverage: 46 passed in 14.32 seconds; 100% new-module line coverage.
- Scoped flake8/isort pass.
- VPS READ ONLY with force_generic_plan: 751 clubs, 48 national teams, four
  queries, 2.678 seconds; pagination, stable population/versions, domestic display
  and both national aliases pass. Scores unchanged from previous captured data.
- Prepared generic plans exposed a remaining nested-loop issue after repeated
  requests. Final query materializes distinct observed seasons (at most two),
  uses set intersection for verified version coverage and aggregates individual
  scores by version/season before attribution; no planner/session settings change
  in the production endpoint, no migrations or N+1 reads.
- Confirmed Barcelona -> La Liga, Liverpool -> Premier League, PSG -> Ligue 1.
- Updated fixture: output/playwright/team-ranking-live.json. Cutoff unchanged:
  2026-09-20T19:00:00Z; request timestamp is not ingestion freshness.

- Complete suite: 634 passed in 11.16 seconds; 41 new tests.
- Targeted new tests with coverage: 41 passed in 11.95 seconds; new domain,
  application, repository, router and schema modules have 100% line coverage.
- Scoped flake8 and isort checks pass. Existing global coverage artifact untouched.
- Actual VPS PostgreSQL via SSH BatchMode, staged source under
  `/tmp/sfa-team-ranking-check.d7cZ6a`, no service restart or deployment.
- The verification script enforces `SET TRANSACTION READ ONLY`, checks that
  transaction_read_only is on and avoids ASGI lifespan (no create_all).
- Initial live verification exposed a >30-second planner issue in version
  selection. Fixed by materializing bounded appearances and score projections
  and using a verified-appearance semijoin, without indexes or DB writes.
- Final actual endpoint: HTTP 200, 751 club teams, rules version 4, four
  aggregate reads, first response 2.344 seconds; repeat 2.248 seconds.
- Data cutoff: 2026-09-20T19:00:00Z. Top-20 observed/scored players: 457/425.
- Real examples: Barcelona 92.4805 (coverage 0.9302), Inter 92.0307,
  Bayern 91.8543. These are descriptive merits, not strength predictions.
- Real pagination pages have disjoint IDs; literal name filtering preserves
  the population score; mutually exclusive selectors return 422.
- Public response fixture: `output/playwright/team-ranking-live.json`, requested
  by the frontend owner; no frontend source files changed by this work.
- Script: `scripts/verify_team_ranking_readonly.py --response-json <public-path>`.
- No migrations, score/M1 changes, deployments or commits.
