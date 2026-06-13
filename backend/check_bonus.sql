SELECT
  ROUND(final_bonus::numeric,0) AS bonus,
  calculation_details->>'team_total_minutes' AS team_total,
  calculation_details->>'participation_ratio' AS ratio,
  calculation_details->>'performance_factor' AS perf
FROM player_achievement_bonuses
WHERE rules_version_id=3 AND competition_id=3
ORDER BY final_bonus DESC LIMIT 5;
