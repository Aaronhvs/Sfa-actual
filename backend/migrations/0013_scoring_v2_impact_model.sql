-- Migration 0013: Scoring v2 — Impact Model
-- Applies: 2026-05-31
-- Spec: specs/refactor/0013-scoring-v2-impact-model/

BEGIN;

-- ─── 1. team_strengths ────────────────────────────────────────────────────────

CREATE TABLE team_strengths (
    id             SERIAL PRIMARY KEY,
    team_id        INTEGER NOT NULL REFERENCES teams(id),
    season         VARCHAR(10) NOT NULL,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    strength       NUMERIC(5, 2) NOT NULL,
    source         VARCHAR(20) NOT NULL DEFAULT 'calculated',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_team_strength UNIQUE (team_id, season, competition_id),
    CONSTRAINT ck_team_strength_range CHECK (strength BETWEEN 0 AND 100),
    CONSTRAINT ck_team_strength_source CHECK (source IN ('calculated', 'default', 'override'))
);

CREATE INDEX ix_team_strengths_season_comp ON team_strengths (season, competition_id);


-- ─── 2. competition_achievements ─────────────────────────────────────────────

CREATE TABLE competition_achievements (
    id             SERIAL PRIMARY KEY,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    team_id        INTEGER NOT NULL REFERENCES teams(id),
    season         VARCHAR(10) NOT NULL,
    phase          VARCHAR(50) NOT NULL,
    bonus_points   INTEGER NOT NULL DEFAULT 0,
    weight         NUMERIC(4, 3) NOT NULL DEFAULT 1.0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_competition_achievement UNIQUE (competition_id, team_id, season, phase),
    CONSTRAINT ck_achievement_bonus_positive CHECK (bonus_points >= 0),
    CONSTRAINT ck_achievement_weight_range CHECK (weight > 0 AND weight <= 1.0)
);


-- ─── 3. player_achievement_bonuses ───────────────────────────────────────────

CREATE TABLE player_achievement_bonuses (
    id                   SERIAL PRIMARY KEY,
    player_id            INTEGER NOT NULL REFERENCES players(id),
    team_id              INTEGER NOT NULL REFERENCES teams(id),
    competition_id       INTEGER NOT NULL REFERENCES competitions(id),
    season               VARCHAR(10) NOT NULL,
    rules_version_id     INTEGER NOT NULL REFERENCES scoring_rules_versions(id),
    achievement_id       INTEGER NOT NULL REFERENCES competition_achievements(id) ON DELETE CASCADE,
    participation_ratio  NUMERIC(5, 4) NOT NULL,
    final_bonus          NUMERIC(10, 2) NOT NULL,
    calculation_details  JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_player_achievement_bonus UNIQUE (player_id, achievement_id, rules_version_id),
    CONSTRAINT ck_participation_ratio_range CHECK (participation_ratio BETWEEN 0 AND 1),
    CONSTRAINT ck_final_bonus_positive CHECK (final_bonus >= 0)
);

CREATE INDEX ix_pab_player_season ON player_achievement_bonuses (player_id, season, rules_version_id);
CREATE INDEX ix_pab_competition ON player_achievement_bonuses (competition_id, season, rules_version_id);


-- ─── 4. sfa_season_scores — add achievement_bonus_pts ────────────────────────

ALTER TABLE sfa_season_scores
    ADD COLUMN IF NOT EXISTS achievement_bonus_pts NUMERIC(12, 2) NOT NULL DEFAULT 0;

ALTER TABLE sfa_season_scores
    ADD CONSTRAINT ck_score_achievement_bonus_positive CHECK (achievement_bonus_pts >= 0);

-- Generated column sfa_total_pts = total_pts + achievement_bonus_pts
-- NOTE: PostgreSQL generated columns require the expression to reference only
-- stored columns. If your PG version supports it (12+):
ALTER TABLE sfa_season_scores
    ADD COLUMN IF NOT EXISTS sfa_total_pts NUMERIC(12, 2)
    GENERATED ALWAYS AS (total_pts + achievement_bonus_pts) STORED;


-- ─── 5. Update CHECK constraints in player_events for v2 value ranges ─────────
-- These constraints guard the legacy m1/m4/mvisit columns. v2 scores go into
-- player_event_scores (which has no such constraints), so we widen the guards
-- to accommodate both v1 and v2 ranges.

ALTER TABLE player_events DROP CONSTRAINT IF EXISTS ck_event_m1;
ALTER TABLE player_events ADD CONSTRAINT ck_event_m1
    CHECK (m1 BETWEEN 0.5 AND 2.0);   -- keep legacy range; v2 stores in player_event_scores

ALTER TABLE player_events DROP CONSTRAINT IF EXISTS ck_event_m4;
ALTER TABLE player_events ADD CONSTRAINT ck_event_m4
    CHECK (m4 BETWEEN 1.0 AND 2.0);   -- keep legacy range

ALTER TABLE player_events DROP CONSTRAINT IF EXISTS ck_event_mvisit;
ALTER TABLE player_events ADD CONSTRAINT ck_event_mvisit
    CHECK (mvisit IN (1.0, 1.3));     -- keep legacy values

COMMIT;
