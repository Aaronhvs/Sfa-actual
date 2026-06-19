from celery import Celery
from celery.schedules import crontab, timedelta

from sfa.core.config import get_settings

settings = get_settings()

celery_app = Celery("sfa", broker=settings.CELERY_BROKER_URL)

celery_app.autodiscover_tasks(["sfa.tasks"])

celery_app.conf.timezone = "UTC"

ingest_interval_minutes = max(1, settings.INGEST_INTERVAL_MINUTES)

# Runs every INGEST_INTERVAL_MINUTES.
# Checks API-Football for today's fixtures (1 API call).
# Only ingests competitions with live or recently finished matches (within 4 hours).
# If nothing is active, exits immediately at zero extra cost.
celery_app.conf.beat_schedule = {
    # Checks if there are live or recently finished matches to ingest.
    # Only ingests competitions listed in ACTIVE_COMPETITIONS (ingest_today_task.py).
    "ingest-today-competitions": {
        "task": "sfa.tasks.ingest_today_task.ingest_today_task",
        "schedule": timedelta(minutes=ingest_interval_minutes),
    },
    # Runs once a day at 3 AM UTC to fix player positions via Transfermarkt.
    # Important during active competitions where new players appear daily.
    # season="2026" targets World Cup players — update when active season changes.
    "enrich-player-positions-daily": {
        "task": "enrich_player_positions_task",
        "schedule": crontab(hour=3, minute=0),
        "kwargs": {"batch_size": 500, "season": "2026"},
    },
}
