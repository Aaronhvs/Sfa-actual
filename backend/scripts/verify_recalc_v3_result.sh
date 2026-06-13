#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose-development.yml)

"${compose[@]}" up -d db >/dev/null
sleep 8

"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
SELECT
  (SELECT count(*) FROM player_events) AS player_events,
  (SELECT count(*) FROM player_event_scores WHERE rules_version_id = 3) AS scored_v3,
  (SELECT max(created_at) FROM player_event_scores WHERE rules_version_id = 3) AS latest_score,
  (
    SELECT count(*)
    FROM player_achievement_bonuses
    WHERE rules_version_id = 3 AND season = '2024'
  ) AS bonuses_v3,
  (
    SELECT max(created_at)
    FROM player_achievement_bonuses
    WHERE rules_version_id = 3 AND season = '2024'
  ) AS latest_bonus;

SELECT
  row_number() OVER (
    ORDER BY sum(s.total_pts + s.achievement_bonus_pts) DESC
  ) AS rank,
  p.name,
  p.position,
  t.name AS team,
  round(sum(s.total_pts + s.achievement_bonus_pts)) AS sfa_total
FROM sfa_season_scores s
JOIN players p ON p.id = s.player_id
JOIN teams t ON t.id = p.team_id
WHERE s.rules_version_id = 3
  AND s.season = '2024'
GROUP BY p.id, p.name, p.position, t.name
ORDER BY sfa_total DESC
LIMIT 10;
SQL
