#!/usr/bin/env bash
echo "=== Checking celery worker logs ==="
COUNT=$(docker logs backend-celery_worker-1 2>&1 | grep -c "succeeded")
echo "Lines with 'succeeded': $COUNT"

echo ""
echo "=== Lines with 'enrich_understat_task' ==="
docker logs backend-celery_worker-1 2>&1 | grep "enrich_understat_task" | grep -v "^$"

echo ""
echo "=== Last 5 RecalculateScores lines ==="
docker logs backend-celery_worker-1 2>&1 | grep "RecalculateScores:" | tail -5

echo ""
echo "=== Last 10 lines of worker logs ==="
docker logs backend-celery_worker-1 2>&1 | tail -10

echo ""
echo "=== Container status ==="
docker ps --filter "name=backend-celery_worker-1" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
