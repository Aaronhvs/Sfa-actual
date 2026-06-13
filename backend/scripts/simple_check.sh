#!/usr/bin/env bash
echo "docker test"
docker ps | grep celery
echo "---"
docker logs backend-celery_worker-1 2>&1 | wc -l
echo "---"
docker logs backend-celery_worker-1 2>&1 | grep "succeeded" | wc -l
echo "---"
docker logs backend-celery_worker-1 2>&1 | grep "RecalculateScores:" | tail -3
echo "---"
docker logs backend-celery_worker-1 2>&1 | tail -3
