from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from sfa.domain.ports import (
    PlayerScoreDTO,
    RankedPlayerDTO,
    SFAScoreRepositoryProtocol,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.teams.models import Team


class SFAScoreRepository(SFAScoreRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_best_score_for_player_season(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> PlayerScoreDTO | None:
        season_team = aliased(Team)
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.name.label("player_name"),
                func.coalesce(season_team.name, Team.name).label("team_name"),
                Player.position,
                Competition.name.label("competition_name"),
                SFASeasonScore.competition_id,
                SFASeasonScore.total_pts,
                SFASeasonScore.matches_played,
                Player.photo_url,
                SFASeasonScore.breakdown,
            )
            .join(Player, SFASeasonScore.player_id == Player.id)
            .join(Team, Player.team_id == Team.id)
            .outerjoin(season_team, SFASeasonScore.team_id == season_team.id)
            .join(Competition, SFASeasonScore.competition_id == Competition.id)
            .where(SFASeasonScore.player_id == player_id)
            .where(SFASeasonScore.season == season)
            .where(rv_filter)
            .order_by(
                case((Competition.country == "EUR", 1), else_=0).asc(),
                SFASeasonScore.total_pts.desc(),
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).mappings().first()
        if row is None:
            return None
        pos = row["position"]
        return PlayerScoreDTO(
            player_id=row["player_id"],
            player_name=row["player_name"],
            team_name=row["team_name"],
            position=pos.value if hasattr(pos, "value") else str(pos),
            competition_name=row["competition_name"],
            competition_id=row["competition_id"],
            total_pts=float(row["total_pts"]),
            matches_played=row["matches_played"],
            photo_url=row["photo_url"],
            breakdown=row["breakdown"],
        )

    async def get_global_rank(
        self,
        player_id: int,
        season: str,
        total_pts: float,
        rules_version_id: int | None = None,
    ) -> int:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        per_player = (
            select(
                SFASeasonScore.player_id,
                func.sum(
                    SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts
                ).label("sum_pts"),
            )
            .where(
                SFASeasonScore.season == season,
                SFASeasonScore.player_id != player_id,
                rv_filter,
            )
            .group_by(SFASeasonScore.player_id)
            .subquery()
        )
        stmt = select(func.count()).where(per_player.c.sum_pts > total_pts)
        return (await self._session.execute(stmt)).scalar_one() + 1

    async def get_competitions_for_player_season(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> list[str]:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        stmt = (
            select(Competition.name)
            .join(SFASeasonScore, SFASeasonScore.competition_id == Competition.id)
            .where(
                SFASeasonScore.player_id == player_id,
                SFASeasonScore.season == season,
                rv_filter,
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_ranking(
        self,
        season: str,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = 50,
        name: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> list[RankedPlayerDTO]:
        season_team = aliased(Team)
        score_filters = [SFASeasonScore.season == season]
        if rules_version_id is None:
            score_filters.append(SFASeasonScore.rules_version_id.is_(None))
        else:
            score_filters.append(SFASeasonScore.rules_version_id == rules_version_id)
        if competition_id is not None:
            score_filters.append(SFASeasonScore.competition_id == competition_id)

        def _jint(key: str) -> object:
            return func.coalesce(cast(SFASeasonScore.breakdown[key]["count"].astext, Integer), 0)

        sum_pts_expr = (
            func.sum(SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts)
            if use_total
            else func.sum(SFASeasonScore.total_pts)
        )
        agg = (
            select(
                SFASeasonScore.player_id,
                sum_pts_expr.label("sum_pts"),
                func.sum(SFASeasonScore.matches_played).label("sum_matches"),
                func.sum(_jint("goal") + _jint("goal_penalty")).label("sum_goals"),
                func.sum(_jint("assist") + _jint("corner_assist")).label("sum_assists"),
                func.sum(_jint("dribbles_won")).label("sum_dribbles"),
                func.sum(_jint("duels_won")).label("sum_duels"),
            )
            .where(*score_filters)
            .group_by(SFASeasonScore.player_id)
            .subquery()
        )

        ranked_scores = (
            select(
                SFASeasonScore.player_id,
                SFASeasonScore.competition_id,
                SFASeasonScore.team_id,
                func.row_number().over(
                    partition_by=SFASeasonScore.player_id,
                    order_by=[
                        case((Competition.country == "EUR", 1), else_=0).asc(),
                        SFASeasonScore.total_pts.desc(),
                    ],
                ).label("rn"),
            )
            .join(Competition, SFASeasonScore.competition_id == Competition.id)
            .where(*score_filters)
            .subquery()
        )
        best_comp = (
            select(
                ranked_scores.c.player_id,
                ranked_scores.c.competition_id,
                ranked_scores.c.team_id,
            )
            .where(ranked_scores.c.rn == 1)
            .subquery()
        )

        rank_col = func.rank().over(order_by=agg.c.sum_pts.desc()).label("rank")
        stmt = (
            select(
                rank_col,
                Player.id.label("player_id"),
                Player.name.label("player_name"),
                func.coalesce(season_team.name, Team.name).label("team_name"),
                func.coalesce(
                    season_team.external_id, Team.external_id
                ).label("team_external_id"),
                Player.position,
                Competition.name.label("competition_name"),
                agg.c.sum_pts.label("total_pts"),
                agg.c.sum_matches.label("matches_played"),
                Player.photo_url,
                agg.c.sum_goals.label("goals"),
                agg.c.sum_assists.label("assists"),
                agg.c.sum_dribbles.label("dribbles_won"),
                agg.c.sum_duels.label("duels_won"),
            )
            .join(agg, Player.id == agg.c.player_id)
            .join(Team, Player.team_id == Team.id)
            .join(best_comp, Player.id == best_comp.c.player_id)
            .outerjoin(season_team, best_comp.c.team_id == season_team.id)
            .join(Competition, best_comp.c.competition_id == Competition.id)
            .order_by(agg.c.sum_pts.desc())
        )
        if position is not None:
            stmt = stmt.where(Player.position == position)

        if name is not None:
            sub = stmt.subquery()
            final = (
                select(sub)
                .where(
                    func.unaccent(sub.c.player_name).ilike(
                        func.concat("%", func.unaccent(name), "%")
                    )
                )
                .limit(limit)
            )
        else:
            final = stmt.limit(limit)

        rows = (await self._session.execute(final)).mappings().all()

        def _logo(ext_id: int | None) -> str | None:
            return f"https://media.api-sports.io/football/teams/{ext_id}.png" if ext_id else None

        return [
            RankedPlayerDTO(
                rank=row["rank"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=row["team_name"],
                team_logo_url=_logo(row["team_external_id"]),
                position=(lambda p: p.value if hasattr(p, "value") else str(p))(row["position"]),
                competition_name=row["competition_name"],
                total_pts=float(row["total_pts"]),
                matches_played=row["matches_played"],
                photo_url=row["photo_url"],
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
                dribbles_won=int(row["dribbles_won"] or 0),
                duels_won=int(row["duels_won"] or 0),
            )
            for row in rows
        ]

    async def get_ranking_total(
        self,
        season: str,
        position: str | None = None,
        competition_id: int | None = None,
        name: str | None = None,
        rules_version_id: int | None = None,
    ) -> int:
        score_filters = [SFASeasonScore.season == season]
        if rules_version_id is None:
            score_filters.append(SFASeasonScore.rules_version_id.is_(None))
        else:
            score_filters.append(SFASeasonScore.rules_version_id == rules_version_id)
        if competition_id is not None:
            score_filters.append(SFASeasonScore.competition_id == competition_id)

        inner = (
            select(SFASeasonScore.player_id)
            .join(Player, SFASeasonScore.player_id == Player.id)
            .where(*score_filters)
            .group_by(SFASeasonScore.player_id)
        )
        if position is not None:
            inner = inner.where(Player.position == position)
        if name is not None:
            inner = inner.where(
                func.unaccent(Player.name).ilike(
                    func.concat("%", func.unaccent(name), "%")
                )
            )

        subq = inner.subquery()
        stmt = select(func.count()).select_from(subq)
        return (await self._session.execute(stmt)).scalar_one()

    async def latest_season(self) -> str | None:
        result = await self._session.execute(select(func.max(SFASeasonScore.season)))
        return result.scalar_one_or_none()

    async def latest_season_for_player(self, player_id: int) -> str | None:
        result = await self._session.execute(
            select(func.max(SFASeasonScore.season)).where(
                SFASeasonScore.player_id == player_id
            )
        )
        return result.scalar_one_or_none()

    async def get_total_player_stats(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> tuple[int, int, int, float]:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        stmt = (
            select(
                SFASeasonScore.matches_played,
                SFASeasonScore.breakdown,
                SFASeasonScore.total_pts,
                SFASeasonScore.achievement_bonus_pts,
            )
            .where(
                SFASeasonScore.player_id == player_id,
                SFASeasonScore.season == season,
                rv_filter,
            )
        )
        rows = (await self._session.execute(stmt)).fetchall()

        total_matches = sum(r[0] for r in rows)
        total_goals = sum(
            (r[1] or {}).get("goal", {}).get("count", 0)
            + (r[1] or {}).get("goal_penalty", {}).get("count", 0)
            for r in rows
        )
        total_assists = sum(
            (r[1] or {}).get("assist", {}).get("count", 0)
            + (r[1] or {}).get("corner_assist", {}).get("count", 0)
            for r in rows
        )
        total_pts = round(sum(float(r[2]) + float(r[3]) for r in rows), 2)
        return total_matches, total_goals, total_assists, total_pts

    async def get_available_seasons_for_player(self, player_id: int) -> list[str]:
        stmt = (
            select(SFASeasonScore.season)
            .distinct()
            .where(SFASeasonScore.player_id == player_id)
            .order_by(SFASeasonScore.season.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_ranking_all_seasons(
        self,
        position: str | None = None,
        competition_id: int | None = None,
        limit: int = 50,
        name: str | None = None,
        rules_version_id: int | None = None,
        use_total: bool = False,
    ) -> list[RankedPlayerDTO]:
        score_filters = []
        if rules_version_id is None:
            score_filters.append(SFASeasonScore.rules_version_id.is_(None))
        else:
            score_filters.append(SFASeasonScore.rules_version_id == rules_version_id)
        if competition_id is not None:
            score_filters.append(SFASeasonScore.competition_id == competition_id)

        def _jint(key: str) -> object:
            return func.coalesce(cast(SFASeasonScore.breakdown[key]["count"].astext, Integer), 0)

        sum_pts_expr = (
            func.sum(SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts)
            if use_total
            else func.sum(SFASeasonScore.total_pts)
        )
        agg = (
            select(
                SFASeasonScore.player_id,
                sum_pts_expr.label("sum_pts"),
                func.sum(SFASeasonScore.matches_played).label("sum_matches"),
                func.sum(_jint("goal") + _jint("goal_penalty")).label("sum_goals"),
                func.sum(_jint("assist") + _jint("corner_assist")).label("sum_assists"),
                func.sum(_jint("dribbles_won")).label("sum_dribbles"),
                func.sum(_jint("duels_won")).label("sum_duels"),
            )
            .where(*score_filters)
            .group_by(SFASeasonScore.player_id)
            .subquery()
        )

        ranked_scores = (
            select(
                SFASeasonScore.player_id,
                SFASeasonScore.competition_id,
                func.row_number().over(
                    partition_by=SFASeasonScore.player_id,
                    order_by=[
                        case((Competition.country == "EUR", 1), else_=0).asc(),
                        SFASeasonScore.total_pts.desc(),
                    ],
                ).label("rn"),
            )
            .join(Competition, SFASeasonScore.competition_id == Competition.id)
            .where(*score_filters)
            .subquery()
        )
        best_comp = (
            select(ranked_scores.c.player_id, ranked_scores.c.competition_id)
            .where(ranked_scores.c.rn == 1)
            .subquery()
        )

        rank_col = func.rank().over(order_by=agg.c.sum_pts.desc()).label("rank")
        stmt = (
            select(
                rank_col,
                Player.id.label("player_id"),
                Player.name.label("player_name"),
                Team.name.label("team_name"),
                Team.external_id.label("team_external_id"),
                Player.position,
                Competition.name.label("competition_name"),
                agg.c.sum_pts.label("total_pts"),
                agg.c.sum_matches.label("matches_played"),
                Player.photo_url,
                agg.c.sum_goals.label("goals"),
                agg.c.sum_assists.label("assists"),
                agg.c.sum_dribbles.label("dribbles_won"),
                agg.c.sum_duels.label("duels_won"),
            )
            .join(agg, Player.id == agg.c.player_id)
            .join(Team, Player.team_id == Team.id)
            .join(best_comp, Player.id == best_comp.c.player_id)
            .join(Competition, best_comp.c.competition_id == Competition.id)
            .order_by(agg.c.sum_pts.desc())
        )
        if position is not None:
            stmt = stmt.where(Player.position == position)

        if name is not None:
            sub = stmt.subquery()
            final = (
                select(sub)
                .where(
                    func.unaccent(sub.c.player_name).ilike(
                        func.concat("%", func.unaccent(name), "%")
                    )
                )
                .limit(limit)
            )
        else:
            final = stmt.limit(limit)

        rows = (await self._session.execute(final)).mappings().all()

        def _logo(ext_id: int | None) -> str | None:
            return f"https://media.api-sports.io/football/teams/{ext_id}.png" if ext_id else None

        return [
            RankedPlayerDTO(
                rank=row["rank"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=row["team_name"],
                team_logo_url=_logo(row["team_external_id"]),
                position=(lambda p: p.value if hasattr(p, "value") else str(p))(row["position"]),
                competition_name=row["competition_name"],
                total_pts=float(row["total_pts"]),
                matches_played=row["matches_played"],
                photo_url=row["photo_url"],
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
                dribbles_won=int(row["dribbles_won"] or 0),
                duels_won=int(row["duels_won"] or 0),
            )
            for row in rows
        ]

    async def get_ranking_total_all_seasons(
        self,
        position: str | None = None,
        competition_id: int | None = None,
        name: str | None = None,
        rules_version_id: int | None = None,
    ) -> int:
        score_filters = []
        if rules_version_id is None:
            score_filters.append(SFASeasonScore.rules_version_id.is_(None))
        else:
            score_filters.append(SFASeasonScore.rules_version_id == rules_version_id)
        if competition_id is not None:
            score_filters.append(SFASeasonScore.competition_id == competition_id)

        inner = (
            select(SFASeasonScore.player_id)
            .join(Player, SFASeasonScore.player_id == Player.id)
            .where(*score_filters)
            .group_by(SFASeasonScore.player_id)
        )
        if position is not None:
            inner = inner.where(Player.position == position)
        if name is not None:
            inner = inner.where(
                func.unaccent(Player.name).ilike(
                    func.concat("%", func.unaccent(name), "%")
                )
            )

        subq = inner.subquery()
        stmt = select(func.count()).select_from(subq)
        return (await self._session.execute(stmt)).scalar_one()

    async def get_total_player_stats_all_seasons(
        self, player_id: int, rules_version_id: int | None = None,
    ) -> tuple[int, int, int, float]:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        stmt = (
            select(
                SFASeasonScore.matches_played,
                SFASeasonScore.breakdown,
                SFASeasonScore.total_pts,
                SFASeasonScore.achievement_bonus_pts,
            )
            .where(
                SFASeasonScore.player_id == player_id,
                rv_filter,
            )
        )
        rows = (await self._session.execute(stmt)).fetchall()

        total_matches = sum(r[0] for r in rows)
        total_goals = sum(
            (r[1] or {}).get("goal", {}).get("count", 0)
            + (r[1] or {}).get("goal_penalty", {}).get("count", 0)
            for r in rows
        )
        total_assists = sum(
            (r[1] or {}).get("assist", {}).get("count", 0)
            + (r[1] or {}).get("corner_assist", {}).get("count", 0)
            for r in rows
        )
        total_pts = round(sum(float(r[2]) + float(r[3]) for r in rows), 2)
        return total_matches, total_goals, total_assists, total_pts

    async def get_global_rank_all_seasons(
        self,
        player_id: int,
        total_pts: float,
        rules_version_id: int | None = None,
    ) -> int:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        per_player = (
            select(
                SFASeasonScore.player_id,
                func.sum(
                    SFASeasonScore.total_pts + SFASeasonScore.achievement_bonus_pts
                ).label("sum_pts"),
            )
            .where(
                SFASeasonScore.player_id != player_id,
                rv_filter,
            )
            .group_by(SFASeasonScore.player_id)
            .subquery()
        )
        stmt = select(func.count()).where(per_player.c.sum_pts > total_pts)
        return (await self._session.execute(stmt)).scalar_one() + 1
