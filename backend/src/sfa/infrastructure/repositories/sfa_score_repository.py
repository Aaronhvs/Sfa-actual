from datetime import date
from unicodedata import combining, normalize

from sqlalchemy import Integer, Numeric, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.ports import (
    PlayerScoreDTO,
    RankedPlayerDTO,
    SFAScoreRepositoryProtocol,
)
from sfa.domain.player_position_overrides import (
    override_name_terms_for_position,
    position_for_context,
)
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.scores.models import SFASeasonScore
from sfa.infrastructure.models.teams.models import Team


def _age_at_date(birth_date: date, reference_date: date) -> int:
    age = reference_date.year - birth_date.year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _b1_label_for_birth_date(birth_date: date | None) -> str | None:
    if birth_date is None:
        return None
    age = _age_at_date(birth_date, date.today())
    if 17 <= age <= 20:
        return "Promesa"
    if age >= 35:
        return "Veterano"
    return None


_TEAM_SEARCH_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("argentina",),
    ("australia",),
    ("austria",),
    ("belgium", "belgica", "belgique"),
    ("brazil", "brasil"),
    ("canada",),
    ("colombia",),
    ("croatia", "croacia"),
    ("czechia", "chequia", "czech republic", "republica checa"),
    ("ecuador",),
    ("egypt", "egipto"),
    ("england", "inglaterra"),
    ("france", "francia"),
    ("germany", "alemania", "deutschland"),
    ("ghana",),
    ("haiti",),
    ("iran",),
    ("japan", "japon"),
    ("jordan", "jordania"),
    ("mexico",),
    ("morocco", "marruecos"),
    ("netherlands", "paises bajos", "holanda", "holland"),
    ("new zealand", "nueva zelanda"),
    ("norway", "noruega"),
    ("panama",),
    ("paraguay",),
    ("portugal",),
    ("qatar", "catar"),
    ("scotland", "escocia"),
    ("senegal",),
    ("south africa", "sudafrica"),
    ("south korea", "corea del sur", "korea republic", "republica de corea"),
    ("spain", "espana"),
    ("switzerland", "suiza"),
    ("tunisia", "tunez"),
    ("turkey", "turquia", "turkiye"),
    ("united states", "estados unidos", "usa", "eeuu", "ee.uu."),
    ("uruguay",),
    ("uzbekistan",),
    ("ivory coast", "costa de marfil", "cote d'ivoire"),
    ("dr congo", "rd congo", "republica democratica del congo", "congo dr"),
    ("bosnia and herzegovina", "bosnia y herzegovina", "bosnia & herzegovina", "bosnia"),
    ("curacao", "curazao"),
    ("paris saint germain", "paris saint-germain", "psg"),
    ("bayern munchen", "bayern munich"),
    ("inter", "internazionale", "inter milan"),
    ("atletico madrid", "atleti"),
    ("manchester city", "man city"),
    ("manchester united", "man united", "man utd"),
    ("tottenham", "tottenham hotspur", "spurs"),
)


def _plain(value: str) -> str:
    return "".join(
        char for char in normalize("NFKD", value.lower()) if not combining(char)
    ).strip()


def _team_search_terms(name: str) -> list[str]:
    query = _plain(name)
    terms = {name.strip()}
    if not query:
        return []

    for aliases in _TEAM_SEARCH_ALIAS_GROUPS:
        normalized_aliases = {_plain(alias) for alias in aliases}
        if any(query in alias or alias in query for alias in normalized_aliases):
            terms.update(aliases)

    return sorted(term for term in terms if term.strip())


def _unaccent_ilike(column, term: str):
    return func.unaccent(column).ilike(func.concat("%", func.unaccent(term), "%"))


def _any_unaccent_ilike(column, terms: list[str]):
    if not terms:
        return _unaccent_ilike(column, "")
    return or_(*[_unaccent_ilike(column, term) for term in terms])


def _player_or_team_name_filter(player_column, team_column, name: str):
    return or_(
        _unaccent_ilike(player_column, name),
        _any_unaccent_ilike(team_column, _team_search_terms(name)),
    )


def _position_value(position: object) -> str | None:
    if position is None:
        return None
    return position.value if hasattr(position, "value") else str(position)


def _position_filter(position: str | None):
    if position is None:
        return None
    name_terms = override_name_terms_for_position(position)
    if not name_terms:
        return Player.position == position
    return or_(
        Player.position == position,
        *[
            func.unaccent(Player.name).ilike(func.concat("%", func.unaccent(term), "%"))
            for term in name_terms
        ],
    )


def _historical_scores_scope(rules_version_id: int | None = None):
    columns = (
        SFASeasonScore.player_id,
        SFASeasonScore.competition_id,
        SFASeasonScore.team_id,
        SFASeasonScore.season,
        SFASeasonScore.total_pts,
        SFASeasonScore.achievement_bonus_pts,
        SFASeasonScore.matches_played,
        SFASeasonScore.breakdown,
        SFASeasonScore.rules_version_id,
    )
    if rules_version_id is not None:
        return (
            select(*columns)
            .where(SFASeasonScore.rules_version_id == rules_version_id)
            .subquery()
        )

    ranked = (
        select(
            *columns,
            func.row_number().over(
                partition_by=(
                    SFASeasonScore.player_id,
                    SFASeasonScore.competition_id,
                    SFASeasonScore.season,
                ),
                order_by=func.coalesce(SFASeasonScore.rules_version_id, 0).desc(),
            ).label("rn"),
        )
        .subquery()
    )
    return select(ranked).where(ranked.c.rn == 1).subquery()


class SFAScoreRepository(SFAScoreRepositoryProtocol):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_best_score_for_player_season(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> PlayerScoreDTO | None:
        rv_filter = (
            SFASeasonScore.rules_version_id == rules_version_id
            if rules_version_id is not None
            else SFASeasonScore.rules_version_id.is_(None)
        )
        stmt = (
            select(
                Player.id.label("player_id"),
                Player.name.label("player_name"),
                Team.name.label("team_name"),
                Player.position,
                Competition.name.label("competition_name"),
                SFASeasonScore.competition_id,
                SFASeasonScore.total_pts,
                SFASeasonScore.matches_played,
                Player.photo_url,
                SFASeasonScore.breakdown,
            )
            .join(Player, SFASeasonScore.player_id == Player.id)
            .join(Team, SFASeasonScore.team_id == Team.id)
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
        pos = position_for_context(
            _position_value(row["position"]),
            player_name=row["player_name"],
            team_name=row["team_name"],
            competition_id=row["competition_id"],
        )
        return PlayerScoreDTO(
            player_id=row["player_id"],
            player_name=row["player_name"],
            team_name=row["team_name"],
            position=pos or "",
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
        b1_filters = [
            PlayerEventScore.season == season,
            PlayerEventScore.calculation_details["b1_bonus"]["applied"].astext == "true",
        ]
        if rules_version_id is not None:
            b1_filters.append(PlayerEventScore.rules_version_id == rules_version_id)
        if competition_id is not None:
            b1_filters.append(PlayerEventScore.competition_id == competition_id)

        b1_age = cast(
            PlayerEventScore.calculation_details["b1_bonus"]["age_at_match"].astext,
            Integer,
        )
        b1_pts = cast(
            PlayerEventScore.calculation_details["b1_bonus"]["b1_per_event"].astext,
            Numeric,
        )
        b1_agg = (
            select(
                PlayerEventScore.player_id,
                func.coalesce(
                    func.sum(case((b1_age <= 20, b1_pts), else_=0)),
                    0,
                ).label("b1_young_pts"),
                func.coalesce(
                    func.sum(case((b1_age >= 35, b1_pts), else_=0)),
                    0,
                ).label("b1_veteran_pts"),
            )
            .where(*b1_filters)
            .group_by(PlayerEventScore.player_id)
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
                Player.birth_date.label("birth_date"),
                Team.name.label("team_name"),
                Team.external_id.label("team_external_id"),
                Player.position,
                Competition.name.label("competition_name"),
                best_comp.c.competition_id.label("competition_id"),
                agg.c.sum_pts.label("total_pts"),
                agg.c.sum_matches.label("matches_played"),
                Player.photo_url,
                agg.c.sum_goals.label("goals"),
                agg.c.sum_assists.label("assists"),
                agg.c.sum_dribbles.label("dribbles_won"),
                agg.c.sum_duels.label("duels_won"),
                func.coalesce(b1_agg.c.b1_young_pts, 0).label("b1_young_pts"),
                func.coalesce(b1_agg.c.b1_veteran_pts, 0).label("b1_veteran_pts"),
            )
            .join(agg, Player.id == agg.c.player_id)
            .join(best_comp, Player.id == best_comp.c.player_id)
            .join(Team, best_comp.c.team_id == Team.id)
            .join(Competition, best_comp.c.competition_id == Competition.id)
            .outerjoin(b1_agg, Player.id == b1_agg.c.player_id)
            .order_by(agg.c.sum_pts.desc())
        )
        if position is not None:
            stmt = stmt.where(_position_filter(position))

        if name is not None:
            sub = stmt.subquery()
            final = (
                select(sub)
                .where(_player_or_team_name_filter(sub.c.player_name, sub.c.team_name, name))
                .limit(limit)
            )
        else:
            final = stmt.limit(limit)

        rows = (await self._session.execute(final)).mappings().all()

        def _logo(ext_id: int | None) -> str | None:
            return f"https://media.api-sports.io/football/teams/{ext_id}.png" if ext_id else None

        result: list[RankedPlayerDTO] = []
        for row in rows:
            b1_young = float(row["b1_young_pts"] or 0)
            b1_veteran = float(row["b1_veteran_pts"] or 0)
            b1_total = round(b1_young + b1_veteran, 2)
            b1_label = _b1_label_for_birth_date(row["birth_date"])
            if b1_total > 0:
                b1_label = "Veterano" if b1_veteran >= b1_young and b1_veteran > 0 else "Promesa"
            display_position = position_for_context(
                _position_value(row["position"]),
                player_name=row["player_name"],
                team_name=row["team_name"],
                competition_id=row["competition_id"],
            )
            if position is not None and display_position != position:
                continue
            result.append(RankedPlayerDTO(
                rank=row["rank"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=row["team_name"],
                team_logo_url=_logo(row["team_external_id"]),
                position=display_position or "",
                competition_name=row["competition_name"],
                total_pts=float(row["total_pts"]),
                matches_played=row["matches_played"],
                photo_url=row["photo_url"],
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
                dribbles_won=int(row["dribbles_won"] or 0),
                duels_won=int(row["duels_won"] or 0),
                b1_bonus_pts=b1_total,
                b1_bonus_label=b1_label,
            ))
        return result

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
            inner = inner.where(_position_filter(position))
        if name is not None:
            team_match = (
                select(SFASeasonScore.player_id)
                .join(Team, SFASeasonScore.team_id == Team.id)
                .where(
                    *score_filters,
                    _any_unaccent_ilike(Team.name, _team_search_terms(name)),
                )
            )
            inner = inner.where(
                or_(
                    _unaccent_ilike(Player.name, name),
                    Player.id.in_(team_match),
                )
            )

        if position is not None:
            exact_stmt = (
                select(
                    Player.id.label("player_id"),
                    Player.name.label("player_name"),
                    Player.position,
                    Team.name.label("team_name"),
                    SFASeasonScore.competition_id,
                )
                .join(Player, SFASeasonScore.player_id == Player.id)
                .join(Team, SFASeasonScore.team_id == Team.id)
                .where(*score_filters, _position_filter(position))
                .group_by(
                    Player.id,
                    Player.name,
                    Player.position,
                    Team.name,
                    SFASeasonScore.competition_id,
                )
            )
            if name is not None:
                exact_stmt = exact_stmt.where(
                    or_(
                        _unaccent_ilike(Player.name, name),
                        Player.id.in_(team_match),
                    )
                )
            rows = (await self._session.execute(exact_stmt)).mappings().all()
            counted: set[int] = set()
            for row in rows:
                display_position = position_for_context(
                    _position_value(row["position"]),
                    player_name=row["player_name"],
                    team_name=row["team_name"],
                    competition_id=row["competition_id"],
                )
                if display_position == position:
                    counted.add(row["player_id"])
            return len(counted)

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

    async def resolve_rules_version_id_for_season(
        self, season: str, preferred_rules_version_id: int | None = None,
    ) -> int | None:
        if preferred_rules_version_id is not None:
            preferred_count = await self._session.scalar(
                select(func.count())
                .select_from(SFASeasonScore)
                .where(
                    SFASeasonScore.season == season,
                    SFASeasonScore.rules_version_id == preferred_rules_version_id,
                )
            )
            if preferred_count and preferred_count > 0:
                return preferred_rules_version_id

        latest_rules_version = await self._session.scalar(
            select(func.max(SFASeasonScore.rules_version_id)).where(
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id.is_not(None),
            )
        )
        if latest_rules_version is not None:
            return int(latest_rules_version)

        null_count = await self._session.scalar(
            select(func.count())
            .select_from(SFASeasonScore)
            .where(
                SFASeasonScore.season == season,
                SFASeasonScore.rules_version_id.is_(None),
            )
        )
        return None if null_count and null_count > 0 else preferred_rules_version_id

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

    async def get_b1_bonus_for_player(
        self, player_id: int, season: str, rules_version_id: int | None = None,
    ) -> tuple[float, str | None]:
        birth_date = await self._session.scalar(
            select(Player.birth_date).where(Player.id == player_id)
        )
        age_label = _b1_label_for_birth_date(birth_date)

        filters = [
            PlayerEventScore.player_id == player_id,
            PlayerEventScore.season == season,
            PlayerEventScore.calculation_details["b1_bonus"]["applied"].astext == "true",
        ]
        if rules_version_id is not None:
            filters.append(PlayerEventScore.rules_version_id == rules_version_id)

        b1_age = cast(
            PlayerEventScore.calculation_details["b1_bonus"]["age_at_match"].astext,
            Integer,
        )
        b1_pts = cast(
            PlayerEventScore.calculation_details["b1_bonus"]["b1_per_event"].astext,
            Numeric,
        )
        stmt = select(
            func.coalesce(func.sum(case((b1_age <= 20, b1_pts), else_=0)), 0),
            func.coalesce(func.sum(case((b1_age >= 35, b1_pts), else_=0)), 0),
        ).where(*filters)

        row = (await self._session.execute(stmt)).first()
        if row is None:
            return (0.0, age_label)

        young_pts = float(row[0] or 0)
        veteran_pts = float(row[1] or 0)
        total = round(young_pts + veteran_pts, 2)
        if total <= 0:
            return (0.0, age_label)

        label = "Veterano" if veteran_pts >= young_pts and veteran_pts > 0 else "Promesa"
        return (total, label)

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
                Team.name.label("team_name"),
                Team.external_id.label("team_external_id"),
                Player.position,
                Competition.name.label("competition_name"),
                best_comp.c.competition_id.label("competition_id"),
                agg.c.sum_pts.label("total_pts"),
                agg.c.sum_matches.label("matches_played"),
                Player.photo_url,
                agg.c.sum_goals.label("goals"),
                agg.c.sum_assists.label("assists"),
                agg.c.sum_dribbles.label("dribbles_won"),
                agg.c.sum_duels.label("duels_won"),
            )
            .join(agg, Player.id == agg.c.player_id)
            .join(best_comp, Player.id == best_comp.c.player_id)
            .join(Team, best_comp.c.team_id == Team.id)
            .join(Competition, best_comp.c.competition_id == Competition.id)
            .order_by(agg.c.sum_pts.desc())
        )
        if position is not None:
            stmt = stmt.where(_position_filter(position))

        if name is not None:
            sub = stmt.subquery()
            final = (
                select(sub)
                .where(_player_or_team_name_filter(sub.c.player_name, sub.c.team_name, name))
                .limit(limit)
            )
        else:
            final = stmt.limit(limit)

        rows = (await self._session.execute(final)).mappings().all()

        def _logo(ext_id: int | None) -> str | None:
            return f"https://media.api-sports.io/football/teams/{ext_id}.png" if ext_id else None

        result: list[RankedPlayerDTO] = []
        for row in rows:
            display_position = position_for_context(
                _position_value(row["position"]),
                player_name=row["player_name"],
                team_name=row["team_name"],
                competition_id=row["competition_id"],
            )
            if position is not None and display_position != position:
                continue
            result.append(RankedPlayerDTO(
                rank=row["rank"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team_name=row["team_name"],
                team_logo_url=_logo(row["team_external_id"]),
                position=display_position or "",
                competition_name=row["competition_name"],
                total_pts=float(row["total_pts"]),
                matches_played=row["matches_played"],
                photo_url=row["photo_url"],
                goals=int(row["goals"] or 0),
                assists=int(row["assists"] or 0),
                dribbles_won=int(row["dribbles_won"] or 0),
                duels_won=int(row["duels_won"] or 0),
            ))
        return result

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
            inner = inner.where(_position_filter(position))
        if name is not None:
            team_match = (
                select(SFASeasonScore.player_id)
                .join(Team, SFASeasonScore.team_id == Team.id)
                .where(
                    *score_filters,
                    _any_unaccent_ilike(Team.name, _team_search_terms(name)),
                )
            )
            inner = inner.where(
                or_(
                    _unaccent_ilike(Player.name, name),
                    Player.id.in_(team_match),
                )
            )

        if position is not None:
            exact_stmt = (
                select(
                    Player.id.label("player_id"),
                    Player.name.label("player_name"),
                    Player.position,
                    Team.name.label("team_name"),
                    SFASeasonScore.competition_id,
                )
                .join(Player, SFASeasonScore.player_id == Player.id)
                .join(Team, SFASeasonScore.team_id == Team.id)
                .where(*score_filters, _position_filter(position))
                .group_by(
                    Player.id,
                    Player.name,
                    Player.position,
                    Team.name,
                    SFASeasonScore.competition_id,
                )
            )
            if name is not None:
                exact_stmt = exact_stmt.where(
                    or_(
                        _unaccent_ilike(Player.name, name),
                        Player.id.in_(team_match),
                    )
                )
            rows = (await self._session.execute(exact_stmt)).mappings().all()
            counted: set[int] = set()
            for row in rows:
                display_position = position_for_context(
                    _position_value(row["position"]),
                    player_name=row["player_name"],
                    team_name=row["team_name"],
                    competition_id=row["competition_id"],
                )
                if display_position == position:
                    counted.add(row["player_id"])
            return len(counted)

        subq = inner.subquery()
        stmt = select(func.count()).select_from(subq)
        return (await self._session.execute(stmt)).scalar_one()

    async def get_total_player_stats_all_seasons(
        self, player_id: int, rules_version_id: int | None = None,
    ) -> tuple[int, int, int, float]:
        scores = _historical_scores_scope(rules_version_id)
        stmt = (
            select(
                scores.c.matches_played,
                scores.c.breakdown,
                scores.c.total_pts,
                scores.c.achievement_bonus_pts,
            )
            .select_from(scores)
            .where(scores.c.player_id == player_id)
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
        scores = _historical_scores_scope(rules_version_id)
        per_player = (
            select(
                scores.c.player_id,
                func.sum(
                    scores.c.total_pts + scores.c.achievement_bonus_pts
                ).label("sum_pts"),
            )
            .select_from(scores)
            .where(
                scores.c.player_id != player_id,
            )
            .group_by(scores.c.player_id)
            .subquery()
        )
        stmt = select(func.count()).where(per_player.c.sum_pts > total_pts)
        return (await self._session.execute(stmt)).scalar_one() + 1
