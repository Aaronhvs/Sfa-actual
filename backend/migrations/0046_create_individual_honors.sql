CREATE TABLE IF NOT EXISTS individual_honors (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    scope_key VARCHAR(80) NOT NULL,
    scope_label VARCHAR(100) NOT NULL,
    context_key VARCHAR(100) NOT NULL,
    context_label VARCHAR(100) NOT NULL,
    scope_category VARCHAR(40) NOT NULL,
    honor_type VARCHAR(40) NOT NULL,
    source_season VARCHAR(10) NOT NULL,
    competition_id INTEGER NULL REFERENCES competitions(id),
    rules_version_id INTEGER NOT NULL REFERENCES scoring_rules_versions(id),
    metric_value NUMERIC(12, 4) NOT NULL,
    metric_total INTEGER NULL,
    metric_rate NUMERIC(7, 6) NULL,
    raw_bonus_pts INTEGER NOT NULL,
    awarded_bonus_pts INTEGER NOT NULL,
    calculation_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_individual_honor_metric_value CHECK (metric_value >= 0),
    CONSTRAINT ck_individual_honor_metric_total CHECK (metric_total IS NULL OR metric_total >= 0),
    CONSTRAINT ck_individual_honor_metric_rate CHECK (
        metric_rate IS NULL OR (metric_rate >= 0 AND metric_rate <= 1)
    ),
    CONSTRAINT ck_individual_honor_raw_bonus CHECK (raw_bonus_pts >= 0),
    CONSTRAINT ck_individual_honor_awarded_bonus CHECK (
        awarded_bonus_pts >= 0 AND awarded_bonus_pts <= raw_bonus_pts
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_individual_honor_context
    ON individual_honors(scope_key, context_key, honor_type, rules_version_id);

CREATE INDEX IF NOT EXISTS ix_individual_honors_player_scope
    ON individual_honors(player_id, scope_key);
