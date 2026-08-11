-- 0048 - Authoritative ELO seeds, official fixture scores and temporal M1 snapshots.

ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS home_goals SMALLINT NULL;
ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS away_goals SMALLINT NULL;
ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS score_source VARCHAR(30) NULL;

CREATE TABLE IF NOT EXISTS team_elo_seeds (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season VARCHAR(10) NOT NULL,
    participant_kind VARCHAR(20) NOT NULL,
    elo_raw NUMERIC(7, 2) NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(30) NOT NULL,
    source_reference VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_team_elo_seed UNIQUE (team_id, season, participant_kind),
    CONSTRAINT ck_team_elo_seed_kind
        CHECK (participant_kind IN ('club', 'national_team')),
    CONSTRAINT ck_team_elo_seed_positive CHECK (elo_raw > 0)
);

CREATE INDEX IF NOT EXISTS ix_team_elo_seed_scope
    ON team_elo_seeds (season, participant_kind);

CREATE TABLE IF NOT EXISTS fixture_team_strengths (
    fixture_id INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    season VARCHAR(10) NOT NULL,
    competition_id INTEGER NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    participant_kind VARCHAR(20) NOT NULL,
    pre_match_elo_raw NUMERIC(7, 2) NOT NULL,
    post_match_elo_raw NUMERIC(7, 2) NOT NULL,
    pre_match_strength NUMERIC(5, 2) NOT NULL,
    post_match_strength NUMERIC(5, 2) NOT NULL,
    model_version VARCHAR(30) NOT NULL,
    seed_source VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_fixture_team_strengths PRIMARY KEY (fixture_id, team_id),
    CONSTRAINT ck_fixture_team_strength_kind
        CHECK (participant_kind IN ('club', 'national_team')),
    CONSTRAINT ck_fixture_team_pre_strength
        CHECK (pre_match_strength BETWEEN 0 AND 100),
    CONSTRAINT ck_fixture_team_post_strength
        CHECK (post_match_strength BETWEEN 0 AND 100),
    CONSTRAINT ck_fixture_team_elo_positive
        CHECK (pre_match_elo_raw > 0 AND post_match_elo_raw > 0)
);

CREATE INDEX IF NOT EXISTS ix_fixture_team_strength_scope
    ON fixture_team_strengths (season, participant_kind, competition_id);

CREATE INDEX IF NOT EXISTS ix_fixture_team_strength_team
    ON fixture_team_strengths (team_id, season, fixture_id);

-- Rollback order:
-- DROP TABLE IF EXISTS fixture_team_strengths;
-- DROP TABLE IF EXISTS team_elo_seeds;
-- ALTER TABLE fixtures DROP COLUMN IF EXISTS score_source;
-- ALTER TABLE fixtures DROP COLUMN IF EXISTS away_goals;
-- ALTER TABLE fixtures DROP COLUMN IF EXISTS home_goals;
