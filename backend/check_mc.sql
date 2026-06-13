SELECT
  pl.name,
  ROUND(pes.final_points::numeric, 2) AS final_pts,
  pes.calculation_details->'midfield_bonuses'->>'enabled' AS mb_enabled,
  ROUND((pes.calculation_details->'midfield_bonuses'->>'mc_bonus_final')::numeric, 2) AS mc_bonus,
  pes.calculation_details->'midfield_bonuses'->>'control_midfield_bonus_earned' AS control,
  pes.calculation_details->'midfield_bonuses'->>'creative_control_bonus_earned' AS creative,
  pes.calculation_details->'midfield_bonuses'->>'two_way_midfield_bonus_earned' AS two_way
FROM player_event_scores pes
JOIN players pl ON pl.id = pes.player_id
WHERE pes.rules_version_id = 3
  AND pes.action_type = 'stats'
  AND (pes.calculation_details->'midfield_bonuses'->>'mc_bonus_final') IS NOT NULL
  AND (pes.calculation_details->'midfield_bonuses'->>'mc_bonus_final')::float > 0
ORDER BY (pes.calculation_details->'midfield_bonuses'->>'mc_bonus_final')::float DESC
LIMIT 10;
