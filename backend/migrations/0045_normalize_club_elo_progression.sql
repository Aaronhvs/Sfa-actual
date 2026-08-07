-- 0045 - Normalize club ELO progression with an auditable progressive source.
--
-- The application now replays club fixtures from elo_seed_raw and stores the
-- resulting rating as club_elo_v2. Existing elo_v1 rows remain readable so the
-- migration is backward compatible during rollout.

ALTER TABLE team_strengths DROP CONSTRAINT IF EXISTS ck_team_strength_source;

ALTER TABLE team_strengths
    ADD CONSTRAINT ck_team_strength_source CHECK (
        source IN (
            'calculated',
            'default',
            'override',
            'clubelo_seed',
            'elo_v1',
            'club_elo_v2',
            'national_elo_seed',
            'national_elo_v1'
        )
    );
