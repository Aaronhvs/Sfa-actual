CREATE TABLE IF NOT EXISTS ranking_player_explanations (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    season VARCHAR(10) NOT NULL,
    competition_id INTEGER NULL REFERENCES competitions(id) ON DELETE CASCADE,
    rules_version_id INTEGER NULL REFERENCES scoring_rules_versions(id) ON DELETE SET NULL,
    scope VARCHAR(30) NOT NULL,
    rank INTEGER NOT NULL,
    variant VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    short_text TEXT NOT NULL,
    long_text TEXT NOT NULL,
    bullets JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_json JSONB NOT NULL,
    model_name VARCHAR(80) NULL,
    prompt_version VARCHAR(30) NOT NULL,
    input_tokens INTEGER NULL,
    output_tokens INTEGER NULL,
    cost_estimate_usd NUMERIC(10, 6) NULL,
    source_hash VARCHAR(64) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NULL,
    error TEXT NULL,
    CONSTRAINT ck_ranking_explanations_rank_positive CHECK (rank > 0),
    CONSTRAINT ck_ranking_explanations_status CHECK (status IN ('generated', 'fallback', 'failed', 'stale')),
    CONSTRAINT ck_ranking_explanations_variant CHECK (variant IN ('ai', 'deterministic')),
    CONSTRAINT ck_ranking_explanations_short_len CHECK (char_length(short_text) <= 280),
    CONSTRAINT ck_ranking_explanations_long_len CHECK (char_length(long_text) <= 1800)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ranking_player_expl_comp
    ON ranking_player_explanations (player_id, season, competition_id, rules_version_id, scope)
    WHERE competition_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ranking_player_expl_global
    ON ranking_player_explanations (player_id, season, rules_version_id, scope)
    WHERE competition_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_ranking_player_expl_scope_rank
    ON ranking_player_explanations (season, competition_id, rules_version_id, scope, rank);

CREATE INDEX IF NOT EXISTS ix_ranking_player_expl_player_scope
    ON ranking_player_explanations (player_id, season, rules_version_id, scope);

CREATE INDEX IF NOT EXISTS ix_ranking_player_expl_status
    ON ranking_player_explanations (status);
