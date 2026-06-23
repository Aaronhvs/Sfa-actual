from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import RankedPlayerDTO
from sfa.domain.player_position_overrides import position_for_context
from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixtureDTO,
    WorldCupFixtureEventDTO,
    WorldCupLineupPlayerDTO,
    WorldCupRepositoryProtocol,
    WorldCupStandingDTO,
    WorldCupStatisticDTO,
    WorldCupTeamDTO,
    WorldCupTeamLineupDTO,
    WorldCupVenueDTO,
    WcTeamProfileDTO,
    WcTeamSFARankingDTO,
)
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.models.fixture_events.models import FixtureEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.ingestion_repository import _normalize_fixture_event_type

logger = logging.getLogger(__name__)

_WC_COMPETITION_ID = 350
_FIXTURES_TTL_SECONDS = 600
_STANDINGS_TTL_SECONDS = 3600
_DETAIL_LIVE_TTL_SECONDS = 45        # in-progress: show events within ~45s
_DETAIL_UPCOMING_TTL_SECONDS = 120   # pre-match: recheck every 2 min
_DETAIL_DEFAULT_TTL_SECONDS = 21600  # completed: cache 6h
_COMPLETED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}
_LIVE_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "INT", "LIVE"}


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

        if detail.fixture.status in _COMPLETED_STATUSES:
            ttl = _DETAIL_DEFAULT_TTL_SECONDS
        elif detail.fixture.status in _LIVE_STATUSES:
            ttl = _DETAIL_LIVE_TTL_SECONDS
        else:
            ttl = _DETAIL_UPCOMING_TTL_SECONDS
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
            events=[],
        )

    async def get_fixture_events(
        self, fixture_external_id: int,
    ) -> list[WorldCupFixtureEventDTO]:
        rows = (
            await self._session.execute(
                select(FixtureEvent)
                .where(FixtureEvent.fixture_external_id == fixture_external_id)
                .order_by(
                    FixtureEvent.minute,
                    FixtureEvent.extra_minute,
                    FixtureEvent.source_sequence.nulls_last(),
                )
            )
        ).scalars().all()

        stored_events = [
            WorldCupFixtureEventDTO(
                minute=row.minute,
                extra_minute=row.extra_minute,
                team_external_id=row.team_external_id,
                event_type=row.event_type,
                player_name=row.player_name,
                assist_name=row.assist_name,
            )
            for row in rows
        ]

        if stored_events:
            return stored_events

        raw_events = await self._provider.fetch_fixture_events(fixture_external_id)
        live_events: list[WorldCupFixtureEventDTO] = []
        for raw in raw_events:
            event_type = _normalize_fixture_event_type(raw.type, raw.detail)
            if event_type is None:
                continue
            live_events.append(
                WorldCupFixtureEventDTO(
                    minute=raw.minute,
                    extra_minute=raw.extra_minute,
                    team_external_id=raw.team_external_id,
                    event_type=event_type,
                    player_name=raw.player_name,
                    assist_name=raw.assist_name,
                )
            )

        return live_events

    async def get_wc_team_sfa_ranking(
        self, season: str, rules_version_id: int | None,
    ) -> list[WcTeamSFARankingDTO]:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )

        def _jint(key: str) -> object:
            return func.coalesce(cast(SFASeasonScore.breakdown[key]["count"].astext, Integer), 0)

        total_goals_expr = func.sum(_jint("goal") + _jint("goal_penalty"))

        stmt = (
            select(
                Team.external_id.label("team_external_id"),
                Team.name.label("team_name"),
                func.sum(SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts).label("total_sfa_pts"),
                func.count(SFASeasonScore.player_id.distinct()).label("player_count"),
                total_goals_expr.label("total_goals"),
            )
            .join(Team, SFASeasonScore.team_id == Team.id)
            .where(
                SFASeasonScore.competition_id == _WC_COMPETITION_ID,
                SFASeasonScore.season == season,
                rv_filter,
            )
            .group_by(Team.external_id, Team.name)
            .order_by(func.sum(SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts).desc())
        )

        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            WcTeamSFARankingDTO(
                rank=idx + 1,
                team_external_id=row["team_external_id"],
                team_name=row["team_name"],
                total_sfa_pts=round(float(row["total_sfa_pts"]), 2),
                total_goals=int(row["total_goals"]),
                player_count=int(row["player_count"]),
            )
            for idx, row in enumerate(rows)
        ]

    async def get_wc_team_profile(
        self, team_external_id: int, season: str, rules_version_id: int | None,
    ) -> WcTeamProfileDTO | None:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )

        team_row = (
            await self._session.execute(
                select(Team.id.label("team_id"), Team.name.label("team_name"))
                .where(Team.external_id == team_external_id)
                .limit(1)
            )
        ).mappings().first()

        if team_row is None:
            return None

        team_id = team_row["team_id"]
        team_name = team_row["team_name"]

        def _jint(key: str) -> object:
            return func.coalesce(cast(SFASeasonScore.breakdown[key]["count"].astext, Integer), 0)

        summary = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts),
                        0,
                    ).label("total_sfa_pts"),
                    func.coalesce(
                        func.sum(_jint("goal") + _jint("goal_penalty")),
                        0,
                    ).label("total_goals"),
                )
                .where(
                    SFASeasonScore.competition_id == _WC_COMPETITION_ID,
                    SFASeasonScore.season == season,
                    SFASeasonScore.team_id == team_id,
                    rv_filter,
                )
            )
        ).mappings().first()

        if summary is None or summary["total_sfa_pts"] == 0:
            return None

        top_rows = (
            await self._session.execute(
                select(
                    Player.id.label("player_id"),
                    Player.name.label("player_name"),
                    Player.position,
                    Player.photo_url,
                    (SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts).label("total_pts"),
                    SFASeasonScore.matches_played,
                    (_jint("goal") + _jint("goal_penalty")).label("goals"),
                    (_jint("assist") + _jint("corner_assist")).label("assists"),
                )
                .join(Player, SFASeasonScore.player_id == Player.id)
                .where(
                    SFASeasonScore.competition_id == _WC_COMPETITION_ID,
                    SFASeasonScore.season == season,
                    SFASeasonScore.team_id == team_id,
                    rv_filter,
                )
                .order_by((SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts).desc())
                .limit(5)
            )
        ).mappings().all()

        top_players = [
            RankedPlayerDTO(
                rank=idx + 1,
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=team_name,
                team_logo_url=f"https://media.api-sports.io/football/teams/{team_external_id}.png",
                position=position_for_context(
                    row["position"].value if hasattr(row["position"], "value") else str(row["position"]),
                    player_name=row["player_name"],
                    team_name=team_name,
                    competition_id=_WC_COMPETITION_ID,
                ) or "",
                competition_name="FIFA World Cup 2026",
                total_pts=float(row["total_pts"]),
                matches_played=row["matches_played"],
                photo_url=row["photo_url"],
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
            )
            for idx, row in enumerate(top_rows)
        ]

        return WcTeamProfileDTO(
            team_external_id=team_external_id,
            team_name=team_name,
            total_sfa_pts=round(float(summary["total_sfa_pts"]), 2),
            total_goals=int(summary["total_goals"] or 0),
            top_players=top_players,
        )
