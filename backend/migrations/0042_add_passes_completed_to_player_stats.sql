ALTER TABLE player_stats
  ADD COLUMN IF NOT EXISTS passes_completed SMALLINT NOT NULL DEFAULT 0;

UPDATE player_stats
SET passes_completed = CASE
  WHEN passes_accuracy <= passes_total THEN passes_accuracy
  ELSE ROUND(passes_total * passes_accuracy / 100.0)::INTEGER
END
WHERE passes_completed = 0
  AND passes_total > 0
  AND passes_accuracy > 0;

UPDATE player_stats
SET passes_accuracy = CASE
  WHEN passes_total > 0 THEN ROUND(passes_completed * 100.0 / passes_total)::INTEGER
  ELSE 0
END;

ALTER TABLE player_stats
  DROP CONSTRAINT IF EXISTS ck_ps_passes_accuracy;

ALTER TABLE player_stats
  ADD CONSTRAINT ck_ps_passes_accuracy CHECK (passes_accuracy BETWEEN 0 AND 100);

ALTER TABLE player_stats
  ADD CONSTRAINT ck_ps_passes_completed CHECK (passes_completed >= 0);
