from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.ingestion_ports import ScoringRepositoryPort

logger = logging.getLogger(__name__)

MIN_MINUTES_THRESHOLD = 90


@dataclass(frozen=True)
class CalculateScoresResult:
    competition_id: int
    season: str
    players_scored: int
    status: str
    error: str | None


class CalculateCompetitionScoresUseCase:
    def __init__(self, repo: ScoringRepositoryPort) -> None:
        self._repo = repo

    async def execute(self, competition_id: int, season: str) -> CalculateScoresResult:
        try:
            rows = await self._repo.get_player_scores_for_competition(competition_id, season)

            players_scored = 0
            for row in rows:
                if row.total_minutes < MIN_MINUTES_THRESHOLD:
                    continue

                breakdown = dict(row.breakdown)
                if row.total_pts > 0:
                    for key in breakdown:
                        pct = round(breakdown[key]["pts"] / row.total_pts * 100, 1)
                        breakdown[key] = {**breakdown[key], "pct": pct}

                await self._repo.upsert_season_score(
                    row.player_id, competition_id, season,
                    row.total_pts, row.matches_played, breakdown,
                )
                players_scored += 1

            logger.info(
                "[CalculateCompetitionScoresUseCase] competition_id=%s season=%s players_scored=%s",
                competition_id, season, players_scored,
            )
            return CalculateScoresResult(
                competition_id=competition_id,
                season=season,
                players_scored=players_scored,
                status="completed",
                error=None,
            )

        except Exception as exc:
            logger.exception(
                "[CalculateCompetitionScoresUseCase] Failed for competition_id=%s season=%s",
                competition_id, season,
            )
            return CalculateScoresResult(
                competition_id=competition_id,
                season=season,
                players_scored=0,
                status="failed",
                error=str(exc),
            )
