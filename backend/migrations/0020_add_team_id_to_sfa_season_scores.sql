ALTER TABLE sfa_season_scores
ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_sfa_season_scores_team_id
ON sfa_season_scores(team_id);
