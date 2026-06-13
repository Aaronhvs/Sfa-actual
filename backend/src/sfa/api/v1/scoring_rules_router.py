from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.api.v1.schemas.scoring_rules_schemas import (
    CreateScoringRulesVersionRequestSchema,
    InferAchievementsAllRequestSchema,
    InferAchievementsRequestSchema,
    InferAchievementsResponseSchema,
    RecalculateRequestSchema,
    RecalculateResponseSchema,
    ScoringRulesVersionResponseSchema,
)
from sfa.api.v1.schemas.full_recalculation_schemas import (
    FullRecalculateRequestSchema,
    FullRecalculateResponseSchema,
)
from sfa.application.use_cases.manage_scoring_rules_version import (
    ActivateScoringRulesVersionUseCase,
    CreateScoringRulesVersionUseCase,
    ListScoringRulesVersionsUseCase,
)
from sfa.core.dependencies import (
    get_activate_scoring_rules_version_use_case,
    get_create_scoring_rules_version_use_case,
    get_list_scoring_rules_versions_use_case,
)
from sfa.infrastructure.database import get_db

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/rules-versions", response_model=list[ScoringRulesVersionResponseSchema])
async def list_scoring_rules_versions(
    use_case: Annotated[
        ListScoringRulesVersionsUseCase,
        Depends(get_list_scoring_rules_versions_use_case),
    ],
):
    result = await use_case.execute()
    return [
        ScoringRulesVersionResponseSchema(
            id=v.id,
            name=v.name,
            version=v.version,
            description=v.description or None,
            is_active=v.is_active,
            config_json=v.config.to_dict(),
            created_at=v.created_at,
        )
        for v in result.versions
    ]


@router.post("/rules-versions", response_model=ScoringRulesVersionResponseSchema, status_code=201)
async def create_scoring_rules_version(
    body: CreateScoringRulesVersionRequestSchema,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_case: Annotated[
        CreateScoringRulesVersionUseCase,
        Depends(get_create_scoring_rules_version_use_case),
    ],
    list_use_case: Annotated[
        ListScoringRulesVersionsUseCase,
        Depends(get_list_scoring_rules_versions_use_case),
    ],
):
    result = await use_case.execute(
        name=body.name,
        version=body.version,
        description=body.description,
        config_dict=body.config_json,
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.error)

    await db.commit()

    versions_result = await list_use_case.execute()
    created = next((v for v in versions_result.versions if v.id == result.version_id), None)
    if created is None:
        raise HTTPException(status_code=500, detail="Version created but not found")

    return ScoringRulesVersionResponseSchema(
        id=created.id,
        name=created.name,
        version=created.version,
        description=created.description or None,
        is_active=created.is_active,
        config_json=created.config.to_dict(),
        created_at=created.created_at,
    )


@router.patch("/rules-versions/{version_id}/activate", status_code=200)
async def activate_scoring_rules_version(
    version_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    use_case: Annotated[
        ActivateScoringRulesVersionUseCase,
        Depends(get_activate_scoring_rules_version_use_case),
    ],
):
    result = await use_case.execute(version_id)
    if result.status == "failed":
        if "not found" in (result.error or "").lower():
            raise HTTPException(status_code=404, detail=result.error)
        raise HTTPException(status_code=400, detail=result.error)
    await db.commit()
    return {"version_id": result.version_id, "status": result.status}


@router.post("/recalculate", response_model=RecalculateResponseSchema, status_code=202)
async def trigger_recalculate(body: RecalculateRequestSchema):
    from sfa.tasks.calculate_scores_for_rules_version_task import (
        calculate_scores_for_rules_version_task,
    )

    task = calculate_scores_for_rules_version_task.delay(
        rules_version_id=body.rules_version_id,
        season=body.season,
        competition_id=body.competition_id,
        match_id=body.match_id,
        player_id=body.player_id,
        force_recalculate=body.force_recalculate,
    )
    return RecalculateResponseSchema(
        task_id=task.id,
        status="queued",
        message=f"Recalculation queued for rules_version_id={body.rules_version_id} season={body.season}",
    )


@router.post(
    "/recalculate-full",
    response_model=FullRecalculateResponseSchema,
    status_code=202,
)
async def trigger_full_recalculate(body: FullRecalculateRequestSchema):
    """Full recalculation: scoring + bulk season score rebuild + achievement bonuses."""
    from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task

    task = run_full_recalculation_task.delay(
        rules_version_id=body.rules_version_id,
        season=body.season,
        force_recalculate=body.force_recalculate,
    )
    return FullRecalculateResponseSchema(
        task_id=task.id,
        status="queued",
        message=(
            f"Full recalculation queued for rules_version_id={body.rules_version_id} "
            f"season={body.season}. Includes scoring and achievement bonuses."
        ),
    )


@router.post("/infer-achievements", response_model=InferAchievementsResponseSchema, status_code=202)
async def trigger_infer_achievements(body: InferAchievementsRequestSchema):
    """Infer and upsert competition achievements from fixture data for one competition."""
    from sfa.tasks.infer_competition_achievements_task import infer_competition_achievements_task

    task = infer_competition_achievements_task.delay(
        competition_id=body.competition_id,
        season=body.season,
        rules_version_id=body.rules_version_id,
    )
    return InferAchievementsResponseSchema(
        task_id=task.id,
        status="queued",
        message=f"Achievement inference queued for competition_id={body.competition_id} season={body.season}",
    )


@router.post("/infer-achievements-all", response_model=InferAchievementsResponseSchema, status_code=202)
async def trigger_infer_achievements_all(body: InferAchievementsAllRequestSchema):
    """Infer and upsert competition achievements for ALL knockout competitions in a season."""
    from sfa.tasks.infer_all_competition_achievements_task import infer_all_competition_achievements_task

    task = infer_all_competition_achievements_task.delay(
        season=body.season,
        rules_version_id=body.rules_version_id,
    )
    return InferAchievementsResponseSchema(
        task_id=task.id,
        status="queued",
        message=f"Achievement inference queued for ALL competitions season={body.season}",
    )
