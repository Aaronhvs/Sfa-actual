from __future__ import annotations

import logging

from sfa.domain.infer_achievements_ports import (
    InferAchievementsRepositoryPort,
    InferAchievementsResult,
    InferAllAchievementsResult,
    KnockoutFixtureDTO,
)
from sfa.domain.scoring.achievement_categories import (
    TERMINAL_KNOCKOUT_PHASES,
    get_competition_category,
)
from sfa.domain.scoring.entities import CompetitionAchievement
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)
from sfa.domain.trophy_results import FINAL_STATUSES, title_policy

logger = logging.getLogger(__name__)

STAGE_TO_PHASE: dict[str, str] = {
    "final":        "winner",
    "third_place":  "third_place",
    "semi":         "semi_final",
    "semi_final":   "semi_final",
    "quarter":      "quarter_final",
    "quarter_final": "quarter_final",
    "round_of_16":  "round_of_16",
    "round_of_32":  "round_of_32",
}

STAGE_ORDER: dict[str, int] = {
    "round_of_32":  1,
    "round_of_16":  2,
    "quarter":      3,
    "quarter_final": 3,
    "semi":         4,
    "semi_final":   4,
    "third_place":  5,
    "final":        6,
}

ORDER_TO_PHASE: dict[int, str] = {
    1: "round_of_32",
    2: "round_of_16",
    3: "quarter_final",
    4: "semi_final",
}


class InferCompetitionAchievementsUseCase:
    def __init__(
        self,
        infer_repo: InferAchievementsRepositoryPort,
        achievement_repo: CompetitionAchievementRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._infer_repo = infer_repo
        self._achievement_repo = achievement_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        competition_id: int,
        season: str,
        rules_version_id: int,
    ) -> InferAchievementsResult:
        rules_version = await self._rules_version_repo.get_version_by_id(rules_version_id)
        if rules_version is None:
            logger.warning(
                "[InferCompetitionAchievementsUseCase] rules_version_id=%d not found",
                rules_version_id,
            )
            return InferAchievementsResult(
                competition_id=competition_id, season=season,
                skipped=True, achievements_upserted=0, phases_found=[],
            )

        config = rules_version.config

        fixtures = await self._infer_repo.get_knockout_stage_fixtures(competition_id, season)
        if not fixtures:
            logger.info(
                "[InferCompetitionAchievementsUseCase] competition_id=%d season=%s: "
                "no knockout fixtures, skipping",
                competition_id, season,
            )
            return InferAchievementsResult(
                competition_id=competition_id, season=season,
                skipped=True, achievements_upserted=0, phases_found=[],
            )

        competition_name = await self._infer_repo.get_competition_name(competition_id)
        category = get_competition_category(competition_name)
        if category == "domestic_league":
            return InferAchievementsResult(
                competition_id=competition_id, season=season,
                skipped=True, achievements_upserted=0, phases_found=[],
            )
        if category is None and title_policy(competition_name, "winner") is None:
            logger.warning(
                "[InferCompetitionAchievementsUseCase] competition '%s' not in "
                "COMPETITION_CATEGORY_MAP, bonus_points will be 0",
                competition_name,
            )

        # Build teams_at_stage: stage → set of team_ids
        teams_at_stage: dict[str, set[int]] = {}
        for fx in fixtures:
            stage = fx.stage
            if stage not in teams_at_stage:
                teams_at_stage[stage] = set()
            teams_at_stage[stage].add(fx.home_team_id)
            teams_at_stage[stage].add(fx.away_team_id)

        # Only process known stages
        known_stages = {s for s in teams_at_stage if s in STAGE_ORDER}
        if not known_stages:
            logger.info(
                "[InferCompetitionAchievementsUseCase] competition_id=%d: no known KO stages",
                competition_id,
            )
            return InferAchievementsResult(
                competition_id=competition_id, season=season,
                skipped=True, achievements_upserted=0, phases_found=[],
            )

        team_reached_order: dict[int, int] = {}
        terminal_phase_team_ids: set[int] = set()
        phase_teams: dict[str, set[int]] = {}

        for fx in fixtures:
            if fx.stage not in STAGE_ORDER:
                continue
            current_order = min(STAGE_ORDER[fx.stage], max(ORDER_TO_PHASE))
            for team_id in (fx.home_team_id, fx.away_team_id):
                team_reached_order[team_id] = max(
                    team_reached_order.get(team_id, 0),
                    current_order,
                )

        for fx in fixtures:
            if fx.stage not in STAGE_ORDER or fx.stage in {"final", "third_place"}:
                continue

            winner_id, loser_id = await self._resolve_fixture_winner(fx)
            if winner_id is None or loser_id is None:
                continue

            current_order = STAGE_ORDER[fx.stage]
            next_order = min(current_order + 1, max(ORDER_TO_PHASE))
            team_reached_order[winner_id] = max(
                team_reached_order.get(winner_id, 0),
                next_order,
            )
            team_reached_order[loser_id] = max(
                team_reached_order.get(loser_id, 0),
                min(current_order, max(ORDER_TO_PHASE)),
            )

        if "final" in teams_at_stage:
            final_fixtures = [fx for fx in fixtures if fx.stage == "final"]
            final_team_ids = {
                team_id
                for fixture in final_fixtures
                for team_id in (fixture.home_team_id, fixture.away_team_id)
            }
            # An unresolved final is pending, never proof of a semi-final exit.
            terminal_phase_team_ids.update(final_team_ids)
            winner_id, runner_up_id = await self._resolve_final_winner(final_fixtures)
            if winner_id is not None and runner_up_id is not None:
                phase_teams["winner"] = {winner_id}
                phase_teams["runner_up"] = {runner_up_id}
                terminal_phase_team_ids.update({winner_id, runner_up_id})
            else:
                existing = await self._achievement_repo.get_achievements_for_season(
                    competition_id, season
                )
                preserved_candidates: dict[str, set[int]] = {}
                for achievement in existing:
                    if (
                        achievement.phase in TERMINAL_KNOCKOUT_PHASES
                        and achievement.team_id in final_team_ids
                    ):
                        preserved_candidates.setdefault(
                            achievement.phase, set()
                        ).add(achievement.team_id)
                preserved_team_ids = {
                    team_id
                    for team_ids in preserved_candidates.values()
                    for team_id in team_ids
                }
                complete_terminal_result = (
                    set(preserved_candidates) == TERMINAL_KNOCKOUT_PHASES
                    and all(
                        len(team_ids) == 1
                        for team_ids in preserved_candidates.values()
                    )
                    and len(preserved_team_ids) == 2
                    and preserved_team_ids == final_team_ids
                )
                if complete_terminal_result:
                    preserved = {
                        phase: next(iter(team_ids))
                        for phase, team_ids in preserved_candidates.items()
                    }
                    for phase, team_id in preserved.items():
                        phase_teams[phase] = {team_id}
                    terminal_phase_team_ids.update(preserved_team_ids)
                    logger.info(
                        "[InferCompetitionAchievementsUseCase] competition_id=%d "
                        "season=%s preserved authoritative final result=%s",
                        competition_id,
                        season,
                        preserved,
                    )
                else:
                    logger.info(
                        "[InferCompetitionAchievementsUseCase] competition_id=%d "
                        "season=%s final winner undetermined and no complete "
                        "authoritative result, skipping terminal phases",
                        competition_id,
                        season,
                    )

        if "third_place" in teams_at_stage:
            for fx in [fx for fx in fixtures if fx.stage == "third_place"]:
                terminal_phase_team_ids.update({fx.home_team_id, fx.away_team_id})
                winner_id, fourth_place_id = await self._resolve_fixture_winner(fx)
                if winner_id is not None and fourth_place_id is not None:
                    phase_teams.setdefault("third_place", set()).add(winner_id)
                    phase_teams.setdefault("fourth_place", set()).add(fourth_place_id)
                    terminal_phase_team_ids.update({winner_id, fourth_place_id})

        for team_id, reached_order in team_reached_order.items():
            if team_id in terminal_phase_team_ids:
                continue
            phase = ORDER_TO_PHASE.get(reached_order)
            if phase is not None:
                phase_teams.setdefault(phase, set()).add(team_id)

        # Reconcile only teams with a newly determined phase. Pending results and
        # identical natural keys retain their facts, IDs and dependent bonuses.
        proposed = {(team_id, phase) for phase, teams in phase_teams.items() for team_id in teams}
        resolved_teams = {team_id for team_id, _ in proposed}
        for old in await self._achievement_repo.get_achievements_for_season(competition_id, season):
            terminal_replaced = old.phase in {"winner", "runner_up"} and {
                "winner", "runner_up"
            }.issubset(phase_teams)
            if ((old.team_id in resolved_teams or terminal_replaced)
                    and (old.team_id, old.phase) not in proposed):
                await self._achievement_repo.retire_achievement(old.id)

        achievements_upserted = 0
        phases_found: list[str] = []

        for phase, team_ids in phase_teams.items():
            for team_id in team_ids:
                bonus_points = 0
                weight = 1.0

                if category is not None:
                    category_bonuses = config.achievement_phase_bonuses.get(category, {})
                    bonus_points = category_bonuses.get(phase, 0)
                    weight = config.competition_bonus_weights.get(competition_name, 1.0)
                policy = title_policy(competition_name, phase)
                if policy is not None:
                    bonus_points, weight, _ = policy

                try:
                    achievement = CompetitionAchievement(
                        id=None,
                        competition_id=competition_id,
                        team_id=team_id,
                        season=season,
                        phase=phase,
                        bonus_points=bonus_points,
                        weight=weight,
                        created_at=None,
                    )
                except ValueError as exc:
                    logger.warning(
                        "[InferCompetitionAchievementsUseCase] Skipping team_id=%d phase=%s: %s",
                        team_id, phase, exc,
                    )
                    continue

                await self._achievement_repo.upsert_achievement(achievement)
                achievements_upserted += 1

            if team_ids:
                phases_found.append(phase)

        logger.info(
            "[InferCompetitionAchievementsUseCase] competition_id=%d season=%s "
            "upserted=%d phases=%s",
            competition_id, season, achievements_upserted, phases_found,
        )
        return InferAchievementsResult(
            competition_id=competition_id,
            season=season,
            skipped=False,
            achievements_upserted=achievements_upserted,
            phases_found=phases_found,
        )

    async def _resolve_fixture_winner(
        self,
        fixture: KnockoutFixtureDTO,
    ) -> tuple[int | None, int | None]:
        result = await self._infer_repo.get_authoritative_result(fixture.fixture_id)
        if result is None or (result.home_team_id, result.away_team_id) != (
            fixture.home_team_id, fixture.away_team_id
        ):
            return None, None
        return result.winner()

    async def _resolve_final_winner(
        self, final_fixtures: list[KnockoutFixtureDTO]
    ) -> tuple[int | None, int | None]:
        if len(final_fixtures) not in {1, 2}:
            return None, None
        if len(final_fixtures) == 1:
            return await self._resolve_fixture_winner(final_fixtures[0])
        first, last = final_fixtures
        if (first.home_team_id, first.away_team_id) != (last.away_team_id, last.home_team_id):
            return None, None
        results = []
        for fixture in final_fixtures:
            result = await self._infer_repo.get_authoritative_result(fixture.fixture_id)
            if (result is None or not result.verified or result.status not in FINAL_STATUSES
                    or result.home_goals is None or result.away_goals is None
                    or min(result.home_goals, result.away_goals) < 0
                    or (result.home_team_id, result.away_team_id) != (
                        fixture.home_team_id, fixture.away_team_id)):
                return None, None
            results.append(result)
        if results[0].status == "PEN":
            return None, None
        a, b = first.home_team_id, first.away_team_id
        a_goals = results[0].home_goals + results[1].away_goals
        b_goals = results[0].away_goals + results[1].home_goals
        if a_goals != b_goals:
            if results[1].status == "PEN":
                return None, None
            return (a, b) if a_goals > b_goals else (b, a)
        # Only the return leg's verified shootout breaks an aggregate tie.
        last_result = results[1]
        if last_result.status != "PEN":
            return None, None
        h, v = last_result.home_penalty_goals, last_result.away_penalty_goals
        if h is None or v is None or min(h, v) < 0 or h == v:
            return None, None
        return (last.home_team_id, last.away_team_id) if h > v else (last.away_team_id, last.home_team_id)


class InferAllCompetitionAchievementsUseCase:
    def __init__(
        self,
        infer_repo: InferAchievementsRepositoryPort,
        achievement_repo: CompetitionAchievementRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._infer_repo = infer_repo
        self._achievement_repo = achievement_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        season: str,
        rules_version_id: int,
    ) -> InferAllAchievementsResult:
        competition_ids = await self._infer_repo.get_all_knockout_competition_ids(season)
        logger.info(
            "[InferAllCompetitionAchievementsUseCase] season=%s found %d KO competitions",
            season, len(competition_ids),
        )

        competitions_processed = 0
        competitions_skipped = 0
        total_upserted = 0

        single_uc = InferCompetitionAchievementsUseCase(
            infer_repo=self._infer_repo,
            achievement_repo=self._achievement_repo,
            rules_version_repo=self._rules_version_repo,
        )

        for competition_id in competition_ids:
            result = await single_uc.execute(
                competition_id=competition_id,
                season=season,
                rules_version_id=rules_version_id,
            )
            if result.skipped:
                competitions_skipped += 1
            else:
                competitions_processed += 1
                total_upserted += result.achievements_upserted

        logger.info(
            "[InferAllCompetitionAchievementsUseCase] DONE season=%s "
            "processed=%d skipped=%d total_upserted=%d",
            season, competitions_processed, competitions_skipped, total_upserted,
        )
        return InferAllAchievementsResult(
            season=season,
            competitions_processed=competitions_processed,
            competitions_skipped=competitions_skipped,
            total_achievements_upserted=total_upserted,
        )
