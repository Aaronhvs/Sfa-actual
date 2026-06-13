-- Diagnostic mode works before migration 0021; post-expand mode adds the five
-- critical snapshot counters. Run with psql so the conditional blocks can
-- detect whether the snapshot columns exist.

SELECT
    COUNT(*) AS player_stats_rows,
    COUNT(*) FILTER (
        WHERE p.team_id IN (f.home_team_id, f.away_team_id)
    ) AS legacy_player_candidate_valid,
    COUNT(*) FILTER (
        WHERE p.team_id IS NOT NULL
          AND p.team_id NOT IN (f.home_team_id, f.away_team_id)
    ) AS legacy_player_candidate_invalid
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
JOIN fixtures f ON f.id = ps.fixture_id;

SELECT
    COUNT(DISTINCT ps.id) AS season_score_candidate_valid
FROM player_stats ps
JOIN fixtures f ON f.id = ps.fixture_id
JOIN sfa_season_scores sss
  ON sss.player_id = ps.player_id
 AND sss.competition_id = f.competition_id
 AND sss.season = ps.season
WHERE sss.team_id IN (f.home_team_id, f.away_team_id);

SELECT
    ps.player_id,
    ps.fixture_id
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
JOIN fixtures f ON f.id = ps.fixture_id
WHERE p.team_id NOT IN (f.home_team_id, f.away_team_id)
  AND NOT EXISTS (
      SELECT 1
      FROM sfa_season_scores sss
      WHERE sss.player_id = ps.player_id
        AND sss.competition_id = f.competition_id
        AND sss.season = ps.season
        AND sss.team_id IN (f.home_team_id, f.away_team_id)
  )
ORDER BY ps.fixture_id, ps.player_id
LIMIT 100;

DO $$
DECLARE
    has_stats_snapshot BOOLEAN;
    has_events_snapshot BOOLEAN;
    audit_count BIGINT;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'player_stats' AND column_name = 'team_id'
    ) INTO has_stats_snapshot;
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'player_events' AND column_name = 'team_id'
    ) INTO has_events_snapshot;

    IF has_stats_snapshot THEN
        EXECUTE 'SELECT COUNT(*) FROM player_stats WHERE team_id IS NULL'
            INTO audit_count;
        RAISE NOTICE 'player_stats.team_id IS NULL: %', audit_count;

        EXECUTE $sql$
            SELECT COUNT(*)
            FROM player_stats ps
            JOIN fixtures f ON f.id = ps.fixture_id
            WHERE ps.team_id IS NOT NULL
              AND ps.team_id NOT IN (f.home_team_id, f.away_team_id)
        $sql$ INTO audit_count;
        RAISE NOTICE 'player_stats snapshot outside fixture: %', audit_count;
    END IF;

    IF has_events_snapshot THEN
        EXECUTE 'SELECT COUNT(*) FROM player_events WHERE team_id IS NULL'
            INTO audit_count;
        RAISE NOTICE 'player_events.team_id IS NULL: %', audit_count;

        IF has_stats_snapshot THEN
            EXECUTE $sql$
                SELECT COUNT(*)
                FROM player_events pe
                JOIN player_stats ps
                  ON ps.player_id = pe.player_id
                 AND ps.fixture_id = pe.fixture_id
                WHERE pe.team_id IS DISTINCT FROM ps.team_id
            $sql$ INTO audit_count;
            RAISE NOTICE 'player event/stat snapshot mismatch: %', audit_count;
        END IF;
    END IF;

    SELECT COUNT(*)
    INTO audit_count
    FROM player_events pe
    LEFT JOIN player_stats ps
      ON ps.player_id = pe.player_id
     AND ps.fixture_id = pe.fixture_id
    WHERE ps.id IS NULL;
    RAISE NOTICE 'player events without player_stats: %', audit_count;
END $$;
