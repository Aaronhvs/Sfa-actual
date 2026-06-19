from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sfa.domain.ports import SFAScoreRepositoryProtocol


@dataclass(frozen=True)
class BreakdownEntry:
    count: int
    pts: float
    pct: float | None = None


@dataclass(frozen=True)
class PlayerDetailResult:
    id: int
    name: str
    team: str
    position: str
    competition: str
    sfa_pts: float
    matches: int          # total partidos en todas las competiciones de la temporada
    total_goals: int      # total goles en todas las competiciones
    total_assists: int    # total asistencias en todas las competiciones
    photo_url: str | None
    global_rank: int
    season: str
    breakdown: dict[str, BreakdownEntry] | None
    competitions: list[str]
    available_seasons: list[str] = field(default_factory=list)
    b1_bonus_pts: float = 0.0
    b1_bonus_label: str | None = None


@runtime_checkable
class GetPlayerDetailUseCaseProtocol(Protocol):
    async def execute(
        self, player_id: int, season: str | None = None, rules_version_id: int | None = None,
    ) -> PlayerDetailResult: ...


class GetPlayerDetailUseCase(GetPlayerDetailUseCaseProtocol):
    """Orquesta la obtención del detalle de un jugador.

    Lógica movida desde players.py _get_player_detail.
    """

    def __init__(
        self,
        score_repo: SFAScoreRepositoryProtocol,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._score_repo = score_repo
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self, player_id: int, season: str | None = None, rules_version_id: int | None = None,
    ) -> PlayerDetailResult:
        explicit_rules_version = rules_version_id is not None
        if rules_version_id is None:
            rules_version_id = self._default_rules_version_id

        # 1. Resolver season
        if season is None:
            season = await self._score_repo.latest_season_for_player(player_id)

        if season is None:
            raise PlayerNotFoundError(player_id)

        available_seasons = await self._score_repo.get_available_seasons_for_player(
            player_id
        )

        if season == "all":
            historical_rules_version_id = rules_version_id if explicit_rules_version else None
            total_matches, total_goals, total_assists, total_pts = (
                await self._score_repo.get_total_player_stats_all_seasons(
                    player_id, historical_rules_version_id
                )
            )
            if total_pts == 0.0 and total_matches == 0:
                raise PlayerNotFoundError(player_id)

            latest = available_seasons[0] if available_seasons else (
                await self._score_repo.latest_season_for_player(player_id)
            )
            if latest is None:
                raise PlayerNotFoundError(player_id)

            latest_rules_version_id = await self._score_repo.resolve_rules_version_id_for_season(
                latest, rules_version_id,
            )
            score = await self._score_repo.get_best_score_for_player_season(
                player_id, latest, latest_rules_version_id,
            )
            if score is None:
                raise PlayerNotFoundError(player_id)

            competitions = await self._score_repo.get_competitions_for_player_season(
                player_id, latest, latest_rules_version_id,
            )
            global_rank = await self._score_repo.get_global_rank_all_seasons(
                player_id, total_pts, historical_rules_version_id,
            )
            return self._build_result(
                score=score,
                season="all",
                competitions=competitions,
                available_seasons=available_seasons,
                total_matches=total_matches,
                total_goals=total_goals,
                total_assists=total_assists,
                total_pts=total_pts,
                global_rank=global_rank,
            )

        if not explicit_rules_version:
            rules_version_id = await self._score_repo.resolve_rules_version_id_for_season(
                season, rules_version_id,
            )

        # 2. Obtener score principal
        score = await self._score_repo.get_best_score_for_player_season(
            player_id, season, rules_version_id,
        )
        if score is None:
            raise PlayerNotFoundError(player_id)

        # 3. Obtener competitions
        competitions = await self._score_repo.get_competitions_for_player_season(
            player_id, season, rules_version_id,
        )

        # 4. Totales globales de la temporada (todas las competiciones)
        total_matches, total_goals, total_assists, total_pts = (
            await self._score_repo.get_total_player_stats(player_id, season, rules_version_id)
        )

        # 5. Calcular rank global usando pts totales
        global_rank = await self._score_repo.get_global_rank(
            player_id, season, total_pts, rules_version_id,
        )
        b1_bonus_pts, b1_bonus_label = await self._score_repo.get_b1_bonus_for_player(
            player_id, season, rules_version_id,
        )

        return self._build_result(
            score=score,
            season=season,
            competitions=competitions,
            available_seasons=available_seasons,
            total_matches=total_matches,
            total_goals=total_goals,
            total_assists=total_assists,
            total_pts=total_pts,
            global_rank=global_rank,
            b1_bonus_pts=b1_bonus_pts,
            b1_bonus_label=b1_bonus_label,
        )

    @staticmethod
    def _build_result(
        score,
        season: str,
        competitions: list[str],
        available_seasons: list[str],
        total_matches: int,
        total_goals: int,
        total_assists: int,
        total_pts: float,
        global_rank: int,
        b1_bonus_pts: float = 0.0,
        b1_bonus_label: str | None = None,
    ) -> PlayerDetailResult:
        breakdown: dict[str, BreakdownEntry] | None = None
        if score.breakdown:
            breakdown = {
                k: BreakdownEntry(**v)
                for k, v in score.breakdown.items()
                if isinstance(v, dict) and "count" in v and "pts" in v
            }

        return PlayerDetailResult(
            id=score.player_id,
            name=score.player_name,
            team=score.team_name,
            position=score.position,
            competition=score.competition_name,
            sfa_pts=total_pts,
            matches=total_matches,
            total_goals=total_goals,
            total_assists=total_assists,
            photo_url=score.photo_url,
            global_rank=global_rank,
            season=season,
            breakdown=breakdown,
            competitions=competitions,
            available_seasons=available_seasons,
            b1_bonus_pts=b1_bonus_pts,
            b1_bonus_label=b1_bonus_label,
        )


class PlayerNotFoundError(Exception):
    def __init__(self, player_id: int) -> None:
        self.player_id = player_id
        super().__init__(f"Player {player_id} not found")
