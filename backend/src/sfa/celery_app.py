from celery import Celery
from celery.schedules import timedelta

from sfa.core.config import get_settings

settings = get_settings()

celery_app = Celery("sfa", broker=settings.CELERY_BROKER_URL)

celery_app.autodiscover_tasks(["sfa.tasks"])

celery_app.conf.timezone = "UTC"

# Runs every 30 minutes.
# Checks API-Football for today's fixtures (1 API call).
# Only ingests competitions with live or recently finished matches (within 4 hours).
# If nothing is active, exits immediately at zero extra cost.
celery_app.conf.beat_schedule = {
    "ingest-today-competitions": {
        "task": "sfa.tasks.ingest_today_task.ingest_today_task",
        "schedule": timedelta(minutes=30),
    },
}
