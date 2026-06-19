from typing import Annotated

from fastapi import APIRouter, Depends, Query

from sfa.api.v1.schemas.ranking import RankedPlayerSchema, RankingResponseSchema
from sfa.application.use_cases.get_ranking import GetRankingUseCase
from sfa.core.dependencies import get_ranking_use_case

router = APIRouter()


@router.get("/ranking", response_model=RankingResponseSchema)
async def get_ranking(
    use_case: Annotated[GetRankingUseCase, Depends(get_ranking_use_case)],
    season: str | None = Query(default=None, description="Temporada, ej: 2024-25"),
    position: str | None = Query(default=None, description="Posición: DEL, EXT, MC, DC, LAT, GK"),
    competition_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    name: str | None = Query(default=None, description="Búsqueda por nombre de jugador"),
    rules_version_id: int | None = Query(
        default=None,
        description="ID de versión de reglas. Si no se pasa, usa la versión activa.",
    ),
    use_total: bool = Query(
        default=False,
        description="Si true, ordena por sfa_total_pts (total_pts + achievement_bonus_pts).",
    ),
):
    result = await use_case.execute(
        season, position, competition_id, limit, name, rules_version_id, use_total
    )
    return RankingResponseSchema(
        season=result.season,
        total=result.total,
        ranking=[
            RankedPlayerSchema(
                rank=r.rank,
                id=r.player_id,
                name=r.player_name,
                team=r.team_name,
                team_logo_url=r.team_logo_url,
                position=r.position,
                competition=r.competition_name,
                sfa_pts=r.total_pts,
                matches=r.matches_played,
                photo_url=r.photo_url,
                goals=r.goals,
                assists=r.assists,
                dribbles_won=r.dribbles_won,
                duels_won=r.duels_won,
                b1_bonus_pts=r.b1_bonus_pts,
                b1_bonus_label=r.b1_bonus_label,
            )
            for r in result.ranking
        ],
    )
