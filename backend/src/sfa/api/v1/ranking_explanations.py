from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sfa.api.v1.schemas.ranking_explanations import (
    GenerateRankingExplanationsQueuedSchema,
    GenerateRankingExplanationsRequestSchema,
    RankingExplanationsResponseSchema,
    RankingPlayerExplanationSchema,
)
from sfa.application.use_cases.get_player_ranking_explanation import GetPlayerRankingExplanationUseCase
from sfa.application.use_cases.get_ranking_explanations import GetRankingExplanationsUseCase
from sfa.core.dependencies import (
    get_scoring_rules_version_repository,
    get_player_ranking_explanation_use_case,
    get_ranking_explanations_use_case,
    require_admin_key,
)
from sfa.domain.ranking_explanation_ports import RankingExplanationRequestDTO
from sfa.infrastructure.repositories.scoring_rules_version_repository import (
    ScoringRulesVersionRepository,
)

router = APIRouter()


@router.get("/ranking/explanations", response_model=RankingExplanationsResponseSchema)
async def get_ranking_explanations(
    use_case: Annotated[GetRankingExplanationsUseCase, Depends(get_ranking_explanations_use_case)],
    ver_repo: Annotated[
        ScoringRulesVersionRepository,
        Depends(get_scoring_rules_version_repository),
    ],
    season: str = Query(...),
    competition_id: int | None = Query(default=None),
    rules_version_id: int | None = Query(default=None),
    scope: str = Query(default="ranking"),
    limit: int = Query(default=10, ge=1, le=10),
    use_total: bool = Query(default=True),
) -> RankingExplanationsResponseSchema:
    if rules_version_id is None:
        active = await ver_repo.get_active_version()
        rules_version_id = active.id if active else None
    request = RankingExplanationRequestDTO(
        season=season,
        competition_id=competition_id,
        rules_version_id=rules_version_id,
        scope=scope,
        limit=limit,
        use_total=use_total,
    )
    explanations = await use_case.execute(request)
    return RankingExplanationsResponseSchema(
        season=season,
        scope=scope,
        explanations=[RankingPlayerExplanationSchema(**item.__dict__) for item in explanations],
    )


@router.get("/players/{player_id}/explanation", response_model=RankingPlayerExplanationSchema)
async def get_player_ranking_explanation(
    player_id: int,
    use_case: Annotated[
        GetPlayerRankingExplanationUseCase,
        Depends(get_player_ranking_explanation_use_case),
    ],
    ver_repo: Annotated[
        ScoringRulesVersionRepository,
        Depends(get_scoring_rules_version_repository),
    ],
    season: str = Query(...),
    competition_id: int | None = Query(default=None),
    rules_version_id: int | None = Query(default=None),
    scope: str = Query(default="ranking"),
    use_total: bool = Query(default=True),
) -> RankingPlayerExplanationSchema:
    if rules_version_id is None:
        active = await ver_repo.get_active_version()
        rules_version_id = active.id if active else None
    request = RankingExplanationRequestDTO(
        season=season,
        competition_id=competition_id,
        rules_version_id=rules_version_id,
        scope=scope,
        use_total=use_total,
    )
    explanation = await use_case.execute(player_id, request)
    if explanation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explanation not found")
    return RankingPlayerExplanationSchema(**explanation.__dict__)


@router.post(
    "/admin/ranking-explanations/generate",
    response_model=GenerateRankingExplanationsQueuedSchema,
    dependencies=[Depends(require_admin_key)],
)
async def trigger_generate_ranking_explanations(
    body: GenerateRankingExplanationsRequestSchema,
) -> GenerateRankingExplanationsQueuedSchema:
    from sfa.tasks.generate_ranking_explanations_task import generate_ranking_explanations_task

    task = generate_ranking_explanations_task.delay(
        body.season,
        body.rules_version_id,
        body.competition_id,
        body.scope,
        body.limit,
        body.force,
        body.use_total,
    )
    return GenerateRankingExplanationsQueuedSchema(task_id=task.id)
