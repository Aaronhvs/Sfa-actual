from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.infrastructure.database import get_db
from sfa.infrastructure.redis_client import get_redis
from sfa.infrastructure.repositories import (
    BirthDateEnrichmentRepository,
    CompetitionAchievementRepository,
    CompetitionRepository,
    EnrichPositionRepository,
    IndividualHonorRepository,
    InferAchievementsRepository,
    PlayerEventRepository,
    PlayerEventScoreRepository,
    PlayerRepository,
    PlayerTmIdRepository,
    RankingExplanationRepository,
    ScoringRepository,
    ScoringRulesVersionRepository,
    SeasonRepository,
    SFAScoreRepository,
    StandingRepository,
    SystemRepository,
    TeamStrengthRepository,
    TournamentRepository,
    WorldCupRepository,
)

# ─── Repositorios ────────────────────────────────────────────────────



async def get_player_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerRepository:
    return PlayerRepository(db)


async def get_sfa_score_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SFAScoreRepository:
    return SFAScoreRepository(db)


async def get_ranking_explanation_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RankingExplanationRepository:
    return RankingExplanationRepository(db)


async def get_competition_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompetitionRepository:
    return CompetitionRepository(db)


async def get_standing_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StandingRepository:
    return StandingRepository(db)


async def get_tournament_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TournamentRepository:
    return TournamentRepository(db)


async def get_player_event_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerEventRepository:
    return PlayerEventRepository(db)


async def get_system_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemRepository:
    return SystemRepository(db)


async def get_scoring_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScoringRepository:
    return ScoringRepository(db)


async def get_scoring_rules_version_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScoringRulesVersionRepository:
    return ScoringRulesVersionRepository(db)


async def get_season_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SeasonRepository:
    return SeasonRepository(db)


async def get_player_event_score_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerEventScoreRepository:
    return PlayerEventScoreRepository(db)


async def get_player_tm_id_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerTmIdRepository:
    return PlayerTmIdRepository(db)


async def get_enrich_position_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrichPositionRepository:
    return EnrichPositionRepository(db)


# ─── Use Cases ───────────────────────────────────────────────────────

from sfa.application.use_cases.calculate_achievement_bonuses import (
    CalculateAchievementBonusesUseCase,
)
from sfa.application.use_cases.calculate_all_scores import CalculateAllScoresUseCase
from sfa.application.use_cases.calculate_competition_scores import CalculateCompetitionScoresUseCase
from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
)
from sfa.application.use_cases.calculate_team_strengths import CalculateTeamStrengthsUseCase
from sfa.application.use_cases.compare_players import ComparePlayersUseCase
from sfa.application.use_cases.enrich_player_birth_dates import EnrichPlayerBirthDatesUseCase
from sfa.application.use_cases.enrich_player_positions import EnrichPlayerPositionsUseCase
from sfa.application.use_cases.fix_player_positions import FixPlayerPositionsUseCase
from sfa.application.use_cases.get_ingestion_status import GetIngestionStatusUseCase
from sfa.application.use_cases.get_national_team_elo_coverage import (
    GetNationalTeamEloCoverageUseCase,
)
from sfa.application.use_cases.get_player_achievements import GetPlayerAchievementsUseCase
from sfa.application.use_cases.get_player_detail import GetPlayerDetailUseCase
from sfa.application.use_cases.get_player_events import GetPlayerEventsUseCase
from sfa.application.use_cases.get_player_fixtures import GetPlayerFixturesUseCase
from sfa.application.use_cases.get_player_individual_honors import (
    GetPlayerIndividualHonorsUseCase,
)
from sfa.application.use_cases.get_player_ranking_explanation import (
    GetPlayerRankingExplanationUseCase,
)
from sfa.application.use_cases.get_player_season_stats import GetPlayerSeasonStatsUseCase
from sfa.application.use_cases.get_ranking import GetRankingUseCase
from sfa.application.use_cases.get_ranking_explanations import GetRankingExplanationsUseCase
from sfa.application.use_cases.get_seasons import GetSeasonsUseCase
from sfa.application.use_cases.get_standings import GetStandingsUseCase
from sfa.application.use_cases.get_status import GetStatusUseCase
from sfa.application.use_cases.get_tournaments import (
    GetTournamentDashboardUseCase,
    GetTournamentUseCase,
    ListTournamentsUseCase,
)
from sfa.application.use_cases.get_world_cup import (
    GetWcTeamProfileUseCase,
    GetWcTeamSFARankingUseCase,
    GetWorldCupFixtureDetailUseCase,
    GetWorldCupFixturesUseCase,
    GetWorldCupLiveUseCase,
    GetWorldCupStandingsUseCase,
)
from sfa.application.use_cases.infer_competition_achievements import (
    InferAllCompetitionAchievementsUseCase,
    InferCompetitionAchievementsUseCase,
)
from sfa.application.use_cases.list_competitions import ListCompetitionsUseCase
from sfa.application.use_cases.manage_scoring_rules_version import (
    ActivateScoringRulesVersionUseCase,
    CreateScoringRulesVersionUseCase,
    ListScoringRulesVersionsUseCase,
)
from sfa.application.use_cases.register_competition_achievement import (
    RegisterCompetitionAchievementUseCase,
)
from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
from sfa.application.use_cases.seed_national_team_elo import SeedNationalTeamEloUseCase
from sfa.infrastructure.providers.ranking_explanation_writer import (
    DeterministicRankingExplanationWriter,
)


async def get_player_detail_use_case(
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
    ver_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
) -> GetPlayerDetailUseCase:
    active = await ver_repo.get_active_version()
    return GetPlayerDetailUseCase(
        score_repo,
        default_rules_version_id=active.id if active else None,
        season_repo=season_repo,
    )


async def get_ranking_use_case(
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
    ver_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
) -> GetRankingUseCase:
    active = await ver_repo.get_active_version()
    return GetRankingUseCase(
        score_repo,
        default_rules_version_id=active.id if active else None,
        season_repo=season_repo,
    )


async def get_ranking_explanation_writer() -> DeterministicRankingExplanationWriter:
    return DeterministicRankingExplanationWriter()


async def get_ranking_explanations_use_case(
    repo: Annotated[RankingExplanationRepository, Depends(get_ranking_explanation_repository)],
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    writer: Annotated[
        DeterministicRankingExplanationWriter,
        Depends(get_ranking_explanation_writer),
    ],
) -> GetRankingExplanationsUseCase:
    return GetRankingExplanationsUseCase(
        repo,
        score_repo=score_repo,
        season_repo=season_repo,
        fallback_writer=writer,
    )


async def get_player_ranking_explanation_use_case(
    repo: Annotated[RankingExplanationRepository, Depends(get_ranking_explanation_repository)],
) -> GetPlayerRankingExplanationUseCase:
    return GetPlayerRankingExplanationUseCase(repo)


async def get_birth_date_enrichment_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BirthDateEnrichmentRepository:
    return BirthDateEnrichmentRepository(db)


async def get_enrich_player_birth_dates_use_case(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrichPlayerBirthDatesUseCase:
    from sfa.core.config import get_settings
    from sfa.infrastructure.providers.api_football import APIFootballProvider

    settings = get_settings()
    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)
    repo = BirthDateEnrichmentRepository(db)
    return EnrichPlayerBirthDatesUseCase(provider=provider, repo=repo)


async def get_seasons_use_case(
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
) -> GetSeasonsUseCase:
    return GetSeasonsUseCase(season_repo)


async def get_player_events_use_case(
    event_repo: Annotated[PlayerEventRepository, Depends(get_player_event_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
) -> GetPlayerEventsUseCase:
    return GetPlayerEventsUseCase(event_repo, season_repo, score_repo)


async def get_player_fixtures_use_case(
    event_repo: Annotated[PlayerEventRepository, Depends(get_player_event_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
) -> GetPlayerFixturesUseCase:
    return GetPlayerFixturesUseCase(event_repo, season_repo, score_repo)


async def get_player_season_stats_use_case(
    event_repo: Annotated[PlayerEventRepository, Depends(get_player_event_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
) -> GetPlayerSeasonStatsUseCase:
    return GetPlayerSeasonStatsUseCase(event_repo, season_repo)


async def get_compare_players_use_case(
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
    event_repo: Annotated[PlayerEventRepository, Depends(get_player_event_repository)],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    ver_repo: Annotated[
        ScoringRulesVersionRepository,
        Depends(get_scoring_rules_version_repository),
    ],
) -> ComparePlayersUseCase:
    active = await ver_repo.get_active_version()
    detail_uc = GetPlayerDetailUseCase(
        score_repo,
        default_rules_version_id=active.id if active else None,
        season_repo=season_repo,
    )
    return ComparePlayersUseCase(
        detail_uc=detail_uc,
        events_uc=GetPlayerEventsUseCase(event_repo, season_repo, score_repo),
        fixtures_uc=GetPlayerFixturesUseCase(event_repo, season_repo, score_repo),
        stats_uc=GetPlayerSeasonStatsUseCase(event_repo, season_repo),
    )


async def get_list_competitions_use_case(
    comp_repo: Annotated[CompetitionRepository, Depends(get_competition_repository)],
) -> ListCompetitionsUseCase:
    return ListCompetitionsUseCase(comp_repo)


async def get_standings_use_case(
    standing_repo: Annotated[StandingRepository, Depends(get_standing_repository)],
) -> GetStandingsUseCase:
    return GetStandingsUseCase(standing_repo)


async def get_tournaments_use_case(
    repository: Annotated[
        TournamentRepository,
        Depends(get_tournament_repository),
    ],
) -> ListTournamentsUseCase:
    return ListTournamentsUseCase(repository)


async def get_tournament_dashboard_use_case(
    repository: Annotated[
        TournamentRepository,
        Depends(get_tournament_repository),
    ],
) -> GetTournamentDashboardUseCase:
    return GetTournamentDashboardUseCase(repository)


async def get_tournament_use_case(
    repository: Annotated[
        TournamentRepository,
        Depends(get_tournament_repository),
    ],
) -> GetTournamentUseCase:
    return GetTournamentUseCase(repository)


async def get_status_use_case(
    system_repo: Annotated[SystemRepository, Depends(get_system_repository)],
) -> GetStatusUseCase:
    return GetStatusUseCase(system_repo)


async def get_world_cup_repository(
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorldCupRepository:
    from sfa.core.config import get_settings
    from sfa.infrastructure.providers.api_football import APIFootballProvider

    settings = get_settings()
    provider = APIFootballProvider(
        settings.API_FOOTBALL_KEY,
        settings.API_FOOTBALL_BASE_URL,
    )
    return WorldCupRepository(provider=provider, redis=redis, session=db)


async def get_world_cup_fixtures_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
) -> GetWorldCupFixturesUseCase:
    return GetWorldCupFixturesUseCase(repository)


async def get_world_cup_fixture_detail_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
) -> GetWorldCupFixtureDetailUseCase:
    return GetWorldCupFixtureDetailUseCase(repository)


async def get_world_cup_live_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
) -> GetWorldCupLiveUseCase:
    return GetWorldCupLiveUseCase(repository)


async def get_world_cup_standings_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
) -> GetWorldCupStandingsUseCase:
    return GetWorldCupStandingsUseCase(repository)


async def get_wc_team_sfa_ranking_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
    ver_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
) -> GetWcTeamSFARankingUseCase:
    active = await ver_repo.get_active_version()
    return GetWcTeamSFARankingUseCase(repository, default_rules_version_id=active.id if active else None)


async def get_wc_team_profile_use_case(
    repository: Annotated[WorldCupRepository, Depends(get_world_cup_repository)],
    ver_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
) -> GetWcTeamProfileUseCase:
    active = await ver_repo.get_active_version()
    return GetWcTeamProfileUseCase(repository, default_rules_version_id=active.id if active else None)


async def get_ingestion_status_use_case(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GetIngestionStatusUseCase:
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    return GetIngestionStatusUseCase(IngestionRepository(db))


async def get_calculate_competition_scores_use_case(
    repo: Annotated[ScoringRepository, Depends(get_scoring_repository)],
) -> CalculateCompetitionScoresUseCase:
    return CalculateCompetitionScoresUseCase(repo)


async def get_calculate_all_scores_use_case(
    repo: Annotated[ScoringRepository, Depends(get_scoring_repository)],
) -> CalculateAllScoresUseCase:
    return CalculateAllScoresUseCase(repo)


async def get_create_scoring_rules_version_use_case(
    repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
) -> CreateScoringRulesVersionUseCase:
    return CreateScoringRulesVersionUseCase(repo)


async def get_activate_scoring_rules_version_use_case(
    repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
) -> ActivateScoringRulesVersionUseCase:
    return ActivateScoringRulesVersionUseCase(repo)


async def get_list_scoring_rules_versions_use_case(
    repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
) -> ListScoringRulesVersionsUseCase:
    return ListScoringRulesVersionsUseCase(repo)


async def get_team_strength_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamStrengthRepository:
    return TeamStrengthRepository(db)


async def get_competition_achievement_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompetitionAchievementRepository:
    return CompetitionAchievementRepository(db)


async def get_individual_honor_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IndividualHonorRepository:
    return IndividualHonorRepository(db)


async def get_player_individual_honors_use_case(
    honor_repo: Annotated[IndividualHonorRepository, Depends(get_individual_honor_repository)],
    ver_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
) -> GetPlayerIndividualHonorsUseCase:
    active = await ver_repo.get_active_version()
    return GetPlayerIndividualHonorsUseCase(
        honor_repo,
        season_repo,
        score_repo,
        default_rules_version_id=active.id if active else None,
    )


async def get_player_achievements_use_case(
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    ver_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
    season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
    score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
) -> GetPlayerAchievementsUseCase:
    active = await ver_repo.get_active_version()
    return GetPlayerAchievementsUseCase(
        achievement_repo,
        default_rules_version_id=active.id if active else None,
        season_repository=season_repo,
        score_repository=score_repo,
    )


async def get_calculate_team_strengths_use_case(
    repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
) -> CalculateTeamStrengthsUseCase:
    return CalculateTeamStrengthsUseCase(repo)


async def get_infer_achievements_repository(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InferAchievementsRepository:
    return InferAchievementsRepository(db)


async def get_infer_competition_achievements_use_case(
    infer_repo: Annotated[InferAchievementsRepository, Depends(get_infer_achievements_repository)],
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
) -> InferCompetitionAchievementsUseCase:
    return InferCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_version_repo)


async def get_infer_all_competition_achievements_use_case(
    infer_repo: Annotated[InferAchievementsRepository, Depends(get_infer_achievements_repository)],
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
) -> InferAllCompetitionAchievementsUseCase:
    return InferAllCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_version_repo)


async def get_register_competition_achievement_use_case(
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
) -> RegisterCompetitionAchievementUseCase:
    return RegisterCompetitionAchievementUseCase(achievement_repo, rules_version_repo)


async def get_calculate_achievement_bonuses_use_case(
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
) -> CalculateAchievementBonusesUseCase:
    return CalculateAchievementBonusesUseCase(achievement_repo, rules_version_repo)


async def get_calculate_scores_for_rules_version_use_case(
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
    event_score_repo: Annotated[
        PlayerEventScoreRepository, Depends(get_player_event_score_repository)
    ],
) -> CalculateScoresForRulesVersionUseCase:
    return CalculateScoresForRulesVersionUseCase(
        rules_version_repo=rules_version_repo,
        event_score_repo=event_score_repo,
    )


async def get_seed_clubelo_use_case(
    repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
) -> SeedClubEloUseCase:
    from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    return SeedClubEloUseCase(
        repo=repo,
        provider=ClubEloProvider(),
        calculator=EloCalculatorService(),
    )


async def get_seed_national_team_elo_use_case(
    repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
) -> SeedNationalTeamEloUseCase:
    from sfa.infrastructure.providers.national_team_elo_provider import NationalTeamEloProvider
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    return SeedNationalTeamEloUseCase(
        repo=repo,
        provider=NationalTeamEloProvider(),
        calculator=EloCalculatorService(),
    )


async def get_national_team_elo_coverage_use_case(
    repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
) -> GetNationalTeamEloCoverageUseCase:
    return GetNationalTeamEloCoverageUseCase(repo)


async def get_calculate_elo_use_case(
    repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
) -> CalculateEloRatingsUseCase:
    from sfa.infrastructure.services.elo_calculator import EloCalculatorService

    return CalculateEloRatingsUseCase(repo=repo, calculator=EloCalculatorService())


async def get_fix_player_positions_use_case(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FixPlayerPositionsUseCase:
    return FixPlayerPositionsUseCase(db)


async def get_enrich_player_positions_use_case(
    tm_id_repo: Annotated[PlayerTmIdRepository, Depends(get_player_tm_id_repository)],
    enrich_repo: Annotated[EnrichPositionRepository, Depends(get_enrich_position_repository)],
) -> EnrichPlayerPositionsUseCase:
    from sfa.infrastructure.providers.transfermarkt_scraper import TransfermarktScraper

    return EnrichPlayerPositionsUseCase(
        provider=TransfermarktScraper(),
        tm_id_repo=tm_id_repo,
        enrich_repo=enrich_repo,
    )


async def get_reingest_player_use_case(
    db: Annotated[AsyncSession, Depends(get_db)],
    scoring_uc: Annotated[
        CalculateScoresForRulesVersionUseCase,
        Depends(get_calculate_scores_for_rules_version_use_case),
    ],
) -> object:
    from sfa.application.use_cases.reingest_player import ReingestPlayerUseCase
    from sfa.core.config import get_settings
    from sfa.infrastructure.providers.api_football import APIFootballProvider
    from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository

    settings = get_settings()
    provider = APIFootballProvider(settings.API_FOOTBALL_KEY, settings.API_FOOTBALL_BASE_URL)
    ingestion_repo = IngestionRepository(db)
    rules_version_repo = ScoringRulesVersionRepository(db)
    return ReingestPlayerUseCase(provider, ingestion_repo, rules_version_repo, scoring_uc)


async def require_admin_key(
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    """
    Protects admin endpoints with a static API key.
    - DEBUG=True + no key configured → allow (local dev, no .env config needed)
    - DEBUG=False + no key configured → block (production fail-safe)
    - Key configured → require X-Admin-Key header to match exactly
    """
    from sfa.core.config import get_settings
    settings = get_settings()
    configured_key = settings.ADMIN_API_KEY

    if not configured_key:
        if settings.DEBUG:
            return  # dev mode, no key set → open
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API not available",
        )

    if x_admin_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header",
        )


__all__ = ["get_db", "get_redis", "require_admin_key"]
