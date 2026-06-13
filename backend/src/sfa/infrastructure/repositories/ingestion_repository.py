from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ingestion_ports import (
    FixtureInfoRow,
    IngestionLogRow,
    IngestionRepositoryPort,
    PlayerFixtureInfoRow,
)
from sfa.infrastructure.models.competitions.models import Competition, CompetitionStage
from sfa.infrastructure.models.enums import EventType, IngestionStatus, Position
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.ingestion.models import IngestionLog
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.standings.models import StandingSnapshot
from sfa.infrastructure.models.teams.models import Team


class IngestionRepository(IngestionRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_competition(
        self,
        name: str,
        country: str,
        factor: float,
        participant_kind: str = "club",
    ) -> int:
        stmt = (
            pg_insert(Competition)
            .values(
                name=name,
                country=country,
                competition_factor=factor,
                participant_kind=participant_kind,
            )
            .on_conflict_do_update(
                index_elements=["name"],
                set_={
                    "country": country,
                    "competition_factor": factor,
                    "participant_kind": participant_kind,
                },
            )
            .returning(Competition.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def upsert_team(self, external_id: int, name: str, competition_id: int) -> int:
        # First try to link external_id to an already-seeded team by (name, competition_id)
        upd = (
            update(Team)
            .where(Team.name == name, Team.competition_id == competition_id, Team.external_id.is_(None))
            .values(external_id=external_id)
            .returning(Team.id)
        )
        result = await self._session.execute(upd)
        row = result.fetchone()
        if row:
            await self._session.flush()
            return row[0]

        # Otherwise upsert by external_id
        stmt = (
            pg_insert(Team)
            .values(external_id=external_id, name=name, competition_id=competition_id)
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={"name": name, "competition_id": competition_id},
            )
            .returning(Team.id)
        )
        result2 = await self._session.execute(stmt)
        await self._session.flush()
        return result2.scalar_one()

    async def upsert_player(
        self, external_id: int, name: str, position: Position,
        photo_url: str | None = None,
        update_position: bool = True,
        position_source: str = "apifootball",
    ) -> int:
        if external_id <= 0:
            raise ValueError("player external_id must be a positive integer")

        insert_stmt = pg_insert(Player).values(
            external_id=external_id, name=name,
            position=position, photo_url=photo_url, position_source=position_source,
        )
        set_dict = {
            "name": insert_stmt.excluded.name,
            "photo_url": func.coalesce(insert_stmt.excluded.photo_url, Player.photo_url),
        }
        if update_position:
            set_dict["position"] = case(
                (Player.position_source == "transfermarkt", Player.position),
                else_=insert_stmt.excluded.position,
            )
            set_dict["position_source"] = case(
                (Player.position_source == "transfermarkt", Player.position_source),
                else_=position_source,
            )

        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["external_id"],
            set_=set_dict,
        ).returning(Player.id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def upsert_fixture(
        self,
        external_id: int,
        competition_id: int,
        home_team_id: int,
        away_team_id: int,
        stage: str,
        season: str,
        played_at: object,
        matchday: int | None,
    ) -> int:
        stmt = (
            pg_insert(Fixture)
            .values(
                external_id=external_id,
                competition_id=competition_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                stage=stage,
                season=season,
                played_at=played_at,
                matchday=matchday,
            )
            .on_conflict_do_update(
                index_elements=["external_id"],
                set_={"stage": stage, "matchday": matchday},
            )
            .returning(Fixture.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def upsert_standing_snapshot(
        self,
        competition_id: int,
        team_id: int,
        season: str,
        matchday: int,
        position: int,
        points: int,
    ) -> None:
        stmt = (
            pg_insert(StandingSnapshot)
            .values(
                competition_id=competition_id,
                team_id=team_id,
                season=season,
                matchday=matchday,
                position=position,
                points=points,
            )
            .on_conflict_do_update(
                constraint="uq_standing_snapshot",
                set_={"position": position, "points": points},
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_player_event(
        self,
        player_id: int,
        fixture_id: int,
        team_id: int,
        minute: int,
        event_type: EventType,
        score_before: str | None,
        score_diff: int | None,
        psxg: float | None,
        m1: float,
        m2: float,
        m3: float,
        m4: float,
        mvisit: float,
        pts: float,
        player_team_pos: int | None = None,
        rival_team_pos: int | None = None,
        is_away: bool | None = None,
    ) -> None:
        stmt = pg_insert(PlayerEvent).values(
            player_id=player_id,
            fixture_id=fixture_id,
            team_id=team_id,
            minute=minute,
            event_type=event_type,
            score_before=score_before,
            score_diff=score_diff,
            psxg=psxg,
            m1=m1,
            m2=m2,
            m3=m3,
            m4=m4,
            mvisit=mvisit,
            pts=pts,
            player_team_pos=player_team_pos,
            rival_team_pos=rival_team_pos,
            is_away=is_away,
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_player_stats(
        self, player_id: int, fixture_id: int, team_id: int, season: str, stats: dict,
    ) -> None:
        values = dict(
            player_id=player_id,
            fixture_id=fixture_id,
            team_id=team_id,
            season=season,
            goals=stats.get("goals", 0),
            assists=stats.get("assists", 0),
            corner_assists=stats.get("corner_assists", 0),
            shots_on=stats.get("shots_on", 0),
            shots_total=stats.get("shots_total", 0),
            passes_key=stats.get("passes_key", 0),
            passes_total=stats.get("passes_total", 0),
            passes_accuracy=stats.get("passes_accuracy", 0),
            dribbles_won=stats.get("dribbles_won", 0),
            dribbles_attempts=stats.get("dribbles_attempts", 0),
            dribbles_past=stats.get("dribbles_past", 0),
            duels_won=stats.get("duels_won", 0),
            duels_total=stats.get("duels_total", 0),
            tackles_won=stats.get("tackles_won", 0),
            interceptions=stats.get("interceptions", 0),
            blocks=stats.get("blocks", 0),
            fouls_drawn=stats.get("fouls_drawn", 0),
            fouls_committed=stats.get("fouls_committed", 0),
            cards_yellow=stats.get("cards_yellow", 0),
            cards_red=stats.get("cards_red", 0),
            penalty_won=stats.get("penalty_won", 0),
            saves=stats.get("saves", 0),
            goals_conceded=stats.get("goals_conceded", 0),
            minutes=stats.get("minutes", 0),
            appearances=stats.get("appearances", 1),
            rating=stats.get("rating", None),
        )
        update_set = {k: v for k, v in values.items() if k not in ("player_id", "fixture_id", "season")}
        stmt = (
            pg_insert(PlayerStats)
            .values(**values)
            .on_conflict_do_update(constraint="uq_player_stats", set_=update_set)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_season_score(
        self,
        player_id: int,
        competition_id: int,
        season: str,
        total_pts: float,
        matches_played: int,
        breakdown: dict,
        team_id: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if team_id is None:
            team_id = (
                await self._session.execute(
                    select(PlayerStats.team_id)
                    .join(Fixture, PlayerStats.fixture_id == Fixture.id)
                    .where(
                        PlayerStats.player_id == player_id,
                        Fixture.competition_id == competition_id,
                        PlayerStats.season == season,
                    )
                    .group_by(PlayerStats.team_id)
                    .order_by(func.sum(PlayerStats.minutes).desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        insert_stmt = pg_insert(SFASeasonScore).values(
            player_id=player_id,
            competition_id=competition_id,
            team_id=team_id,
            season=season,
            total_pts=total_pts,
            matches_played=matches_played,
            breakdown=breakdown,
            last_updated=now,
        )
        stmt = insert_stmt.on_conflict_do_update(
                constraint="uq_sfa_season_score",
                set_={
                    "team_id": insert_stmt.excluded.team_id,
                    "total_pts": total_pts,
                    "matches_played": matches_played,
                    "breakdown": breakdown,
                    "last_updated": now,
                },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_stage_factor(self, competition_id: int, stage: str) -> float:
        result = await self._session.execute(
            select(CompetitionStage.stage_factor).where(
                CompetitionStage.competition_id == competition_id,
                CompetitionStage.stage == stage,
            )
        )
        row = result.scalar_one_or_none()
        return float(row) if row is not None else 1.0

    async def save_ingestion_log(
        self,
        competition_id: int,
        season: str,
        status: IngestionStatus,
        players_processed: int | None,
        error_msg: str | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        await self._session.execute(
            pg_insert(IngestionLog).values(
                competition_id=competition_id,
                season=season,
                started_at=now,
                finished_at=now,
                status=status,
                players_processed=players_processed,
                error_msg=error_msg,
            )
        )
        await self._session.flush()

    async def delete_player_events_for_fixture(
        self, player_id: int, fixture_id: int,
    ) -> None:
        await self._session.execute(
            delete(PlayerEvent).where(
                PlayerEvent.player_id == player_id,
                PlayerEvent.fixture_id == fixture_id,
            )
        )
        await self._session.flush()

    async def get_season_fixtures(
        self, competition_id: int, season: str,
    ) -> list[FixtureInfoRow]:
        result = await self._session.execute(
            select(Fixture.id, Fixture.external_id, Fixture.season)
            .where(Fixture.competition_id == competition_id)
            .where(Fixture.season == season)
            .order_by(Fixture.played_at)
        )
        return [
            FixtureInfoRow(fixture_id=row[0], fixture_external_id=row[1], season=row[2])
            for row in result.all()
        ]

    async def get_player_id_by_external(self, external_id: int) -> int | None:
        result = await self._session.execute(
            select(Player.id).where(Player.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_last_ingestion_log(
        self, competition_id: int, season: str,
    ) -> IngestionLogRow | None:
        stmt = (
            select(
                IngestionLog.competition_id,
                Competition.name.label("competition_name"),
                IngestionLog.season,
                IngestionLog.status,
                IngestionLog.started_at,
                IngestionLog.finished_at,
                IngestionLog.error_msg,
            )
            .join(Competition, IngestionLog.competition_id == Competition.id)
            .where(
                IngestionLog.competition_id == competition_id,
                IngestionLog.season == season,
            )
            .order_by(IngestionLog.started_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        return IngestionLogRow(**row) if row is not None else None

    async def get_ingestion_logs_by_season(
        self, season: str,
    ) -> list[IngestionLogRow]:
        stmt = (
            select(
                IngestionLog.competition_id,
                Competition.name.label("competition_name"),
                IngestionLog.season,
                IngestionLog.status,
                IngestionLog.started_at,
                IngestionLog.finished_at,
                IngestionLog.error_msg,
            )
            .join(Competition, IngestionLog.competition_id == Competition.id)
            .where(IngestionLog.season == season)
            .order_by(IngestionLog.competition_id, IngestionLog.started_at.desc())
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        return [IngestionLogRow(**row) for row in rows]

    async def get_fixture_counts_by_competition(
        self, season: str,
    ) -> dict[int, int]:
        stmt = (
            select(Fixture.competition_id, func.count(Fixture.id))
            .where(Fixture.season == season)
            .group_by(Fixture.competition_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return {competition_id: count for competition_id, count in rows}

    async def get_fixtures_for_player(
        self,
        player_id: int,
        season: str,
        competition_id: int | None = None,
    ) -> list[PlayerFixtureInfoRow]:
        stmt = (
            select(
                Fixture.id.label("fixture_id"),
                Fixture.external_id.label("fixture_external_id"),
                Fixture.season,
                Fixture.competition_id,
                Fixture.home_team_id,
                Fixture.away_team_id,
                PlayerStats.team_id.label("player_team_id"),
                Player.external_id.label("player_external_id"),
                Player.name.label("player_name"),
                Fixture.stage,
            )
            .join(PlayerStats, PlayerStats.fixture_id == Fixture.id)
            .join(Player, Player.id == PlayerStats.player_id)
            .where(PlayerStats.player_id == player_id)
            .where(PlayerStats.team_id.is_not(None))
            .where(Fixture.season == season)
            .order_by(Fixture.id)
        )
        if competition_id is not None:
            stmt = stmt.where(Fixture.competition_id == competition_id)

        rows = (await self._session.execute(stmt)).mappings().all()
        return [
            PlayerFixtureInfoRow(
                fixture_id=row["fixture_id"],
                fixture_external_id=row["fixture_external_id"],
                season=row["season"],
                competition_id=row["competition_id"],
                home_team_id=row["home_team_id"],
                away_team_id=row["away_team_id"],
                player_team_id=row["player_team_id"],
                player_external_id=row["player_external_id"],
                player_name=row["player_name"],
                stage=row["stage"],
            )
            for row in rows
        ]
