-- Migration 0012: Versioned Scoring Rules & Raw-Event Recalculation
-- Applies: 2026-05-31
-- Spec: specs/refactor/0012-versioned-scoring-rules/

BEGIN;

-- ─── 1. scoring_rules_versions ────────────────────────────────────────────────

CREATE TABLE scoring_rules_versions (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    version     VARCHAR(20)  NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    config_json JSONB   NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_scoring_rules_version_name UNIQUE (name)
);

-- At most one active version at any time
CREATE UNIQUE INDEX uq_scoring_rules_active
    ON scoring_rules_versions (is_active)
    WHERE is_active = TRUE;


-- ─── 2. player_events — add context columns ───────────────────────────────────

ALTER TABLE player_events
    ADD COLUMN player_team_pos SMALLINT,
    ADD COLUMN rival_team_pos  SMALLINT,
    ADD COLUMN is_away         BOOLEAN;


-- ─── 3. player_event_scores ──────────────────────────────────────────────────

CREATE TABLE player_event_scores (
    id                    SERIAL PRIMARY KEY,
    event_id              INTEGER NOT NULL REFERENCES player_events(id) ON DELETE CASCADE,
    player_id             INTEGER NOT NULL REFERENCES players(id),
    fixture_id            INTEGER NOT NULL REFERENCES fixtures(id),
    season                VARCHAR(10)  NOT NULL,
    competition_id        INTEGER NOT NULL REFERENCES competitions(id),
    rules_version_id      INTEGER NOT NULL REFERENCES scoring_rules_versions(id),
    action_type           VARCHAR(50)  NOT NULL,
    position              VARCHAR(10)  NOT NULL,
    base_points           NUMERIC(10, 2) NOT NULL,
    m1                    NUMERIC(5, 3)  NOT NULL,
    m2                    NUMERIC(5, 3)  NOT NULL,
    m3                    NUMERIC(5, 3)  NOT NULL,
    m4                    NUMERIC(5, 3)  NOT NULL,
    mvisit                NUMERIC(3, 2)  NOT NULL DEFAULT 1.0,
    mrating               NUMERIC(3, 2)  NOT NULL DEFAULT 1.0,
    combined_before_clamp NUMERIC(8, 4)  NOT NULL,
    combined_after_clamp  NUMERIC(8, 4)  NOT NULL,
    final_points          NUMERIC(10, 2) NOT NULL,
    calculation_details   JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pes_event_version UNIQUE (event_id, rules_version_id)
);

CREATE INDEX ix_pes_player_season
    ON player_event_scores (player_id, season, rules_version_id);

CREATE INDEX ix_pes_competition
    ON player_event_scores (competition_id, season, rules_version_id);


-- ─── 4. sfa_season_scores — add rules_version_id, replace unique constraint ───

ALTER TABLE sfa_season_scores
    ADD COLUMN rules_version_id INTEGER REFERENCES scoring_rules_versions(id);

-- Drop the old single unique constraint
ALTER TABLE sfa_season_scores
    DROP CONSTRAINT IF EXISTS uq_sfa_season_score;

-- Legacy scores (rules_version_id IS NULL): one row per (player, competition, season)
CREATE UNIQUE INDEX uq_sfa_season_score_legacy
    ON sfa_season_scores (player_id, competition_id, season)
    WHERE rules_version_id IS NULL;

-- Versioned scores (rules_version_id IS NOT NULL): one row per (player, competition, season, version)
CREATE UNIQUE INDEX uq_sfa_season_score_versioned
    ON sfa_season_scores (player_id, competition_id, season, rules_version_id)
    WHERE rules_version_id IS NOT NULL;

COMMIT;
