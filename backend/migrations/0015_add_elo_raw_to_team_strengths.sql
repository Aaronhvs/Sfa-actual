-- Migration 0015: Add raw ELO support to team_strengths
-- Applies: 2026-06-07
-- Spec: specs/feature/0017-elo-team-ratings/

BEGIN;

ALTER TABLE team_strengths
    ADD COLUMN elo_raw NUMERIC(7, 2) NULL;

ALTER TABLE team_strengths
    DROP CONSTRAINT ck_team_strength_source;

ALTER TABLE team_strengths
    ADD CONSTRAINT ck_team_strength_source
    CHECK (source IN ('calculated', 'default', 'override', 'clubelo_seed', 'elo_v1'));

COMMIT;
