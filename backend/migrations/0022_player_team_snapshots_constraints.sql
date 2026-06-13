-- Execute only after all five critical audit counters are zero.

ALTER TABLE player_stats
    ALTER COLUMN team_id SET NOT NULL;

ALTER TABLE player_events
    ALTER COLUMN team_id SET NOT NULL;
