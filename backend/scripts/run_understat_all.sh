#!/usr/bin/env bash
set -e

BASE="http://localhost:8000/api/v1/admin/enrich-understat"
SEASON="2024"
SEASON_INT="2024"

declare -A LEAGUES=(
    [3]="Premier League"
    [6]="Bundesliga"
    [7]="Serie A"
    [9]="Ligue 1"
)

for id in "${!LEAGUES[@]}"; do
    name="${LEAGUES[$id]}"
    encoded=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$name'))")
    echo "Triggering: $name (competition_id=$id)..."
    resp=$(curl -s -X POST "$BASE/$id?competition_name=$encoded&season=$SEASON&season_int=$SEASON_INT")
    echo "  Response: $resp"
done

echo ""
echo "All tasks submitted. Monitoring worker logs (ctrl+c to stop):"
docker logs backend-celery_worker-1 -f --tail=5
