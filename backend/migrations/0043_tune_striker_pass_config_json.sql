UPDATE scoring_rules_versions
SET config_json = jsonb_set(
  jsonb_set(
    config_json,
    '{base_points,DEL,passes_completed}',
    '3'::jsonb,
    true
  ),
  '{passes_avg_by_position,DEL}',
  '10'::jsonb,
  true
)
WHERE id = 4;
