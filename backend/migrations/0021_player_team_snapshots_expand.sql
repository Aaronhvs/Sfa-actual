-- 0021: expand player team snapshots.
-- Safe to re-run. Apply before deploying code that stops writing players.team_id.

ALTER TABLE players
    ALTER COLUMN team_id DROP NOT NULL;

ALTER TABLE competitions
    ADD COLUMN IF NOT EXISTS participant_kind VARCHAR(20) NOT NULL DEFAULT 'club';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_competitions_participant_kind'
    ) THEN
        ALTER TABLE competitions
            ADD CONSTRAINT ck_competitions_participant_kind
            CHECK (participant_kind IN ('club', 'national_team')) NOT VALID;
    END IF;
END $$;

ALTER TABLE competitions
    VALIDATE CONSTRAINT ck_competitions_participant_kind;

ALTER TABLE player_stats
    ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id);

CREATE INDEX IF NOT EXISTS ix_player_stats_team_season
    ON player_stats(team_id, season);

ALTER TABLE player_events
    ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id);

CREATE INDEX IF NOT EXISTS ix_player_events_team_fixture
    ON player_events(team_id, fixture_id);

-- Candidate 1: the legacy player team, only when it belongs to the fixture.
UPDATE player_stats ps
SET team_id = p.team_id
FROM players p, fixtures f
WHERE ps.team_id IS NULL
  AND p.id = ps.player_id
  AND f.id = ps.fixture_id
  AND p.team_id IN (f.home_team_id, f.away_team_id);

-- Candidate 2: the existing season-score snapshot. Prefer the team with the
-- highest score when more than one version exists for the same scope.
WITH score_candidates AS (
    SELECT DISTINCT ON (ps.id)
        ps.id AS player_stats_id,
        sss.team_id
    FROM player_stats ps
    JOIN fixtures f ON f.id = ps.fixture_id
    JOIN sfa_season_scores sss
      ON sss.player_id = ps.player_id
     AND sss.competition_id = f.competition_id
     AND sss.season = ps.season
    WHERE ps.team_id IS NULL
      AND sss.team_id IN (f.home_team_id, f.away_team_id)
    ORDER BY
        ps.id,
        (sss.total_pts + sss.achievement_bonus_pts) DESC,
        sss.last_updated DESC
)
UPDATE player_stats ps
SET team_id = sc.team_id
FROM score_candidates sc
WHERE ps.id = sc.player_stats_id
  AND ps.team_id IS NULL;

UPDATE player_events pe
SET team_id = ps.team_id
FROM player_stats ps
WHERE pe.team_id IS NULL
  AND ps.player_id = pe.player_id
  AND ps.fixture_id = pe.fixture_id
  AND ps.team_id IS NOT NULL;

SELECT 'player_stats_team_id_null' AS audit_name, COUNT(*) AS audit_count
FROM player_stats
WHERE team_id IS NULL
UNION ALL
SELECT 'player_events_team_id_null', COUNT(*)
FROM player_events
WHERE team_id IS NULL
UNION ALL
SELECT 'player_stats_team_outside_fixture', COUNT(*)
FROM player_stats ps
JOIN fixtures f ON f.id = ps.fixture_id
WHERE ps.team_id IS NOT NULL
  AND ps.team_id NOT IN (f.home_team_id, f.away_team_id)
UNION ALL
SELECT 'player_event_stats_team_mismatch', COUNT(*)
FROM player_events pe
JOIN player_stats ps
  ON ps.player_id = pe.player_id
 AND ps.fixture_id = pe.fixture_id
WHERE pe.team_id IS DISTINCT FROM ps.team_id
UNION ALL
SELECT 'player_events_without_stats', COUNT(*)
FROM player_events pe
LEFT JOIN player_stats ps
  ON ps.player_id = pe.player_id
 AND ps.fixture_id = pe.fixture_id
WHERE ps.id IS NULL;

SELECT ps.id, ps.player_id, ps.fixture_id
FROM player_stats ps
WHERE ps.team_id IS NULL
ORDER BY ps.id
LIMIT 100;

SELECT pe.id, pe.player_id, pe.fixture_id
FROM player_events pe
WHERE pe.team_id IS NULL
ORDER BY pe.id
LIMIT 100;
