from datetime import datetime, timezone

import pytest

from sfa.tasks.reconcile_recent_ingestion_task import _reconcile_dates


def test_reconcile_dates_defaults_to_previous_three_utc_days() -> None:
    dates = _reconcile_dates(
        now_utc=datetime(2026, 8, 24, 4, tzinfo=timezone.utc),
        lookback_days=3,
        start_date=None,
        end_date=None,
    )

    assert dates == ["2026-08-21", "2026-08-22", "2026-08-23"]


def test_reconcile_dates_supports_explicit_incident_range() -> None:
    dates = _reconcile_dates(
        now_utc=datetime(2026, 8, 24, 4, tzinfo=timezone.utc),
        lookback_days=3,
        start_date="2026-08-20",
        end_date="2026-08-23",
    )

    assert dates == [
        "2026-08-20",
        "2026-08-21",
        "2026-08-22",
        "2026-08-23",
    ]


def test_reconcile_dates_rejects_partial_explicit_range() -> None:
    with pytest.raises(ValueError, match="provided together"):
        _reconcile_dates(
            now_utc=datetime(2026, 8, 24, 4, tzinfo=timezone.utc),
            lookback_days=3,
            start_date="2026-08-20",
            end_date=None,
        )
