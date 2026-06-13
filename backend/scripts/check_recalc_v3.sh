#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose -f docker-compose-development.yml)

echo "PROCESSES"
ps aux | grep -E 'recover_recalc_v3|calculate_scores_for_rules_version|python3' | grep -v grep || true

echo "TRANSACTIONS"
"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
SELECT pid, state, now() - xact_start AS duration, left(query, 100) AS query
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid()
  AND xact_start IS NOT NULL
ORDER BY xact_start;
SQL

echo "COUNTS"
"${compose[@]}" exec -T db psql -U sfa -d sfa <<'SQL'
SELECT
  (SELECT count(*) FROM player_events) AS player_events,
  (SELECT count(*) FROM player_event_scores WHERE rules_version_id = 3) AS scored_v3,
  (SELECT max(created_at) FROM player_event_scores WHERE rules_version_id = 3) AS latest_score,
  (SELECT count(*) FROM player_achievement_bonuses WHERE rules_version_id = 3) AS bonuses_v3;
SQL

echo "LOG"
if [[ -f /tmp/sfa-recalc-v3.log ]]; then
  stat -c '%y %s' /tmp/sfa-recalc-v3.log
  tail -n 5 /tmp/sfa-recalc-v3.log
else
  echo "no-recalc-log"
fi
