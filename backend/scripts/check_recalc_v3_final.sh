#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose-development.yml)

"${compose[@]}" up -d db >/dev/null
sleep 10

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
SQL

echo
echo "RECALC LOG END"
tail -n 15 /tmp/sfa-recalc-v3.log 2>/dev/null || true

echo
echo "BONUS LOGS"
found=0
for file in /tmp/sfa-bonus-*.log; do
  [[ -f "$file" ]] || continue
  found=1
  printf '%s: ' "$(basename "$file")"
  tail -n 1 "$file"
done
[[ "$found" -eq 1 ]] || echo "none"
