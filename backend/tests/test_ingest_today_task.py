from datetime import datetime, timezone

import pytest

from sfa.domain.ingestion_ports import ProviderDailyQuotaExceededError
from sfa.infrastructure.providers import api_football
from sfa.tasks import ingestion_tasks
from sfa.tasks.ingest_today_task import (
    ACTIVE_COMPETITIONS,
    _collect_relevant_fixtures,
    _dates_to_check,
    _run_ingest_dates,
)


def _fixture(fixture_id: int, league_id: int, season: int, status: str) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": datetime.now(timezone.utc).isoformat(),
            "status": {"short": status},
        },
        "league": {"id": league_id, "season": season},
    }


def test_current_club_competitions_replace_world_cup():
    assert (531, 2026) in ACTIVE_COMPETITIONS
    assert (528, 2026) in ACTIVE_COMPETITIONS
    assert (39, 2026) in ACTIVE_COMPETITIONS
    assert (2, 2026) in ACTIVE_COMPETITIONS
    assert (1, 2026) not in ACTIVE_COMPETITIONS


def test_collects_only_live_or_recent_current_season_fixture_ids():
    selected = _collect_relevant_fixtures(
        [
            _fixture(10, 39, 2026, "1H"),
            _fixture(11, 39, 2026, "NS"),
            _fixture(12, 1, 2026, "FT"),
            _fixture(13, 39, 2025, "FT"),
        ],
        {1, 39},
    )

    assert selected == {(39, 2026): {10}}


def test_checks_yesterday_only_near_utc_midnight():
    assert _dates_to_check(
        datetime(2026, 8, 17, 2, tzinfo=timezone.utc),
    ) == ["2026-08-16", "2026-08-17"]
    assert _dates_to_check(
        datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
    ) == ["2026-08-17"]


def test_reconciliation_collects_finished_fixture_outside_live_window():
    old_finished = _fixture(21, 39, 2026, "FT")
    old_finished["fixture"]["date"] = "2026-08-20T12:00:00+00:00"

    assert _collect_relevant_fixtures(
        [old_finished],
        {39},
        include_all_finished=True,
    ) == {(39, 2026): {21}}


class FakeProvider:
    fixtures: list[dict] = []

    def __init__(self, api_key: str, base_url: str) -> None:
        self.closed = False

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        return {"response": list(self.fixtures)}

    async def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_batch_ingests_two_competitions_and_queues_one_recalculation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeProvider.fixtures = [
        _fixture(31, 39, 2026, "FT"),
        _fixture(32, 140, 2026, "FT"),
    ]
    ingestion_calls: list[tuple[int, bool]] = []
    recalculation_calls: list[list[str]] = []

    async def fake_ingest(
        league_id: int,
        season: int,
        force: bool,
        fixture_external_ids: list[int],
        enqueue_recalculation: bool,
    ) -> dict:
        ingestion_calls.append((league_id, enqueue_recalculation))
        return {"status": "completed", "league_id": league_id}

    async def fake_recalculate(season, leagues, force_recalculate=False) -> bool:
        recalculation_calls.append([league.name for league in leagues])
        assert force_recalculate is False
        return True

    monkeypatch.setattr(api_football, "APIFootballProvider", FakeProvider)
    monkeypatch.setattr(ingestion_tasks, "_run_ingest_competition", fake_ingest)
    monkeypatch.setattr(
        ingestion_tasks,
        "_trigger_recalculation_for_leagues",
        fake_recalculate,
    )

    result = await _run_ingest_dates(
        ["2026-08-23"],
        include_all_finished=True,
        cycle_name="test",
    )

    assert ingestion_calls == [(39, False), (140, False)]
    assert recalculation_calls == [["Premier League", "La Liga"]]
    assert result["recalculation_queued"] is True


@pytest.mark.anyio
async def test_batch_stops_on_daily_quota_and_recalculates_completed_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeProvider.fixtures = [
        _fixture(41, 39, 2026, "FT"),
        _fixture(42, 140, 2026, "FT"),
    ]
    recalculation_calls: list[list[str]] = []

    async def fake_ingest(
        league_id: int,
        season: int,
        force: bool,
        fixture_external_ids: list[int],
        enqueue_recalculation: bool,
    ) -> dict:
        if league_id == 140:
            raise ProviderDailyQuotaExceededError("daily quota")
        return {"status": "completed", "league_id": league_id}

    async def fake_recalculate(season, leagues, force_recalculate=False) -> bool:
        recalculation_calls.append([league.name for league in leagues])
        return True

    monkeypatch.setattr(api_football, "APIFootballProvider", FakeProvider)
    monkeypatch.setattr(ingestion_tasks, "_run_ingest_competition", fake_ingest)
    monkeypatch.setattr(
        ingestion_tasks,
        "_trigger_recalculation_for_leagues",
        fake_recalculate,
    )

    result = await _run_ingest_dates(
        ["2026-08-23"],
        include_all_finished=True,
        cycle_name="test",
    )

    assert result["status"] == "quota_exhausted"
    assert recalculation_calls == [["Premier League"]]
