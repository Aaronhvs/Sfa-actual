-- Run outside a transaction. This lookup supports per-player conservation
-- checks without rescanning all event scores in the season for every rollup.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pes_player_context
ON player_event_scores(player_id,competition_id,season,rules_version_id)
INCLUDE(final_points,fixture_id,action_type);
