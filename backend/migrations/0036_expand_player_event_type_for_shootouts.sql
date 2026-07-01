-- Allow longer event type names such as MISSED_SHOOTOUT_DECISIVE.
ALTER TABLE player_events
  ALTER COLUMN event_type TYPE VARCHAR(32);
