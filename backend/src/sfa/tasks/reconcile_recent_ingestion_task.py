from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from sfa.celery_app import celery_app
from sfa.domain.ingestion_ports import ProviderDailyQuotaExceededError

logger = logging.getLogger(__name__)


def _reconcile_dates(
    *,
    now_utc: datetime,
    lookback_days: int,
    start_date: str | None,
    end_date: str | None,
) -> list[str]:
    if (start_date is None) != (end_date is None):
        raise ValueError("start_date and end_date must be provided together")

    if start_date is not None and end_date is not None:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        if (end - start).days > 14:
            raise ValueError("reconciliation range cannot exceed 15 days")
        return [
            (start + timedelta(days=offset)).isoformat()
            for offset in range((end - start).days + 1)
        ]

    if lookback_days < 1 or lookback_days > 7:
        raise ValueError("lookback_days must be between 1 and 7")
    return [
        (now_utc.date() - timedelta(days=offset)).isoformat()
        for offset in range(lookback_days, 0, -1)
    ]


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def reconcile_recent_ingestion_task(
    self,
    lookback_days: int = 3,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Reingest a bounded UTC date window and queue one ELO/scoring replay."""
    try:
        return asyncio.run(
            _run_reconcile_recent_ingestion(
                lookback_days=lookback_days,
                start_date=start_date,
                end_date=end_date,
            )
        )
    except ProviderDailyQuotaExceededError as exc:
        logger.warning(
            "[reconcile_recent_ingestion_task] Daily provider quota exhausted: %s",
            exc,
        )
        return {"status": "quota_exhausted", "error": str(exc)}
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_reconcile_recent_ingestion(
    *,
    lookback_days: int,
    start_date: str | None,
    end_date: str | None,
) -> dict:
    from sfa.tasks.ingest_today_task import (
        _run_ingest_dates,
        _run_with_ingestion_lock,
    )

    dates = _reconcile_dates(
        now_utc=datetime.now(timezone.utc),
        lookback_days=lookback_days,
        start_date=start_date,
        end_date=end_date,
    )
    return await _run_with_ingestion_lock(
        "reconcile",
        lambda: _run_ingest_dates(
            dates,
            include_all_finished=True,
            cycle_name="reconcile",
        ),
    )
