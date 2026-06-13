-- Read-only diagnosis for player team snapshots before migration 0021.
-- This reproduces both backfill candidates without altering any table.

\echo '1. Legacy candidate mismatches'
WITH unresolved AS (
    SELECT ps.id, ps.player_id, ps.fixture_id
    FROM player_stats ps
    JOIN players p ON p.id = ps.player_id
    JOIN fixtures f ON f.id = ps.fixture_id
    WHERE p.team_id IS NULL
       OR p.team_id NOT IN (f.home_team_id, f.away_team_id)
)
SELECT
    COUNT(*) AS unresolved_rows,
    COUNT(DISTINCT player_id) AS affected_players,
    COUNT(DISTINCT fixture_id) AS affected_fixtures,
    ROUND(
        COUNT(*)::numeric / NULLIF(COUNT(DISTINCT player_id), 0),
        2
    ) AS rows_per_player
FROM unresolved;

\echo '2. Candidate 2 impact and final unresolved count'
WITH legacy_unresolved AS (
    SELECT
        ps.id,
        ps.player_id,
        ps.fixture_id,
        ps.season,
        f.competition_id
    FROM player_stats ps
    JOIN players p ON p.id = ps.player_id
    JOIN fixtures f ON f.id = ps.fixture_id
    WHERE p.team_id IS NULL
       OR p.team_id NOT IN (f.home_team_id, f.away_team_id)
),
score_resolved AS (
    SELECT DISTINCT lu.id
    FROM legacy_unresolved lu
    JOIN fixtures f ON f.id = lu.fixture_id
    JOIN sfa_season_scores sss
      ON sss.player_id = lu.player_id
     AND sss.competition_id = lu.competition_id
     AND sss.season = lu.season
    WHERE sss.team_id IN (f.home_team_id, f.away_team_id)
)
SELECT
    (SELECT COUNT(*) FROM legacy_unresolved) AS legacy_unresolved,
    (SELECT COUNT(*) FROM score_resolved) AS resolved_by_score,
    (
        SELECT COUNT(*)
        FROM legacy_unresolved lu
        WHERE NOT EXISTS (
            SELECT 1
            FROM score_resolved sr
            WHERE sr.id = lu.id
        )
    ) AS final_unresolved;

\echo '3. Concentration by player'
WITH unresolved AS (
    SELECT ps.player_id
    FROM player_stats ps
    JOIN players p ON p.id = ps.player_id
    JOIN fixtures f ON f.id = ps.fixture_id
    WHERE p.team_id IS NULL
       OR p.team_id NOT IN (f.home_team_id, f.away_team_id)
),
per_player AS (
    SELECT player_id, COUNT(*) AS rows_count
    FROM unresolved
    GROUP BY player_id
)
SELECT
    CASE
        WHEN rows_count = 1 THEN '1'
        WHEN rows_count BETWEEN 2 AND 5 THEN '2-5'
        WHEN rows_count BETWEEN 6 AND 20 THEN '6-20'
        WHEN rows_count BETWEEN 21 AND 50 THEN '21-50'
        ELSE '51+'
    END AS rows_bucket,
    COUNT(*) AS players,
    SUM(rows_count) AS rows
FROM per_player
GROUP BY rows_bucket
ORDER BY MIN(rows_count);

\echo '4. Invalid player identities requiring manual quarantine'
SELECT
    p.id,
    p.external_id,
    p.name,
    COUNT(ps.id) AS stats_rows,
    COUNT(DISTINCT ps.fixture_id) AS fixtures
FROM players p
LEFT JOIN player_stats ps ON ps.player_id = p.id
WHERE p.external_id IS NULL
   OR p.external_id <= 0
GROUP BY p.id, p.external_id, p.name
ORDER BY stats_rows DESC, p.id;

\echo '5. Most affected players'
WITH unresolved AS (
    SELECT ps.player_id, ps.fixture_id
    FROM player_stats ps
    JOIN players p ON p.id = ps.player_id
    JOIN fixtures f ON f.id = ps.fixture_id
    WHERE p.team_id IS NULL
       OR p.team_id NOT IN (f.home_team_id, f.away_team_id)
)
SELECT
    p.id,
    p.external_id,
    p.name,
    t.name AS current_team,
    COUNT(*) AS unresolved_rows,
    COUNT(DISTINCT u.fixture_id) AS fixtures
FROM unresolved u
JOIN players p ON p.id = u.player_id
LEFT JOIN teams t ON t.id = p.team_id
GROUP BY p.id, p.external_id, p.name, t.name
ORDER BY unresolved_rows DESC, p.name
LIMIT 50;
