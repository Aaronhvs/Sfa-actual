from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ingestion_ports import PlayerSeasonScoreRow, ScoringRepositoryPort
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore


class ScoringRepository(ScoringRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_competition_ids_with_season(self, season: str) -> list[int]:
        stmt = (
            select(Fixture.competition_id)
            .where(Fixture.season == season)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_player_scores_for_competition(
        self, competition_id: int, season: str,
    ) -> list[PlayerSeasonScoreRow]:
        # --- Query 1: sum pts and count per (player_id, event_type) ---
        pts_stmt = (
            select(
                PlayerEvent.player_id,
                PlayerEvent.event_type,
                func.sum(PlayerEvent.pts).label("total_pts"),
                func.count(PlayerEvent.id).label("event_count"),
                func.count(PlayerEvent.fixture_id.distinct()).label("fixtures_with_events"),
            )
            .join(Fixture, PlayerEvent.fixture_id == Fixture.id)
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
            .group_by(PlayerEvent.player_id, PlayerEvent.event_type)
        )
        pts_result = await self._session.execute(pts_stmt)
        pts_rows = pts_result.all()

        # Aggregate into per-player breakdown
        player_totals: dict[int, float] = defaultdict(float)
        player_breakdown: dict[int, dict] = defaultdict(dict)

        for player_id, event_type, total_pts, event_count, _ in pts_rows:
            pts_val = float(total_pts)
            player_totals[player_id] += pts_val
            player_breakdown[player_id][event_type.value] = {
                "count": event_count,
                "pts": round(pts_val, 2),
            }

        if not player_totals:
            return []

        # --- Query 2: sum minutes and count distinct fixtures per player ---
        stats_stmt = (
            select(
                PlayerStats.player_id,
                func.sum(PlayerStats.minutes).label("total_minutes"),
                func.count(PlayerStats.fixture_id.distinct()).label("matches_played"),
            )
            .join(Fixture, PlayerStats.fixture_id == Fixture.id)
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerStats.minutes >= 1,
            )
            .group_by(PlayerStats.player_id)
        )
        stats_result = await self._session.execute(stats_stmt)
        stats_rows = {row[0]: (int(row[1]), int(row[2])) for row in stats_result.all()}

        rows: list[PlayerSeasonScoreRow] = []
        for player_id, total_pts in player_totals.items():
            total_minutes, matches_played = stats_rows.get(player_id, (0, 0))
            rows.append(PlayerSeasonScoreRow(
                player_id=player_id,
                total_pts=round(total_pts, 2),
                matches_played=matches_played,
                breakdown=player_breakdown[player_id],
                total_minutes=total_minutes,
            ))
        return rows

    async def upsert_season_score(
        self,
        player_id: int,
        competition_id: int,
        season: str,
        total_pts: float,
        matches_played: int,
        breakdown: dict,
        rules_version_id: int | None = None,
        team_id: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if team_id is None:
            team_id = (
                await self._session.execute(
                    select(Player.team_id).where(Player.id == player_id)
                )
            ).scalar_one_or_none()
        insert_stmt = pg_insert(SFASeasonScore).values(
            player_id=player_id,
            competition_id=competition_id,
            team_id=team_id,
            season=season,
            rules_version_id=rules_version_id,
            total_pts=round(total_pts, 2),
            matches_played=matches_played,
            breakdown=breakdown,
            last_updated=now,
        )
        stmt = insert_stmt.on_conflict_do_update(
                index_where=(
                    SFASeasonScore.rules_version_id.is_(None)
                    if rules_version_id is None
                    else SFASeasonScore.rules_version_id.isnot(None)
                ),
                index_elements=(
                    ["player_id", "competition_id", "season"]
                    if rules_version_id is None
                    else ["player_id", "competition_id", "season", "rules_version_id"]
                ),
                set_={
                    "team_id": insert_stmt.excluded.team_id,
                    "total_pts": round(total_pts, 2),
                    "matches_played": matches_played,
                    "breakdown": breakdown,
                    "last_updated": now,
                },
        )
        await self._session.execute(stmt)
        await self._session.flush()
