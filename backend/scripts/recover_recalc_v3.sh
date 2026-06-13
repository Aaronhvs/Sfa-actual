#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose-development.yml"
SEASON="2024"
RULES_VERSION_ID=3

cd "$(dirname "$0")/.."

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

psql_value() {
  compose exec -T db psql -U sfa -d sfa -Atc "$1"
}

echo "[1/6] Starting database and API without Celery Beat..."
compose stop celery_beat celery_worker >/dev/null 2>&1 || true
compose up -d db redis api >/dev/null

for _ in $(seq 1 60); do
  if compose exec -T db pg_isready -U sfa -d sfa >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose exec -T db pg_isready -U sfa -d sfa >/dev/null

for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/v1/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS http://localhost:8000/api/v1/health >/dev/null

echo "[2/6] Reading current state..."
event_count="$(psql_value "SELECT count(1) FROM player_events;")"
score_count="$(psql_value "SELECT count(1) FROM player_event_scores WHERE rules_version_id = ${RULES_VERSION_ID};")"
echo "player_events=${event_count}"
echo "player_event_scores_v3=${score_count}"

if [[ "$score_count" != "$event_count" ]]; then
  echo "[3/6] Recalculating rules version ${RULES_VERSION_ID} synchronously..."
  compose exec -T api python3 -c \
    "import asyncio; from sfa.tasks.calculate_scores_for_rules_version_task import _run_calculate_scores_for_rules_version as run; asyncio.run(run(${RULES_VERSION_ID}, '${SEASON}', None, None, None, True))" \
    > /tmp/sfa-recalc-v3.log 2>&1
  tail -n 20 /tmp/sfa-recalc-v3.log
else
  echo "[3/6] Version ${RULES_VERSION_ID} already has one score per player event; skipping recalculation."
fi

echo "[4/6] Verifying recalculation commit..."
score_count="$(psql_value "SELECT count(1) FROM player_event_scores WHERE rules_version_id = ${RULES_VERSION_ID};")"
score_max="$(psql_value "SELECT COALESCE(max(created_at)::text, 'none') FROM player_event_scores WHERE rules_version_id = ${RULES_VERSION_ID};")"
echo "player_event_scores_v3=${score_count}"
echo "latest_score=${score_max}"

if [[ "$score_count" != "$event_count" ]]; then
  echo "ERROR: expected ${event_count} event scores, found ${score_count}" >&2
  exit 1
fi

echo "[5/6] Calculating achievement bonuses sequentially..."
competition_ids=(1 3 6 7 9 10 253 254 90 256 22 94 96 92)
for competition_id in "${competition_ids[@]}"; do
  echo "competition_id=${competition_id}"
  compose exec -T api python3 -c \
    "import asyncio; from sfa.tasks.calculate_achievement_bonuses_task import _run; asyncio.run(_run('${SEASON}', ${competition_id}, ${RULES_VERSION_ID}))" \
    > "/tmp/sfa-bonus-${competition_id}.log" 2>&1
  tail -n 2 "/tmp/sfa-bonus-${competition_id}.log"
done

bonus_count="$(psql_value "SELECT count(1) FROM player_achievement_bonuses WHERE rules_version_id = ${RULES_VERSION_ID} AND season = '${SEASON}';")"
echo "achievement_bonuses_v3=${bonus_count}"

echo "[6/6] Final top 20..."
compose exec -T db psql -U sfa -d sfa <<'SQL'
SELECT
  row_number() OVER (ORDER BY sum(s.total_pts + s.achievement_bonus_pts) DESC) AS rank,
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

echo "Recovery completed successfully."
