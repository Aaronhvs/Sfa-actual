from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.enrichment_ports import (
    EnrichmentRepositoryPort,
    PlayerEnrichDTO,
    PlayerEventRecalcRow,
    PlayerEventRow,
    PlayerSeasonEventRow,
    PlayerStatsEventRecalcRow,
    SeasonScoreRow,
)
from sfa.infrastructure.models.competitions.models import CompetitionStage
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore


class EnrichmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_players_by_competition(
        self, competition_id: int, season: str,
    ) -> list[PlayerEnrichDTO]:
        stmt = (
            select(
                Player.id,
                Player.name,
                Player.external_id,
                Player.fbref_id,
                Player.understat_id,
            )
            .join(PlayerStats, PlayerStats.player_id == Player.id)
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(
                Fixture.competition_id == competition_id,
                PlayerStats.season == season,
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [
            PlayerEnrichDTO(
                id=row[0],
                name=row[1],
                external_id=row[2],
                fbref_id=row[3],
                understat_id=row[4],
            )
            for row in result.fetchall()
        ]

    async def get_player_events_without_psxg(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerEventRow]:
        stmt = (
            select(
                PlayerEvent.id,
                PlayerEvent.event_type,
                PlayerEvent.minute,
                PlayerEvent.m1,
                PlayerEvent.m2,
                PlayerEvent.m3,
                PlayerEvent.mvisit,
            )
            .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
            .where(
                PlayerEvent.player_id == player_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerEvent.psxg.is_(None),
                PlayerEvent.event_type.in_([EventType.GOAL, EventType.GOAL_PENALTY]),
            )
        )
        result = await self._session.execute(stmt)
        return [
            PlayerEventRow(
                id=row[0],
                event_type=row[1].value if hasattr(row[1], "value") else str(row[1]),
                minute=row[2],
                m1=float(row[3]),
                m2=float(row[4]),
                m3=float(row[5]),
                mvisit=float(row[6]),
            )
            for row in result.fetchall()
        ]

    async def update_player_external_ids(
        self, player_id: int,
        fbref_id: str | None = None,
        understat_id: int | None = None,
    ) -> None:
        if fbref_id is not None:
            await self._session.execute(
                update(Player)
                .where(Player.id == player_id, Player.fbref_id.is_(None))
                .values(fbref_id=fbref_id)
            )
        if understat_id is not None:
            await self._session.execute(
                update(Player)
                .where(Player.id == player_id, Player.understat_id.is_(None))
                .values(understat_id=understat_id)
            )
        await self._session.flush()

    async def update_player_stats_from_fbref(
        self, player_id: int, season: str, stats: dict,
    ) -> None:
        """
        Update player_stats fields from FBref data, only overwriting fields
        that are currently 0 (API-Football did not provide them).
        """
        set_clauses: dict = {}
        for field, val in stats.items():
            col = getattr(PlayerStats, field, None)
            if col is None:
                continue
            # CASE WHEN field = 0 THEN :val ELSE field END
            set_clauses[field] = case(
                (col == 0, val),
                else_=col,
            )

        if not set_clauses:
            return

        await self._session.execute(
            update(PlayerStats)
            .where(
                PlayerStats.player_id == player_id,
                PlayerStats.season == season,
            )
            .values(**set_clauses)
        )
        await self._session.flush()

    async def update_event_psxg(self, event_id: int, psxg: float) -> None:
        await self._session.execute(
            update(PlayerEvent)
            .where(PlayerEvent.id == event_id)
            .values(psxg=psxg)
        )
        await self._session.flush()

    async def update_event_scores(
        self, event_id: int, m4: float, pts: float,
    ) -> None:
        await self._session.execute(
            update(PlayerEvent)
            .where(PlayerEvent.id == event_id)
            .values(m4=m4, pts=pts)
        )
        await self._session.flush()

    async def update_season_score(
        self, player_id: int, competition_id: int,
        season: str, total_pts: float,
        matches_played: int, breakdown: dict,
    ) -> None:
        await self._session.execute(
            update(SFASeasonScore)
            .where(
                SFASeasonScore.player_id == player_id,
                SFASeasonScore.competition_id == competition_id,
                SFASeasonScore.season == season,
            )
            .values(
                total_pts=total_pts,
                matches_played=matches_played,
                breakdown=breakdown,
                last_updated=datetime.now(timezone.utc),
            )
        )
        await self._session.flush()

    async def get_events_with_psxg_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerEventRecalcRow]:
        stmt = (
            select(
                PlayerEvent.id,
                PlayerEvent.player_id,
                Player.position,
                PlayerEvent.event_type,
                PlayerEvent.fixture_id,
                PlayerEvent.m1,
                PlayerEvent.m2,
                PlayerEvent.m3,
                PlayerEvent.mvisit,
                PlayerEvent.psxg,
                PlayerEvent.pts,
            )
            .join(Player, Player.id == PlayerEvent.player_id)
            .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerEvent.psxg.is_not(None),
            )
        )
        result = await self._session.execute(stmt)
        return [
            PlayerEventRecalcRow(
                id=row[0],
                player_id=row[1],
                player_position=row[2].value if hasattr(row[2], "value") else str(row[2]),
                event_type=row[3].value if hasattr(row[3], "value") else str(row[3]),
                fixture_id=row[4],
                m1=float(row[5]),
                m2=float(row[6]),
                m3=float(row[7]),
                mvisit=float(row[8]),
                psxg=float(row[9]),
                current_pts=float(row[10]),
            )
            for row in result.fetchall()
        ]

    async def get_stats_events_for_recalc(
        self, competition_id: int, season: str,
    ) -> list[PlayerStatsEventRecalcRow]:
        stmt = (
            select(
                PlayerEvent.id,           # 0
                PlayerEvent.player_id,    # 1
                Player.position,          # 2
                PlayerEvent.m1,           # 3
                func.coalesce(CompetitionStage.stage_factor, 1.0),  # 4 — real stage_factor
                PlayerEvent.pts,          # 5
                PlayerStats.duels_won,    # 6
                PlayerStats.tackles_won,  # 7
                PlayerStats.interceptions,  # 8
                PlayerStats.blocks,       # 9
                PlayerStats.dribbles_won,  # 10
                PlayerStats.passes_key,   # 11
                PlayerStats.passes_total,  # 12
                PlayerStats.passes_accuracy,  # 13
                PlayerStats.shots_on,     # 14
                PlayerStats.shots_total,  # 15
                PlayerStats.dribbles_past,  # 16
                PlayerStats.duels_total,  # 17
                PlayerStats.fouls_drawn,  # 18
                PlayerStats.fouls_committed,  # 19
                PlayerStats.cards_yellow,  # 20
                PlayerStats.cards_red,    # 21
                PlayerStats.penalty_won,  # 22
                PlayerStats.goals,        # 23
                PlayerStats.assists,      # 24
                PlayerStats.rating,       # 25
            )
            .join(Player, Player.id == PlayerEvent.player_id)
            .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
            .join(
                PlayerStats,
                (PlayerStats.player_id == PlayerEvent.player_id)
                & (PlayerStats.fixture_id == PlayerEvent.fixture_id),
            )
            .outerjoin(
                CompetitionStage,
                (CompetitionStage.competition_id == Fixture.competition_id)
                & (CompetitionStage.stage == Fixture.stage),
            )
            .where(
                Fixture.competition_id == competition_id,
                Fixture.season == season,
                PlayerEvent.event_type == EventType.STATS,
            )
        )
        result = await self._session.execute(stmt)
        return [
            PlayerStatsEventRecalcRow(
                event_id=row[0],
                player_id=row[1],
                player_position=row[2].value if hasattr(row[2], "value") else str(row[2]),
                m1=float(row[3]),
                m2=float(row[4]),
                current_pts=float(row[5]),
                duels_won=int(row[6]),
                tackles_won=int(row[7]),
                interceptions=int(row[8]),
                blocks=int(row[9]),
                dribbles_won=int(row[10]),
                passes_key=int(row[11]),
                passes_total=int(row[12]),
                passes_accuracy=int(row[13]),
                shots_on=int(row[14]),
                shots_total=int(row[15]),
                dribbles_past=int(row[16]),
                duels_total=int(row[17]),
                fouls_drawn=int(row[18]),
                fouls_committed=int(row[19]),
                cards_yellow=int(row[20]),
                cards_red=int(row[21]),
                penalty_won=int(row[22]),
                goals=int(row[23]),
                assists=int(row[24]),
                rating=float(row[25]) if row[25] is not None else None,
            )
            for row in result.fetchall()
        ]

    async def update_event_pts(self, event_id: int, pts: float, m2: float | None = None) -> None:
        values: dict = {"pts": pts}
        if m2 is not None:
            values["m2"] = m2
        await self._session.execute(
            update(PlayerEvent)
            .where(PlayerEvent.id == event_id)
            .values(**values)
        )
        await self._session.flush()

    async def get_all_player_season_events(
        self, player_id: int, competition_id: int, season: str,
    ) -> list[PlayerSeasonEventRow]:
        stmt = (
            select(
                PlayerEvent.id,
                PlayerEvent.player_id,
                PlayerEvent.fixture_id,
                PlayerEvent.event_type,
                PlayerEvent.pts,
            )
            .join(Fixture, Fixture.id == PlayerEvent.fixture_id)
            .where(
                PlayerEvent.player_id == player_id,
                Fixture.competition_id == competition_id,
                Fixture.season == season,
            )
        )
        result = await self._session.execute(stmt)
        return [
            PlayerSeasonEventRow(
                id=row[0],
                player_id=row[1],
                fixture_id=row[2],
                event_type=row[3].value if hasattr(row[3], "value") else str(row[3]),
                pts=float(row[4]),
            )
            for row in result.fetchall()
        ]

    async def get_player_season_real_stats(
        self, player_id: int, competition_id: int, season: str,
    ) -> tuple[int, int]:
        stmt = (
            select(
                func.coalesce(func.sum(PlayerStats.goals), 0).label("goals"),
                func.coalesce(func.sum(PlayerStats.assists), 0).label("assists"),
            )
            .join(Fixture, Fixture.id == PlayerStats.fixture_id)
            .where(
                PlayerStats.player_id == player_id,
                PlayerStats.season == season,
                Fixture.competition_id == competition_id,
            )
        )
        row = (await self._session.execute(stmt)).mappings().first()
        if row is None:
            return (0, 0)
        return (int(row["goals"]), int(row["assists"]))

    async def get_player_season_score_row(
        self, player_id: int, competition_id: int, season: str,
    ) -> SeasonScoreRow | None:
        stmt = select(
            SFASeasonScore.player_id,
            SFASeasonScore.competition_id,
            SFASeasonScore.season,
            SFASeasonScore.total_pts,
            SFASeasonScore.matches_played,
            SFASeasonScore.breakdown,
        ).where(
            SFASeasonScore.player_id == player_id,
            SFASeasonScore.competition_id == competition_id,
            SFASeasonScore.season == season,
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row is None:
            return None
        return SeasonScoreRow(
            player_id=row[0],
            competition_id=row[1],
            season=row[2],
            total_pts=float(row[3]),
            matches_played=row[4],
            breakdown=dict(row[5]) if row[5] else {},
        )
