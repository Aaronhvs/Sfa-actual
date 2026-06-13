from celery import Celery

from sfa.core.config import get_settings

settings = get_settings()

celery_app = Celery("sfa", broker=settings.CELERY_BROKER_URL)

celery_app.autodiscover_tasks(["sfa.tasks"])

BEAT_SCHEDULE_DISABLED: bool = True
# INTENTIONALLY EMPTY — no scheduled tasks. All ingestion triggered via admin API only.
celery_app.conf.beat_schedule = {}

celery_app.conf.timezone = "UTC"
