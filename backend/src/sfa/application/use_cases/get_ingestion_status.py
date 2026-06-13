from __future__ import annotations

from sfa.application.use_cases.ingest_competition import LEAGUES
from sfa.domain.ingestion_ports import (
    CompetitionIngestionStatusDTO,
    IngestionRepositoryPort,
)

_STATUS_ORDER = {
    "MISSING": 0,
    "FAILED": 1,
    "RUNNING": 2,
    "COMPLETED": 3,
}


class GetIngestionStatusUseCase:
    def __init__(self, repo: IngestionRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, season: str) -> list[CompetitionIngestionStatusDTO]:
        logs = await self._repo.get_ingestion_logs_by_season(season)
        fixture_counts = await self._repo.get_fixture_counts_by_competition(season)

        latest_by_name = {}
        for log in logs:
            latest_by_name.setdefault(log.competition_name, log)

        statuses = []
        for league in LEAGUES:
            log = latest_by_name.get(league.name)
            if log is None:
                statuses.append(
                    CompetitionIngestionStatusDTO(
                        competition_name=league.name,
                        league_id=league.id,
                        season=season,
                        status="MISSING",
                        fixtures_in_db=0,
                        last_ingested_at=None,
                        error_msg=None,
                    )
                )
                continue

            statuses.append(
                CompetitionIngestionStatusDTO(
                    competition_name=league.name,
                    league_id=league.id,
                    season=season,
                    status=log.status.value.upper(),
                    fixtures_in_db=fixture_counts.get(log.competition_id, 0),
                    last_ingested_at=log.finished_at,
                    error_msg=log.error_msg,
                )
            )

        return sorted(
            statuses,
            key=lambda item: (
                _STATUS_ORDER.get(item.status, len(_STATUS_ORDER)),
                item.competition_name,
            ),
        )
