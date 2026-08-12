from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.ingestion_ports import (
    FixtureScoreBackfillRepositoryPort,
    FixtureScoreBackfillTargetDTO,
    FixtureScoreProviderPort,
    FixtureScoreRawDTO,
)

logger = logging.getLogger(__name__)

FINAL_FIXTURE_STATUSES = {"FT", "AET", "PEN"}
SCORE_SOURCE = "api_football_backfill"


@dataclass(frozen=True)
class BackfillFixtureScoresResult:
    seasons: tuple[str, ...]
    dry_run: bool
    requested: int
    fetched: int
    validated: int
    updated: int
    missing_external_ids: tuple[int, ...]
    blockers: tuple[str, ...]
    status: str
    error: str | None


class BackfillFixtureScoresUseCase:
    def __init__(
        self,
        repository: FixtureScoreBackfillRepositoryPort,
        provider: FixtureScoreProviderPort,
    ) -> None:
        self._repository = repository
        self._provider = provider

    async def execute(
        self,
        seasons: list[str],
        dry_run: bool = True,
        batch_size: int = 20,
    ) -> BackfillFixtureScoresResult:
        normalized_seasons = tuple(dict.fromkeys(seasons))
        if not normalized_seasons:
            return self._failed(normalized_seasons, dry_run, "At least one season is required")
        if batch_size < 1 or batch_size > 20:
            return self._failed(
                normalized_seasons,
                dry_run,
                "batch_size must be between 1 and 20",
            )

        try:
            targets = await self._repository.get_missing_fixture_score_targets(
                list(normalized_seasons)
            )
            if not targets:
                return BackfillFixtureScoresResult(
                    seasons=normalized_seasons,
                    dry_run=dry_run,
                    requested=0,
                    fetched=0,
                    validated=0,
                    updated=0,
                    missing_external_ids=(),
                    blockers=(),
                    status="completed",
                    error=None,
                )

            target_by_external_id = {target.external_id: target for target in targets}
            if len(target_by_external_id) != len(targets):
                return self._failed(
                    normalized_seasons,
                    dry_run,
                    "Duplicate fixture external IDs found in backfill targets",
                    requested=len(targets),
                )

            fetched_by_external_id: dict[int, FixtureScoreRawDTO] = {}
            external_ids = sorted(target_by_external_id)
            for offset in range(0, len(external_ids), batch_size):
                batch = external_ids[offset:offset + batch_size]
                rows = await self._provider.fetch_fixture_scores(batch)
                for row in rows:
                    if row.external_id in fetched_by_external_id:
                        return self._failed(
                            normalized_seasons,
                            dry_run,
                            f"API returned duplicate fixture external_id={row.external_id}",
                            requested=len(targets),
                            fetched=len(fetched_by_external_id),
                        )
                    fetched_by_external_id[row.external_id] = row
                logger.info(
                    "[BackfillFixtureScoresUseCase] fetched=%d/%d",
                    min(offset + batch_size, len(external_ids)),
                    len(external_ids),
                )

            unexpected_ids = sorted(set(fetched_by_external_id) - set(target_by_external_id))
            missing_ids = tuple(
                sorted(set(target_by_external_id) - set(fetched_by_external_id))
            )
            blockers = [
                f"API returned unexpected fixture external_id={external_id}"
                for external_id in unexpected_ids
            ]
            valid_rows: list[tuple[int, FixtureScoreRawDTO]] = []

            for external_id in external_ids:
                target = target_by_external_id[external_id]
                row = fetched_by_external_id.get(external_id)
                if row is None:
                    continue
                row_blockers = self._validate_row(target, row)
                if row_blockers:
                    blockers.extend(row_blockers)
                else:
                    valid_rows.append((target.fixture_id, row))

            if missing_ids:
                blockers.append(
                    f"API did not return {len(missing_ids)} requested fixtures"
                )
            if blockers:
                return BackfillFixtureScoresResult(
                    seasons=normalized_seasons,
                    dry_run=dry_run,
                    requested=len(targets),
                    fetched=len(fetched_by_external_id),
                    validated=len(valid_rows),
                    updated=0,
                    missing_external_ids=missing_ids,
                    blockers=tuple(blockers),
                    status="failed",
                    error="Fixture score backfill validation failed",
                )

            if not dry_run:
                for fixture_id, row in valid_rows:
                    await self._repository.update_fixture_score(
                        fixture_id=fixture_id,
                        status=row.status,
                        home_goals=int(row.home_goals),
                        away_goals=int(row.away_goals),
                        score_source=SCORE_SOURCE,
                    )

            return BackfillFixtureScoresResult(
                seasons=normalized_seasons,
                dry_run=dry_run,
                requested=len(targets),
                fetched=len(fetched_by_external_id),
                validated=len(valid_rows),
                updated=0 if dry_run else len(valid_rows),
                missing_external_ids=(),
                blockers=(),
                status="completed",
                error=None,
            )
        except Exception as exc:
            logger.exception("[BackfillFixtureScoresUseCase] failed")
            return self._failed(normalized_seasons, dry_run, str(exc))

    @staticmethod
    def _validate_row(
        target: FixtureScoreBackfillTargetDTO,
        row: FixtureScoreRawDTO,
    ) -> list[str]:
        prefix = f"fixture external_id={target.external_id}"
        blockers: list[str] = []
        if target.home_team_external_id is None or target.away_team_external_id is None:
            blockers.append(f"{prefix}: local team external ID is missing")
            return blockers
        if row.home_team_external_id != target.home_team_external_id:
            blockers.append(f"{prefix}: home team does not match API response")
        if row.away_team_external_id != target.away_team_external_id:
            blockers.append(f"{prefix}: away team does not match API response")
        if row.status not in FINAL_FIXTURE_STATUSES:
            blockers.append(f"{prefix}: API status {row.status!r} is not final")
        if row.home_goals is None or row.away_goals is None:
            blockers.append(f"{prefix}: API response has a null score")
        elif row.home_goals < 0 or row.away_goals < 0:
            blockers.append(f"{prefix}: API response has a negative score")
        else:
            reference_score = BackfillFixtureScoresUseCase._reference_score(row)
            if reference_score is not None and reference_score != (
                row.home_goals,
                row.away_goals,
            ):
                blockers.append(
                    f"{prefix}: goals do not match the API score breakdown"
                )
            if row.status == "PEN":
                if row.home_goals != row.away_goals:
                    blockers.append(
                        f"{prefix}: PEN fixture goals include a non-drawn score"
                    )
                if (
                    row.shootout_home_goals is None
                    or row.shootout_away_goals is None
                    or row.shootout_home_goals == row.shootout_away_goals
                ):
                    blockers.append(
                        f"{prefix}: PEN fixture has an invalid shootout breakdown"
                    )
        return blockers

    @staticmethod
    def _reference_score(row: FixtureScoreRawDTO) -> tuple[int, int] | None:
        if row.status in {"AET", "PEN"} and (
            row.extratime_home_goals is not None
            and row.extratime_away_goals is not None
        ):
            return row.extratime_home_goals, row.extratime_away_goals
        if (
            row.fulltime_home_goals is not None
            and row.fulltime_away_goals is not None
        ):
            return row.fulltime_home_goals, row.fulltime_away_goals
        return None

    @staticmethod
    def _failed(
        seasons: tuple[str, ...],
        dry_run: bool,
        error: str,
        requested: int = 0,
        fetched: int = 0,
    ) -> BackfillFixtureScoresResult:
        return BackfillFixtureScoresResult(
            seasons=seasons,
            dry_run=dry_run,
            requested=requested,
            fetched=fetched,
            validated=0,
            updated=0,
            missing_external_ids=(),
            blockers=(error,),
            status="failed",
            error=error,
        )
