from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.fixture_detail_ports import (
    FixtureDetailDTO,
    FixtureDetailRepositoryProtocol,
    FixtureLineupPlayerDTO,
    FixtureSFAMomentumBucketDTO,
    FixtureStatisticDTO,
    FixtureSummaryDTO,
    FixtureTeamDTO,
    FixtureTeamLineupDTO,
    FixtureTimelineEventDTO,
    FixtureVenueDTO,
)
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixture_events.models import FixtureEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.ingestion_repository import (
    _normalize_fixture_event_type,
)

logger = logging.getLogger(__name__)

_DETAIL_LIVE_TTL_SECONDS = 45
_DETAIL_UPCOMING_TTL_SECONDS = 120
_DETAIL_COMPLETED_TTL_SECONDS = 21600
_COMPLETED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}
_LIVE_STATUSES = {"1H", "2H", "HT", "ET", "BT", "P", "INT", "LIVE"}


class FixtureDetailRepository(FixtureDetailRepositoryProtocol):
    def __init__(
        self,
        provider: APIFootballProvider,
        redis: aioredis.Redis,
        session: AsyncSession,
    ) -> None:
        self._provider = provider
        self._redis = redis
        self._session = session

    async def get_fixture_detail(
        self,
        fixture_external_id: int,
    ) -> FixtureDetailDTO | None:
        cache_key = f"fixture:api:supplement:v2:{fixture_external_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            detail = self._detail_from_dict(json.loads(cached))
            return await self.attach_sfa_scores(detail)

        try:
            detail = await self._provider.fetch_fixture_detail(fixture_external_id)
        except Exception:
            logger.exception(
                "[FixtureDetailRepository] Supplement fetch failed fixture=%d",
                fixture_external_id,
            )
            return None
        if detail is None:
            return None

        if detail.fixture.status in _COMPLETED_STATUSES:
            ttl = _DETAIL_COMPLETED_TTL_SECONDS
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
            "[FixtureDetailRepository] Cached fixture=%d ttl=%d",
            fixture_external_id,
            ttl,
        )
        return await self.attach_sfa_scores(detail)

    async def attach_sfa_scores(
        self,
        detail: FixtureDetailDTO,
    ) -> FixtureDetailDTO:
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

        def enrich(player: FixtureLineupPlayerDTO) -> FixtureLineupPlayerDTO:
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
    async def get_fixture_events(
        self,
        fixture_external_id: int,
    ) -> list[FixtureTimelineEventDTO]:
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
        stored = [
            FixtureTimelineEventDTO(
                minute=row.minute,
                extra_minute=row.extra_minute,
                team_external_id=row.team_external_id,
                event_type=row.event_type,
                player_name=row.player_name,
                assist_name=row.assist_name,
            )
            for row in rows
        ]
        if stored:
            return stored

        try:
            raw_events = await self._provider.fetch_fixture_events(
                fixture_external_id,
            )
        except Exception:
            logger.exception(
                "[FixtureDetailRepository] Event fetch failed fixture=%d",
                fixture_external_id,
            )
            return []
        events: list[FixtureTimelineEventDTO] = []
        for raw in raw_events:
            event_type = _normalize_fixture_event_type(raw.type, raw.detail)
            if event_type is None:
                continue
            events.append(
                FixtureTimelineEventDTO(
                    minute=raw.minute,
                    extra_minute=raw.extra_minute,
                    team_external_id=raw.team_external_id,
                    event_type=event_type,
                    player_name=raw.player_name,
                    assist_name=raw.assist_name,
                )
            )
        return events

    async def get_fixture_sfa_momentum(
        self,
        fixture_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> list[FixtureSFAMomentumBucketDTO]:
        active_version_subq = (
            select(ScoringRulesVersion.id)
            .where(ScoringRulesVersion.is_active.is_(True))
            .limit(1)
            .scalar_subquery()
        )
        bucket_start = (
            func.floor((PlayerEvent.minute - 1) / 5) * 5
        ).cast(Integer).label("minute_start")
        rows = (
            await self._session.execute(
                select(
                    bucket_start,
                    func.sum(
                        case(
                            (
                                PlayerEvent.team_id == home_team_id,
                                PlayerEventScore.final_points,
                            ),
                            else_=0,
                        )
                    ).label("home_points"),
                    func.sum(
                        case(
                            (
                                PlayerEvent.team_id == away_team_id,
                                PlayerEventScore.final_points,
                            ),
                            else_=0,
                        )
                    ).label("away_points"),
                )
                .join(
                    PlayerEventScore,
                    PlayerEventScore.event_id == PlayerEvent.id,
                )
                .where(
                    PlayerEvent.fixture_id == fixture_id,
                    PlayerEvent.minute >= 1,
                    PlayerEvent.team_id.in_((home_team_id, away_team_id)),
                    PlayerEventScore.rules_version_id == active_version_subq,
                    PlayerEventScore.action_type != "stats",
                )
                .group_by(bucket_start)
                .order_by(bucket_start)
            )
        ).mappings().all()
        if not rows:
            return []
        points_by_bucket = {row["minute_start"]: row for row in rows}
        last_bucket = max(points_by_bucket)
        return [
            FixtureSFAMomentumBucketDTO(
                minute_start=minute_start,
                minute_end=minute_start + 5,
                home_points=round(
                    float(
                        (points_by_bucket.get(minute_start) or {}).get(
                            "home_points",
                        )
                        or 0
                    ),
                    2,
                ),
                away_points=round(
                    float(
                        (points_by_bucket.get(minute_start) or {}).get(
                            "away_points",
                        )
                        or 0
                    ),
                    2,
                ),
            )
            for minute_start in range(0, last_bucket + 1, 5)
        ]

    @staticmethod
    def _fixture_to_dict(fixture: FixtureSummaryDTO) -> dict:
        return {
            **fixture.__dict__,
            "played_at": fixture.played_at.isoformat(),
            "home_team": fixture.home_team.__dict__,
            "away_team": fixture.away_team.__dict__,
        }

    @staticmethod
    def _fixture_from_dict(data: dict) -> FixtureSummaryDTO:
        return FixtureSummaryDTO(
            **{
                **data,
                "played_at": datetime.fromisoformat(data["played_at"]),
                "home_team": FixtureTeamDTO(**data["home_team"]),
                "away_team": FixtureTeamDTO(**data["away_team"]),
            }
        )

    @classmethod
    def _detail_to_dict(cls, detail: FixtureDetailDTO) -> dict:
        return {
            "fixture": cls._fixture_to_dict(detail.fixture),
            "venue": detail.venue.__dict__,
            "referee": detail.referee,
            "lineups": [
                {
                    **lineup.__dict__,
                    "team": lineup.team.__dict__,
                    "start_xi": [player.__dict__ for player in lineup.start_xi],
                    "substitutes": [
                        player.__dict__ for player in lineup.substitutes
                    ],
                }
                for lineup in detail.lineups
            ],
            "statistics": [item.__dict__ for item in detail.statistics],
        }

    @classmethod
    def _detail_from_dict(cls, data: dict) -> FixtureDetailDTO:
        return FixtureDetailDTO(
            fixture=cls._fixture_from_dict(data["fixture"]),
            venue=FixtureVenueDTO(**data["venue"]),
            referee=data.get("referee"),
            lineups=[
                FixtureTeamLineupDTO(
                    team=FixtureTeamDTO(**lineup["team"]),
                    formation=lineup.get("formation"),
                    coach_name=lineup.get("coach_name"),
                    coach_photo=lineup.get("coach_photo"),
                    start_xi=[
                        FixtureLineupPlayerDTO(**player)
                        for player in lineup.get("start_xi", [])
                    ],
                    substitutes=[
                        FixtureLineupPlayerDTO(**player)
                        for player in lineup.get("substitutes", [])
                    ],
                )
                for lineup in data.get("lineups", [])
            ],
            statistics=[
                FixtureStatisticDTO(**item)
                for item in data.get("statistics", [])
            ],
            events=[],
        )
