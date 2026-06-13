#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose-development.yml)

"${compose[@]}" up -d db redis api >/dev/null
sleep 10

"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
\echo 'SEASON SCORE UPDATE RANGE'
SELECT
  count(*) AS rows,
  min(last_updated) AS oldest,
  max(last_updated) AS newest,
  count(*) FILTER (WHERE last_updated >= '2026-06-07 03:40:00+00') AS updated_in_latest_run
FROM sfa_season_scores
WHERE rules_version_id = 3
  AND season = '2024';

\echo 'TOP 10 WITH SCORE UPDATE TIME'
WITH totals AS (
  SELECT
    s.player_id,
    sum(s.total_pts) AS event_pts,
    sum(s.achievement_bonus_pts) AS bonus_pts,
    sum(s.total_pts + s.achievement_bonus_pts) AS total_pts,
    max(s.last_updated) AS last_updated
  FROM sfa_season_scores s
  WHERE s.rules_version_id = 3 AND s.season = '2024'
  GROUP BY s.player_id
)
SELECT
  row_number() OVER (ORDER BY totals.total_pts DESC) AS rank,
  p.id,
  p.name,
  round(totals.event_pts) AS event_pts,
  round(totals.bonus_pts) AS bonus_pts,
  round(totals.total_pts) AS total_pts,
  totals.last_updated
FROM totals
JOIN players p ON p.id = totals.player_id
ORDER BY totals.total_pts DESC
LIMIT 10;

\echo 'RULES VERSION 3 KEY CONFIG'
SELECT
  id,
  name,
  version,
  is_active,
  config_json->>'m1_stats_weight' AS m1_stats_weight,
  config_json->'m1_stats_clamp' AS m1_stats_clamp,
  config_json->>'enable_midfield_control_bonuses' AS midfield_bonuses,
  config_json->>'enable_performance_based_achievement_bonus' AS performance_bonuses,
  config_json->'base_points'->'MF'->>'passes_completed' AS mf_passes_points,
  config_json->'passes_avg_by_position'->>'MF' AS mf_passes_threshold
FROM scoring_rules_versions
WHERE id = 3;

\echo 'BRUNO SAMPLE STATS SCORES'
SELECT
  c.name AS competition,
  count(*) AS events,
  round(sum(pes.final_points)) AS points,
  round(avg((pes.calculation_details->>'m1_original')::numeric), 3) AS avg_m1_original,
  round(avg((pes.calculation_details->>'m1_stats_applied')::numeric), 3) AS avg_m1_stats,
  max(pes.created_at) AS latest_created
FROM player_event_scores pes
JOIN players p ON p.id = pes.player_id
JOIN competitions c ON c.id = pes.competition_id
WHERE pes.rules_version_id = 3
  AND pes.season = '2024'
  AND pes.action_type = 'stats'
  AND p.name = 'Bruno Fernandes'
GROUP BY c.name
ORDER BY c.name;
SQL

echo "API RANKING TOP 10"
curl -fsS 'http://localhost:8000/api/v1/ranking?season=2024&limit=10&rules_version_id=3&use_total=true'
echo
