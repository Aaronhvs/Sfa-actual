UPDATE scoring_rules_versions
SET config_json = jsonb_set(
  jsonb_set(
    config_json,
    '{achievement_phase_bonuses,world_cup,fourth_place}',
    '5000'::jsonb,
    true
  ),
  '{achievement_phase_bonuses,world_cup,winner}',
  '9000'::jsonb,
  true
)
WHERE id = 4;
