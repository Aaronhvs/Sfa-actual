#!/usr/bin/env bash
TARGET=5
while true; do
    COUNT=$(docker logs backend-celery_worker-1 2>&1 | grep -c "enrich_understat_task.*succeeded" || true)
    echo "$COUNT/$TARGET tasks done..."
    if [ "$COUNT" -ge "$TARGET" ]; then
        break
    fi
    sleep 15
done
echo "=== ALL DONE ==="
echo ""
echo "RecalculateScores summary:"
docker logs backend-celery_worker-1 2>&1 | grep "RecalculateScores:"
echo ""
echo "Succeeded tasks:"
docker logs backend-celery_worker-1 2>&1 | grep "enrich_understat_task.*succeeded"
