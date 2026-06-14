from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixtureDTO,
    WorldCupLineupPlayerDTO,
    WorldCupRepositoryProtocol,
    WorldCupStandingDTO,
    WorldCupStatisticDTO,
    WorldCupTeamDTO,
    WorldCupTeamLineupDTO,
    WorldCupVenueDTO,
)
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion

logger = logging.getLogger(__name__)

_FIXTURES_TTL_SECONDS = 30
_STANDINGS_TTL_SECONDS = 300
_DETAIL_LIVE_TTL_SECONDS = 60
_DETAIL_DEFAULT_TTL_SECONDS = 900
_LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}


class WorldCupRepository(WorldCupRepositoryProtocol):
    def __init__(
        self,
        provider: APIFootballProvider,
        redis: aioredis.Redis,
        session: AsyncSession,
        league_id: int = 1,
    ) -> None:
        self._provider = provider
        self._redis = redis
        self._session = session
        self._league_id = league_id

    async def get_fixtures(self, season: str) -> list[WorldCupFixtureDTO]:
        cache_key = f"wc:api:fixtures:{season}"
        cached = await self._redis.get(cache_key)
        if cached:
            return [self._fixture_from_dict(item) for item in json.loads(cached)]

        fixtures = await self._provider.fetch_world_cup_fixtures(
            league_id=self._league_id,
            season=int(season),
        )
        payload = [self._fixture_to_dict(item) for item in fixtures]
        await self._redis.setex(cache_key, _FIXTURES_TTL_SECONDS, json.dumps(payload))
        logger.info(
            "[WorldCupRepository] Cached %d fixtures for season=%s",
            len(fixtures),
            season,
        )
        return fixtures

    async def get_standings(self, season: str) -> list[WorldCupStandingDTO]:
        cache_key = f"wc:api:standings:{season}"
        cached = await self._redis.get(cache_key)
        if cached:
            return [self._standing_from_dict(item) for item in json.loads(cached)]

        standings = await self._provider.fetch_world_cup_standings(
            league_id=self._league_id,
            season=int(season),
        )
        payload = [self._standing_to_dict(item) for item in standings]
        await self._redis.setex(cache_key, _STANDINGS_TTL_SECONDS, json.dumps(payload))
        logger.info(
            "[WorldCupRepository] Cached %d standings rows for season=%s",
            len(standings),
            season,
        )
        return standings

    async def get_fixture_detail(
        self,
        fixture_id: int,
    ) -> WorldCupFixtureDetailDTO | None:
        cache_key = f"wc:api:fixture-detail:{fixture_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            detail = self._detail_from_dict(json.loads(cached))
            return await self._attach_sfa_scores(detail)

        detail = await self._provider.fetch_world_cup_fixture_detail(fixture_id)
        if detail is None:
            return None

        ttl = (
            _DETAIL_LIVE_TTL_SECONDS
            if detail.fixture.status in _LIVE_STATUSES
            else _DETAIL_DEFAULT_TTL_SECONDS
        )
        await self._redis.setex(
            cache_key,
            ttl,
            json.dumps(self._detail_to_dict(detail)),
        )
        logger.info(
            "[WorldCupRepository] Cached fixture detail fixture_id=%d ttl=%d",
            fixture_id,
            ttl,
        )
        return await self._attach_sfa_scores(detail)

    async def _attach_sfa_scores(
        self,
        detail: WorldCupFixtureDetailDTO,
    ) -> WorldCupFixtureDetailDTO:
        external_ids = {
            player.external_id
            for lineup in detail.lineups
            for player in (*lineup.start_xi, *lineup.substitutes)
            if player.external_id is not None
        }
        if not external_ids:
            return detail

        active_version_subq = (
            select(ScoringRulesVersion.id)
            .where(ScoringRulesVersion.is_active.is_(True))
            .limit(1)
            .scalar_subquery()
        )
        rows = (
            await self._session.execute(
                select(
                    Player.external_id,
                    Player.id.label("player_id"),
                    func.sum(PlayerEventScore.final_points).label("sfa_points"),
                )
                .join(PlayerEventScore, PlayerEventScore.player_id == Player.id)
                .join(Fixture, Fixture.id == PlayerEventScore.fixture_id)
                .where(Fixture.external_id == detail.fixture.external_id)
                .where(Player.external_id.in_(external_ids))
                .where(PlayerEventScore.rules_version_id == active_version_subq)
                .group_by(Player.external_id, Player.id)
            )
        ).mappings().all()
        scores = {
            row["external_id"]: (
                row["player_id"],
                round(float(row["sfa_points"]), 2),
            )
            for row in rows
        }

        def enrich(player: WorldCupLineupPlayerDTO) -> WorldCupLineupPlayerDTO:
            score = scores.get(player.external_id)
            if score is None:
                return player
            return replace(player, player_id=score[0], sfa_points=score[1])

        return replace(
            detail,
            lineups=[
                replace(
                    lineup,
                    start_xi=[enrich(player) for player in lineup.start_xi],
                    substitutes=[enrich(player) for player in lineup.substitutes],
                )
                for lineup in detail.lineups
            ],
        )

    @staticmethod
    def _fixture_to_dict(fixture: WorldCupFixtureDTO) -> dict:
        return {
            "external_id": fixture.external_id,
            "stage": fixture.stage,
            "matchday": fixture.matchday,
            "played_at": fixture.played_at.isoformat(),
            "status": fixture.status,
            "status_label": fixture.status_label,
            "elapsed": fixture.elapsed,
            "home_team": fixture.home_team.__dict__,
            "away_team": fixture.away_team.__dict__,
            "home_goals": fixture.home_goals,
            "away_goals": fixture.away_goals,
        }

    @staticmethod
    def _fixture_from_dict(data: dict) -> WorldCupFixtureDTO:
        return WorldCupFixtureDTO(
            external_id=data["external_id"],
            stage=data["stage"],
            matchday=data.get("matchday"),
            played_at=datetime.fromisoformat(data["played_at"]),
            status=data["status"],
            status_label=data["status_label"],
            elapsed=data.get("elapsed"),
            home_team=WorldCupTeamDTO(**data["home_team"]),
            away_team=WorldCupTeamDTO(**data["away_team"]),
            home_goals=data.get("home_goals"),
            away_goals=data.get("away_goals"),
        )

    @staticmethod
    def _standing_to_dict(standing: WorldCupStandingDTO) -> dict:
        return {
            **standing.__dict__,
            "team": standing.team.__dict__,
        }

    @staticmethod
    def _standing_from_dict(data: dict) -> WorldCupStandingDTO:
        return WorldCupStandingDTO(
            group=data["group"],
            position=data["position"],
            team=WorldCupTeamDTO(**data["team"]),
            played=data["played"],
            won=data["won"],
            drawn=data["drawn"],
            lost=data["lost"],
            goals_for=data["goals_for"],
            goals_against=data["goals_against"],
            goal_difference=data["goal_difference"],
            points=data["points"],
            form=data.get("form"),
        )

    @classmethod
    def _detail_to_dict(cls, detail: WorldCupFixtureDetailDTO) -> dict:
        return {
            "fixture": cls._fixture_to_dict(detail.fixture),
            "venue": detail.venue.__dict__,
            "referee": detail.referee,
            "lineups": [
                {
                    "team": lineup.team.__dict__,
                    "formation": lineup.formation,
                    "coach_name": lineup.coach_name,
                    "coach_photo": lineup.coach_photo,
                    "start_xi": [player.__dict__ for player in lineup.start_xi],
                    "substitutes": [
                        player.__dict__ for player in lineup.substitutes
                    ],
                }
                for lineup in detail.lineups
            ],
            "statistics": [statistic.__dict__ for statistic in detail.statistics],
        }

    @classmethod
    def _detail_from_dict(cls, data: dict) -> WorldCupFixtureDetailDTO:
        return WorldCupFixtureDetailDTO(
            fixture=cls._fixture_from_dict(data["fixture"]),
            venue=WorldCupVenueDTO(**data["venue"]),
            referee=data.get("referee"),
            lineups=[
                WorldCupTeamLineupDTO(
                    team=WorldCupTeamDTO(**lineup["team"]),
                    formation=lineup.get("formation"),
                    coach_name=lineup.get("coach_name"),
                    coach_photo=lineup.get("coach_photo"),
                    start_xi=[
                        WorldCupLineupPlayerDTO(**player)
                        for player in lineup.get("start_xi", [])
                    ],
                    substitutes=[
                        WorldCupLineupPlayerDTO(**player)
                        for player in lineup.get("substitutes", [])
                    ],
                )
                for lineup in data.get("lineups", [])
            ],
            statistics=[
                WorldCupStatisticDTO(**statistic)
                for statistic in data.get("statistics", [])
            ],
        )
