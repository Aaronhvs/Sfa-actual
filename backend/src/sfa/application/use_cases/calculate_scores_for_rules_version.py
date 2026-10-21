from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring.event_engine import (
    _MC_BONUS_CONTROL,
    _MC_BONUS_CREATIVE,
    _MC_BONUS_TWO_WAY,
    MIN_MINUTES_FOR_RANKING,
    WORLD_CUP_COMPETITION_ID,
    EventScoringEngine,
    _build_b1_contributions_map,
    _pass_accuracy_bonus_base,
)
from sfa.domain.scoring.services import SFAScoringService
from sfa.domain.scoring_ports import PlayerEventScoreRepositoryPort, ScoringRulesVersionRepositoryPort

__all__ = [
    "CalculateScoresForRulesVersionUseCase", "CalculateScoresForRulesVersionResult",
    "MIN_MINUTES_FOR_RANKING", "WORLD_CUP_COMPETITION_ID", "_build_b1_contributions_map",
    "_MC_BONUS_CONTROL", "_MC_BONUS_CREATIVE", "_MC_BONUS_TWO_WAY", "_pass_accuracy_bonus_base",
]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalculateScoresForRulesVersionResult:
    rules_version_id: int
    season: str
    competition_id: int | None
    events_calculated: int
    players_updated: int
    status: str
    error: str | None


class CalculateScoresForRulesVersionUseCase(EventScoringEngine):
    def __init__(
        self,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
        event_score_repo: PlayerEventScoreRepositoryPort,
    ) -> None:
        self._rules_version_repo = rules_version_repo
        self._event_score_repo = event_score_repo

    async def execute(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None = None,
        match_id: int | None = None,
        player_id: int | None = None,
        force_recalculate: bool = False,
    ) -> CalculateScoresForRulesVersionResult:
        season = str(season)
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            return CalculateScoresForRulesVersionResult(
                rules_version_id=rules_version_id, season=season,
                competition_id=competition_id, events_calculated=0, players_updated=0,
                status="failed", error=f"ScoringRulesVersion id={rules_version_id} not found",
            )

        service = SFAScoringService(config=rules_version.config)
        events = await self._event_score_repo.get_events_for_recalc(
            season=season,
            competition_id=competition_id,
            match_id=match_id,
            player_id=player_id,
        )

        # Preload competition name map for midfield bonus competition_weight lookup
        competition_name_map: dict[int, str] = {}
        if rules_version.config.enable_midfield_control_bonuses:
            competition_name_map = await self._event_score_repo.get_competition_name_map()

        # Preload B1 contributions map: (player_id, fixture_id) -> total goal+assist count
        b1_contributions_map: dict[tuple[int, int], int] = {}
        if rules_version.config.b1_enabled:
            b1_contributions_map = _build_b1_contributions_map(events)

        events_calculated = 0

        for event in events:
            if not force_recalculate:
                if await self._event_score_repo.event_score_exists(event.event_id, rules_version_id):
                    continue

            score = self._score_event(
                event, service, rules_version_id, competition_name_map, b1_contributions_map,
            )
            if score is None:
                continue

            await self._event_score_repo.upsert_event_score(score)
            events_calculated += 1

        players_updated = await self._event_score_repo.bulk_rebuild_season_scores(
            rules_version_id=rules_version_id,
            season=season,
            competition_id=competition_id,
        )

        logger.info(
            "[CalculateScoresForRulesVersionUseCase] rules_version_id=%d season=%s "
            "competition_id=%s events_calculated=%d players_updated=%d",
            rules_version_id, season, competition_id, events_calculated, players_updated,
        )
        return CalculateScoresForRulesVersionResult(
            rules_version_id=rules_version_id,
            season=season,
            competition_id=competition_id,
            events_calculated=events_calculated,
            players_updated=players_updated,
            status="completed",
            error=None,
        )
