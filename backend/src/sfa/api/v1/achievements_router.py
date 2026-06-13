from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.api.v1.schemas.achievements_schemas import (
    CalculateAchievementBonusesRequestSchema,
    CalculateAchievementBonusesResponseSchema,
    CalculateTeamStrengthsRequestSchema,
    CalculateTeamStrengthsResponseSchema,
    RegisterAchievementRequestSchema,
    RegisterAchievementResponseSchema,
)
from sfa.application.use_cases.register_competition_achievement import (
    RegisterCompetitionAchievementUseCase,
)
from sfa.core.dependencies import get_register_competition_achievement_use_case
from sfa.infrastructure.database import get_db

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/achievements", response_model=RegisterAchievementResponseSchema, status_code=201)
async def register_achievement(
    body: RegisterAchievementRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_case: Annotated[
        RegisterCompetitionAchievementUseCase,
        Depends(get_register_competition_achievement_use_case),
    ],
):
    result = await use_case.execute(
        competition_id=body.competition_id,
        team_id=body.team_id,
        season=body.season,
        phase=body.phase,
        rules_version_id=body.rules_version_id,
        competition_name=body.competition_name,
    )
    if result.status == "failed":
        if "not found" in (result.error or "").lower():
            raise HTTPException(status_code=404, detail=result.error)
        raise HTTPException(status_code=400, detail=result.error)
    await db.commit()
    return RegisterAchievementResponseSchema(
        achievement_id=result.achievement_id,
        status=result.status,
        message=f"Achievement registered with id={result.achievement_id}",
    )


@router.post(
    "/achievements/calculate-bonuses",
    response_model=CalculateAchievementBonusesResponseSchema,
    status_code=202,
)
async def trigger_calculate_achievement_bonuses(body: CalculateAchievementBonusesRequestSchema):
    from sfa.tasks.calculate_achievement_bonuses_task import calculate_achievement_bonuses_task

    task = calculate_achievement_bonuses_task.delay(
        season=body.season,
        competition_id=body.competition_id,
        rules_version_id=body.rules_version_id,
    )
    return CalculateAchievementBonusesResponseSchema(
        task_id=task.id,
        status="queued",
        message=f"Achievement bonus calculation queued for season={body.season} "
                f"competition_id={body.competition_id}",
    )


@router.post(
    "/team-strengths/calculate",
    response_model=CalculateTeamStrengthsResponseSchema,
    status_code=202,
)
async def trigger_calculate_team_strengths(body: CalculateTeamStrengthsRequestSchema):
    from sfa.tasks.calculate_team_strengths_task import calculate_team_strengths_task

    task = calculate_team_strengths_task.delay(
        season=body.season,
        competition_id=body.competition_id,
        matchday=body.matchday,
        league_factor=body.league_factor,
    )
    return CalculateTeamStrengthsResponseSchema(
        task_id=task.id,
        status="queued",
        message=f"Team strength calculation queued for season={body.season} "
                f"competition_id={body.competition_id}",
    )
