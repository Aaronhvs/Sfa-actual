#!/usr/bin/env bash
echo "=== Failed tasks ==="
docker logs backend-celery_worker-1 2>&1 | grep "failed" | tail -5

echo ""
echo "=== All enrich_understat_task lines ==="
docker logs backend-celery_worker-1 2>&1 | grep "enrich_understat_task\[" | tail -20

echo ""
echo "=== HTTP requests to understat (recent) ==="
docker logs backend-celery_worker-1 2>&1 | grep "understat.com" | tail -10

echo ""
echo "=== RecalculateScores from today ==="
docker logs backend-celery_worker-1 2>&1 | grep "RecalculateScores:" | grep "2026-05-24" | tail -10

echo ""
echo "=== Docker container status ==="
docker ps -a | grep celery
