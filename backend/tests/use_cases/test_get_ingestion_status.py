from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_ingestion_status import GetIngestionStatusUseCase
from sfa.application.use_cases.ingest_competition import LEAGUES
from sfa.domain.ingestion_ports import (
    FixtureInfoRow,
    IngestionLogRow,
    IngestionRepositoryPort,
)
from sfa.infrastructure.models.enums import IngestionStatus

from .test_ingest_stats_event import FakeIngestionRepository


class FakeIngestionStatusRepository(FakeIngestionRepository):
    def __init__(
        self,
        logs: list[IngestionLogRow] | None = None,
        fixture_counts: dict[int, int] | None = None,
    ) -> None:
        super().__init__()
        self._logs = logs or []
        self._fixture_counts = fixture_counts or {}

    async def get_last_ingestion_log(
        self, competition_id: int, season: str,
    ) -> IngestionLogRow | None:
        matches = [
            log for log in self._logs
            if log.competition_id == competition_id and log.season == season
        ]
        return max(matches, key=lambda log: log.started_at) if matches else None

    async def get_ingestion_logs_by_season(
        self, season: str,
    ) -> list[IngestionLogRow]:
        return sorted(
            (log for log in self._logs if log.season == season),
            key=lambda log: (log.competition_id, -log.started_at.timestamp()),
        )

    async def get_fixture_counts_by_competition(
        self, season: str,
    ) -> dict[int, int]:
        return self._fixture_counts

    async def get_season_fixtures(
        self, competition_id: int, season: str,
    ) -> list[FixtureInfoRow]:
        return []

    async def get_player_id_by_external(
        self, external_id: int,
    ) -> int | None:
        return None


def _log(
    league_index: int,
    status: IngestionStatus,
    error_msg: str | None = None,
) -> IngestionLogRow:
    league = LEAGUES[league_index]
    timestamp = datetime(2026, 6, 10, 12, league_index, tzinfo=timezone.utc)
    return IngestionLogRow(
        competition_id=league_index + 1,
        competition_name=league.name,
        season="2024",
        status=status,
        started_at=timestamp,
        finished_at=timestamp if status != IngestionStatus.RUNNING else None,
        error_msg=error_msg,
    )


class TestGetIngestionStatus:
    @pytest.mark.anyio
    async def test_all_leagues_completed(self):
        logs = [
            _log(index, IngestionStatus.COMPLETED)
            for index in range(len(LEAGUES))
        ]
        counts = {index + 1: 20 + index for index in range(len(LEAGUES))}

        result = await GetIngestionStatusUseCase(
            FakeIngestionStatusRepository(logs, counts)
        ).execute("2024")

        assert len(result) == len(LEAGUES)
        assert all(item.status == "COMPLETED" for item in result)
        assert all(item.fixtures_in_db > 0 for item in result)

    @pytest.mark.anyio
    async def test_failed_league_includes_error(self):
        error = "API quota exhausted"
        result = await GetIngestionStatusUseCase(
            FakeIngestionStatusRepository(
                [_log(0, IngestionStatus.FAILED, error)]
            )
        ).execute("2024")

        failed = next(item for item in result if item.league_id == LEAGUES[0].id)
        assert failed.status == "FAILED"
        assert failed.error_msg == error

    @pytest.mark.anyio
    async def test_missing_league_has_zero_fixtures(self):
        result = await GetIngestionStatusUseCase(
            FakeIngestionStatusRepository()
        ).execute("2024")

        assert result[0].status == "MISSING"
        assert result[0].fixtures_in_db == 0
        assert result[0].last_ingested_at is None

    @pytest.mark.anyio
    async def test_mixed_statuses_are_ordered_missing_first(self):
        result = await GetIngestionStatusUseCase(
            FakeIngestionStatusRepository(
                [
                    _log(0, IngestionStatus.COMPLETED),
                    _log(1, IngestionStatus.FAILED),
                ]
            )
        ).execute("2024")

        statuses = [item.status for item in result]
        assert statuses[0] == "MISSING"
        assert statuses.index("FAILED") < statuses.index("COMPLETED")

    @pytest.mark.anyio
    async def test_running_league_is_reported(self):
        result = await GetIngestionStatusUseCase(
            FakeIngestionStatusRepository(
                [_log(0, IngestionStatus.RUNNING)]
            )
        ).execute("2024")

        running = next(item for item in result if item.league_id == LEAGUES[0].id)
        assert running.status == "RUNNING"
        assert running.last_ingested_at is None

    def test_fake_implements_full_protocol(self):
        assert isinstance(FakeIngestionStatusRepository(), IngestionRepositoryPort)
