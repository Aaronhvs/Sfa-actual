from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sfa.domain.infer_achievements_ports import (
    InferAchievementsRepositoryPort,
    InferAchievementsResult,
    InferAllAchievementsResult,
    KnockoutFixtureDTO,
)
from sfa.domain.scoring.entities import CompetitionAchievement
from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)

logger = logging.getLogger(__name__)

COMPETITION_CATEGORY_MAP: dict[str, str] = {
    "World Cup":             "world_cup",
    "Champions League":      "champions_league",
    "Europa League":         "europa_league",
    "Conference League":     "conference_league",
    "FA Cup":                "domestic_cup_major",
    "Copa del Rey":          "domestic_cup_major",
    "DFB-Pokal":             "domestic_cup_major",
    "Coppa Italia":          "domestic_cup_major",
    "Coupe de France":       "domestic_cup_major",
    "EFL Cup":               "domestic_cup_minor",
    "Community Shield":      "domestic_cup_minor",
    "Supercopa de España":   "domestic_cup_minor",
    "Supercoppa Italiana":   "domestic_cup_minor",
    "DFL-Supercup":          "domestic_cup_minor",
    "Trophée des Champions": "domestic_cup_minor",
    "UEFA Super Cup":        "domestic_cup_minor",
}

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
        category = COMPETITION_CATEGORY_MAP.get(competition_name)
        if category is None:
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

        sorted_stages = sorted(known_stages, key=lambda s: STAGE_ORDER[s], reverse=True)
        phase_teams: dict[str, set[int]] = {}

        if "final" in teams_at_stage:
            final_fixtures = [fx for fx in fixtures if fx.stage == "final"]
            winner_id, runner_up_id = await self._resolve_final_winner(final_fixtures)
            if winner_id is not None and runner_up_id is not None:
                phase_teams["winner"] = {winner_id}
                phase_teams["runner_up"] = {runner_up_id}
            else:
                logger.info(
                    "[InferCompetitionAchievementsUseCase] competition_id=%d season=%s: "
                    "final winner undetermined, skipping winner/runner_up phases",
                    competition_id, season,
                )

        for stage in sorted_stages:
            if stage == "final":
                continue
            # Find the immediately next higher stage (minimum order still greater than current)
            next_higher = min(
                (s for s in known_stages if STAGE_ORDER[s] > STAGE_ORDER[stage]),
                key=lambda s: STAGE_ORDER[s],
                default=None,
            )
            next_teams = teams_at_stage.get(next_higher, set()) if next_higher else set()
            eliminated = teams_at_stage[stage] - next_teams
            phase = STAGE_TO_PHASE[stage]
            phase_teams.setdefault(phase, set()).update(eliminated)

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

    async def _resolve_final_winner(
        self, final_fixtures: list[KnockoutFixtureDTO]
    ) -> tuple[int | None, int | None]:
        home_ids: set[int] = set()
        away_ids: set[int] = set()
        for fx in final_fixtures:
            home_ids.add(fx.home_team_id)
            away_ids.add(fx.away_team_id)

        all_teams = home_ids | away_ids
        if len(all_teams) != 2:
            logger.warning(
                "[InferCompetitionAchievementsUseCase] final has unexpected teams %s, skipping",
                all_teams,
            )
            return None, None

        team_a, team_b = sorted(all_teams)
        scores: dict[int, int] = {team_a: 0, team_b: 0}

        for fx in final_fixtures:
            goals = await self._infer_repo.get_goals_for_fixture(fx.fixture_id)
            for team_id, count in goals.items():
                if team_id in scores:
                    scores[team_id] = scores[team_id] + count

        if scores[team_a] != scores[team_b]:
            winner = team_a if scores[team_a] > scores[team_b] else team_b
            runner_up = team_b if winner == team_a else team_a
            return winner, runner_up

        # Tiebreaker: shootout goals
        shootout: dict[int, int] = {team_a: 0, team_b: 0}
        for fx in final_fixtures:
            sg = await self._infer_repo.get_shootout_goals_for_fixture(fx.fixture_id)
            for team_id, count in sg.items():
                if team_id in shootout:
                    shootout[team_id] = shootout[team_id] + count

        if shootout[team_a] != shootout[team_b]:
            winner = team_a if shootout[team_a] > shootout[team_b] else team_b
            runner_up = team_b if winner == team_a else team_a
            return winner, runner_up

        # No goal data available — cannot determine winner, skip to preserve manual entries
        logger.warning(
            "[InferCompetitionAchievementsUseCase] Cannot determine final winner "
            "from goals or shootout (all 0). Skipping winner/runner_up — "
            "manual achievements preserved. teams=%s",
            all_teams,
        )
        return None, None


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
