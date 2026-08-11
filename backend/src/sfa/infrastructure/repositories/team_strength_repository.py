from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.scoring_ports import (
    FixtureEloRow,
    FixtureTeamStrengthDTO,
    TeamCompetitionRow,
    TeamEloRow,
    TeamEloSeedDTO,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixture_team_strengths.models import (
    FixtureTeamStrength,
)
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.standings.models import StandingSnapshot
from sfa.infrastructure.models.team_elo_seeds.models import TeamEloSeed
from sfa.infrastructure.models.team_strengths.models import TeamStrength
from sfa.infrastructure.models.teams.models import Team

logger = logging.getLogger(__name__)

ELO_SOURCES = (
    "clubelo_seed",
    "elo_v1",
    "club_elo_v2",
    "national_elo_seed",
    "national_elo_v1",
)
ELO_FINAL_FIXTURE_STATUSES = ("FT", "AET", "PEN")


class TeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_team_strength(
        self, team_id: int, season: str, competition_id: int
    ) -> float | None:
        stmt = select(TeamStrength.strength).where(
            TeamStrength.team_id == team_id,
            TeamStrength.season == season,
            TeamStrength.competition_id == competition_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return float(row) if row is not None else None

    async def upsert_team_strength(
        self,
        team_id: int,
        season: str,
        competition_id: int,
        strength: float,
        source: str,
    ) -> None:
        stmt = (
            pg_insert(TeamStrength)
            .values(
                team_id=team_id,
                season=season,
                competition_id=competition_id,
                strength=strength,
                source=source,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_team_strength",
                set_={"strength": strength, "source": source, "elo_raw": None},
                where=TeamStrength.source.not_in(ELO_SOURCES),
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_team_standings_for_season(
        self, competition_id: int, season: str
    ) -> list[TeamStandingRow]:
        stmt = (
            select(
                StandingSnapshot.team_id,
                func.avg(StandingSnapshot.position).label("avg_position"),
                func.max(StandingSnapshot.points).label("total_points"),
                func.count(StandingSnapshot.matchday.distinct()).label("matchdays_played"),
            )
            .where(
                StandingSnapshot.competition_id == competition_id,
                StandingSnapshot.season == season,
            )
            .group_by(StandingSnapshot.team_id)
        )
        result = await self._session.execute(stmt)
        return [
            TeamStandingRow(
                team_id=row.team_id,
                season=season,
                competition_id=competition_id,
                avg_position=float(row.avg_position),
                total_points=int(row.total_points),
                matchdays_played=int(row.matchdays_played),
            )
            for row in result.all()
        ]

    async def get_team_strength_with_elo(
        self, team_id: int, season: str, competition_id: int
    ) -> tuple[float | None, float | None]:
        stmt = select(TeamStrength.strength, TeamStrength.elo_raw).where(
            TeamStrength.team_id == team_id,
            TeamStrength.season == season,
            TeamStrength.competition_id == competition_id,
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None, None
        return (
            float(row.strength) if row.strength is not None else None,
            float(row.elo_raw) if row.elo_raw is not None else None,
        )

    async def upsert_team_elo(
        self,
        team_id: int,
        season: str,
        elo_raw: float,
        strength_normalized: float,
        source: str,
        competition_ids: list[int],
        elo_seed_raw: float | None = None,
    ) -> None:
        if not competition_ids:
            logger.warning(
                "[TeamStrengthRepository] No competition_ids for team_id=%d season=%s; skipping ELO upsert",
                team_id,
                season,
            )
            return

        now = datetime.now(timezone.utc)
        values = {
            "team_id": team_id,
            "season": season,
            "strength": strength_normalized,
            "elo_raw": elo_raw,
            "source": source,
            "created_at": now,
        }
        update_values = {
            "strength": strength_normalized,
            "elo_raw": elo_raw,
            "source": source,
        }
        if elo_seed_raw is not None:
            values["elo_seed_raw"] = elo_seed_raw
            update_values["elo_seed_raw"] = elo_seed_raw

        for competition_id in competition_ids:
            stmt = (
                pg_insert(TeamStrength)
                .values(
                    competition_id=competition_id,
                    **values,
                )
                .on_conflict_do_update(
                    constraint="uq_team_strength",
                    set_=update_values,
                )
            )
            await self._session.execute(stmt)
        await self._session.flush()

    async def get_all_teams_with_elo(
        self,
        season: str,
        competition_ids: list[int] | None = None,
    ) -> list[TeamEloRow]:
        filters = [
            TeamStrength.season == season,
            TeamStrength.elo_raw.is_not(None),
        ]
        if competition_ids is not None:
            filters.append(TeamStrength.competition_id.in_(competition_ids))

        stmt = (
            select(
                TeamStrength.team_id,
                TeamStrength.season,
                func.max(TeamStrength.elo_raw).label("elo_raw"),
                func.max(TeamStrength.elo_seed_raw).label("elo_seed_raw"),
                func.max(TeamStrength.strength).label("strength"),
            )
            .where(*filters)
            .group_by(TeamStrength.team_id, TeamStrength.season)
        )
        result = await self._session.execute(stmt)
        return [
            TeamEloRow(
                team_id=row.team_id,
                season=row.season,
                elo_raw=float(row.elo_raw),
                strength=float(row.strength),
                elo_seed_raw=float(row.elo_seed_raw) if row.elo_seed_raw is not None else None,
            )
            for row in result.all()
        ]

    async def get_fixtures_for_elo_recalc(
        self, season: str, competition_ids: list[int]
    ) -> list[FixtureEloRow]:
        if not competition_ids:
            return []

        stmt = (
            select(
                Fixture.id.label("fixture_id"),
                Fixture.home_team_id,
                Fixture.away_team_id,
                Fixture.played_at,
                Fixture.competition_id,
                Fixture.season,
                Fixture.home_goals,
                Fixture.away_goals,
                Fixture.score_source,
            )
            .where(
                Fixture.competition_id.in_(competition_ids),
                Fixture.season == season,
                Fixture.status.in_(ELO_FINAL_FIXTURE_STATUSES),
            )
            .order_by(Fixture.played_at.asc().nulls_last(), Fixture.id.asc())
        )
        result = await self._session.execute(stmt)
        rows: list[FixtureEloRow] = []
        missing_score_fixture_ids: list[int] = []
        for row in result.all():
            if (
                row.home_goals is None
                or row.away_goals is None
                or row.score_source is None
            ):
                missing_score_fixture_ids.append(row.fixture_id)
                continue
            rows.append(FixtureEloRow(
                fixture_id=row.fixture_id,
                home_team_id=row.home_team_id,
                away_team_id=row.away_team_id,
                played_at=row.played_at,
                competition_id=row.competition_id,
                home_goals=int(row.home_goals),
                away_goals=int(row.away_goals),
                season=row.season,
            ))
        if missing_score_fixture_ids:
            missing = ", ".join(str(item) for item in missing_score_fixture_ids)
            raise ValueError(
                f"Missing official score or provenance for fixture_ids: {missing}"
            )
        return rows

    async def upsert_team_elo_seed(self, seed: TeamEloSeedDTO) -> None:
        stmt = (
            pg_insert(TeamEloSeed)
            .values(
                team_id=seed.team_id,
                season=seed.season,
                participant_kind=seed.participant_kind,
                elo_raw=seed.elo_raw,
                effective_at=seed.effective_at,
                source=seed.source,
                source_reference=seed.source_reference,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_team_elo_seed",
                set_={
                    "elo_raw": seed.elo_raw,
                    "effective_at": seed.effective_at,
                    "source": seed.source,
                    "source_reference": seed.source_reference,
                    "created_at": datetime.now(timezone.utc),
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_team_elo_seeds(
        self,
        season: str,
        participant_kind: str,
    ) -> list[TeamEloSeedDTO]:
        stmt = select(TeamEloSeed).where(
            TeamEloSeed.season == season,
            TeamEloSeed.participant_kind == participant_kind,
        )
        result = await self._session.execute(stmt)
        return [
            TeamEloSeedDTO(
                team_id=row.team_id,
                season=row.season,
                participant_kind=row.participant_kind,
                elo_raw=float(row.elo_raw),
                effective_at=row.effective_at,
                source=row.source,
                source_reference=row.source_reference,
            )
            for row in result.scalars().all()
        ]

    async def replace_fixture_team_strengths(
        self,
        season: str,
        participant_kind: str,
        competition_ids: list[int],
        snapshots: list[FixtureTeamStrengthDTO],
    ) -> None:
        if not competition_ids:
            return

        await self._session.execute(
            delete(FixtureTeamStrength).where(
                FixtureTeamStrength.season == season,
                FixtureTeamStrength.participant_kind == participant_kind,
                FixtureTeamStrength.competition_id.in_(competition_ids),
            )
        )
        if snapshots:
            now = datetime.now(timezone.utc)
            values = [
                {
                    "fixture_id": snapshot.fixture_id,
                    "team_id": snapshot.team_id,
                    "season": snapshot.season,
                    "competition_id": snapshot.competition_id,
                    "participant_kind": snapshot.participant_kind,
                    "pre_match_elo_raw": snapshot.pre_match_elo_raw,
                    "post_match_elo_raw": snapshot.post_match_elo_raw,
                    "pre_match_strength": snapshot.pre_match_strength,
                    "post_match_strength": snapshot.post_match_strength,
                    "model_version": snapshot.model_version,
                    "seed_source": snapshot.seed_source,
                    "created_at": now,
                }
                for snapshot in snapshots
            ]
            stmt = pg_insert(FixtureTeamStrength).values(values)
            await self._session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[
                        FixtureTeamStrength.fixture_id,
                        FixtureTeamStrength.team_id,
                    ],
                    set_={
                        "season": stmt.excluded.season,
                        "competition_id": stmt.excluded.competition_id,
                        "participant_kind": stmt.excluded.participant_kind,
                        "pre_match_elo_raw": stmt.excluded.pre_match_elo_raw,
                        "post_match_elo_raw": stmt.excluded.post_match_elo_raw,
                        "pre_match_strength": stmt.excluded.pre_match_strength,
                        "post_match_strength": stmt.excluded.post_match_strength,
                        "model_version": stmt.excluded.model_version,
                        "seed_source": stmt.excluded.seed_source,
                        "created_at": stmt.excluded.created_at,
                    },
                )
            )
        await self._session.flush()

    async def get_team_name_id_map(
        self,
        season: str,
        participant_kind: str | None = None,
    ) -> dict[str, int]:
        filters = [Fixture.season == season]
        if participant_kind is not None:
            filters.append(Competition.participant_kind == participant_kind)
        stmt = (
            select(Team.name, Team.id)
            .join(
                Fixture,
                or_(
                    Fixture.home_team_id == Team.id,
                    Fixture.away_team_id == Team.id,
                ),
            )
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(*filters)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {row.name: row.id for row in result.all()}

    async def get_active_competition_ids_for_team(
        self, team_id: int, season: str
    ) -> list[int]:
        stmt = (
            select(Fixture.competition_id)
            .where(
                Fixture.season == season,
                or_(
                    Fixture.home_team_id == team_id,
                    Fixture.away_team_id == team_id,
                ),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_competition_ids_for_participant_kind(
        self, season: str, participant_kind: str
    ) -> list[int]:
        stmt = (
            select(Fixture.competition_id)
            .join(Competition, Competition.id == Fixture.competition_id)
            .where(
                Fixture.season == season,
                Competition.participant_kind == participant_kind,
            )
            .distinct()
            .order_by(Fixture.competition_id.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_competition_id_by_name(self, name: str) -> int | None:
        stmt = (
            select(Competition.id)
            .where(func.lower(Competition.name) == name.lower())
            .order_by(Competition.id.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_teams_for_competition_season(
        self, competition_id: int, season: str
    ) -> list[TeamCompetitionRow]:
        stmt = (
            select(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                func.cast(competition_id, Fixture.competition_id.type).label("competition_id"),
            )
            .outerjoin(
                Fixture,
                (
                    (Fixture.competition_id == competition_id)
                    & (Fixture.season == season)
                    & or_(
                        Fixture.home_team_id == Team.id,
                        Fixture.away_team_id == Team.id,
                    )
                ),
            )
            .where(
                or_(
                    Team.competition_id == competition_id,
                    Fixture.id.is_not(None),
                ),
            )
            .distinct()
            .order_by(Team.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            TeamCompetitionRow(
                team_id=row.team_id,
                team_name=row.team_name,
                competition_id=row.competition_id,
            )
            for row in result.all()
        ]

    async def get_team_strength_coverage(
        self, competition_id: int, season: str
    ) -> list[TeamStrengthCoverageRow]:
        stmt = (
            select(
                Team.id.label("team_id"),
                Team.name.label("team_name"),
                func.cast(competition_id, Fixture.competition_id.type).label("competition_id"),
                TeamStrength.strength,
                TeamStrength.elo_raw,
                TeamStrength.source,
            )
            .outerjoin(
                Fixture,
                (
                    (Fixture.competition_id == competition_id)
                    & (Fixture.season == season)
                    & or_(
                        Fixture.home_team_id == Team.id,
                        Fixture.away_team_id == Team.id,
                    )
                ),
            )
            .outerjoin(
                TeamStrength,
                (TeamStrength.team_id == Team.id)
                & (TeamStrength.season == season)
                & (TeamStrength.competition_id == competition_id),
            )
            .where(
                or_(
                    Team.competition_id == competition_id,
                    Fixture.id.is_not(None),
                ),
            )
            .distinct()
            .order_by(Team.name.asc())
        )
        result = await self._session.execute(stmt)
        return [
            TeamStrengthCoverageRow(
                team_id=row.team_id,
                team_name=row.team_name,
                competition_id=row.competition_id,
                strength=float(row.strength) if row.strength is not None else None,
                elo_raw=float(row.elo_raw) if row.elo_raw is not None else None,
                source=row.source,
            )
            for row in result.all()
        ]
