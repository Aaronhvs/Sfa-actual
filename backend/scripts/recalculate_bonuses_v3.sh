#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose-development.yml)

"${compose[@]}" stop celery_beat celery_worker >/dev/null 2>&1 || true
"${compose[@]}" up -d db redis api >/dev/null

for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:8000/api/v1/health >/dev/null

competition_ids=(1 3 6 7 9 10 253 254 90 256 22 94 96 92)
for competition_id in "${competition_ids[@]}"; do
  echo "Calculating bonuses for competition_id=${competition_id}"
  "${compose[@]}" exec -T api python3 -c \
    "import asyncio; from sfa.tasks.calculate_achievement_bonuses_task import _run; asyncio.run(_run('2024', ${competition_id}, 3))"
done

"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
SELECT
  count(*) AS bonuses_v3,
  max(created_at) AS latest_bonus
FROM player_achievement_bonuses
WHERE rules_version_id = 3
  AND season = '2024';
SQL

"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
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
LIMIT 20;
SQL
