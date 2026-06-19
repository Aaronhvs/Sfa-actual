from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Date, cast, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.scoring.entities import PlayerEventScore
from sfa.domain.scoring_ports import PlayerEventRawContextDTO, PlayerEventScoreRepositoryPort
from sfa.domain.player_position_overrides import position_for_context
from sfa.infrastructure.models.competitions.models import CompetitionStage
from sfa.infrastructure.models.events.models import PlayerEvent
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_event_scores.models import PlayerEventScore as PlayerEventScoreModel
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.team_strengths.models import TeamStrength

logger = logging.getLogger(__name__)

_FALLBACK_TEAM_POS = 10  # used when standings data is unavailable for historical events


class PlayerEventScoreRepository(PlayerEventScoreRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_events_for_recalc(
        self,
        season: str,
        competition_id: int | None,
        match_id: int | None,
        player_id: int | None,
    ) -> list[PlayerEventRawContextDTO]:
        """Fetch all PlayerEvents in scope with their full raw context for re-scoring.

        For each event we need:
        - The event itself (minute, score_diff, psxg, event_type, team_pos context)
        - The fixture's competition and stage factor
        - The player's position
        - Player stats from the same fixture (for STATS events)

        player_team_pos / rival_team_pos fall back to _FALLBACK_TEAM_POS when NULL
        (historical events ingested before migration 0012).
        """
        # Build base filter
        filters = [Fixture.season == season]
        if competition_id is not None:
            filters.append(Fixture.competition_id == competition_id)
        if match_id is not None:
            filters.append(PlayerEvent.fixture_id == match_id)
        if player_id is not None:
            filters.append(PlayerEvent.player_id == player_id)

        # Aliases for team_strengths (home/away)
        ts_home = TeamStrength.__table__.alias("ts_home")
        ts_away = TeamStrength.__table__.alias("ts_away")

        # Main query: events JOIN fixtures LEFT JOIN competition_stages JOIN players
        #             LEFT JOIN team_strengths (home + away) for v2 M1
        # competition_stages is LEFT JOIN so competitions without configured stages
        # (e.g. World Cup group stage) still produce events; stage_factor defaults to 1.0.
        stmt = (
            select(
                PlayerEvent.id,
                PlayerEvent.player_id,
                PlayerEvent.fixture_id,
                PlayerEvent.minute,
                PlayerEvent.event_type,
                PlayerEvent.score_diff,
                PlayerEvent.psxg,
                PlayerEvent.player_team_pos,
                PlayerEvent.rival_team_pos,
                PlayerEvent.is_away,
                Fixture.competition_id,
                Fixture.home_team_id,
                Fixture.away_team_id,
                Fixture.season,
                func.coalesce(CompetitionStage.stage_factor, 1.0).label("stage_factor"),
                Player.position,
                Player.name.label("player_name"),
                Player.birth_date.label("player_birth_date"),
                cast(Fixture.played_at, Date).label("fixture_date"),
                ts_home.c.strength.label("home_team_strength"),
                ts_away.c.strength.label("away_team_strength"),
            )
            .join(Fixture, PlayerEvent.fixture_id == Fixture.id)
            .outerjoin(
                CompetitionStage,
                (CompetitionStage.competition_id == Fixture.competition_id)
                & (CompetitionStage.stage == Fixture.stage),
            )
            .join(Player, PlayerEvent.player_id == Player.id)
            .outerjoin(
                ts_home,
                (ts_home.c.team_id == Fixture.home_team_id)
                & (ts_home.c.season == Fixture.season)
                & (ts_home.c.competition_id == Fixture.competition_id),
            )
            .outerjoin(
                ts_away,
                (ts_away.c.team_id == Fixture.away_team_id)
                & (ts_away.c.season == Fixture.season)
                & (ts_away.c.competition_id == Fixture.competition_id),
            )
            .where(*filters)
        )
        event_rows = (await self._session.execute(stmt)).all()

        if not event_rows:
            return []

        # Collect fixture_ids to fetch stats in bulk
        fixture_ids = list({r.fixture_id for r in event_rows})
        player_ids = list({r.player_id for r in event_rows})

        stats_stmt = (
            select(PlayerStats)
            .where(
                PlayerStats.fixture_id.in_(fixture_ids),
                PlayerStats.player_id.in_(player_ids),
            )
        )
        stats_result = await self._session.execute(stats_stmt)
        stats_map: dict[tuple[int, int], PlayerStats] = {
            (s.player_id, s.fixture_id): s
            for s in stats_result.scalars().all()
        }

        dtos: list[PlayerEventRawContextDTO] = []
        for row in event_rows:
            stats = stats_map.get((row.player_id, row.fixture_id))

            player_team_pos = row.player_team_pos if row.player_team_pos is not None else _FALLBACK_TEAM_POS
            rival_team_pos = row.rival_team_pos if row.rival_team_pos is not None else _FALLBACK_TEAM_POS

            # Determine which team the player belongs to and assign strengths accordingly
            is_away = bool(row.is_away)
            if is_away:
                player_team_strength = (
                    float(row.away_team_strength) if row.away_team_strength is not None else None
                )
                rival_team_strength = (
                    float(row.home_team_strength) if row.home_team_strength is not None else None
                )
            else:
                player_team_strength = (
                    float(row.home_team_strength) if row.home_team_strength is not None else None
                )
                rival_team_strength = (
                    float(row.away_team_strength) if row.away_team_strength is not None else None
                )

            dtos.append(PlayerEventRawContextDTO(
                event_id=row.id,
                player_id=row.player_id,
                fixture_id=row.fixture_id,
                competition_id=row.competition_id,
                season=row.season,
                event_type=row.event_type.value if hasattr(row.event_type, "value") else str(row.event_type),
                minute=row.minute,
                score_diff=row.score_diff,
                psxg=float(row.psxg) if row.psxg is not None else None,
                player_team_pos=player_team_pos,
                rival_team_pos=rival_team_pos,
                is_away=row.is_away,
                stage_factor=float(row.stage_factor),
                goals=stats.goals if stats else None,
                assists=stats.assists if stats else None,
                shots_on=stats.shots_on if stats else None,
                passes_key=stats.passes_key if stats else None,
                passes_total=stats.passes_total if stats else None,
                passes_accuracy=float(stats.passes_accuracy) if stats else None,
                dribbles_won=stats.dribbles_won if stats else None,
                duels_won=stats.duels_won if stats else None,
                tackles_won=stats.tackles_won if stats else None,
                interceptions=stats.interceptions if stats else None,
                blocks=stats.blocks if stats else None,
                fouls_drawn=stats.fouls_drawn if stats else None,
                fouls_committed=stats.fouls_committed if stats else None,
                cards_yellow=stats.cards_yellow if stats else None,
                cards_red=stats.cards_red if stats else None,
                penalty_won=stats.penalty_won if stats else None,
                dribbles_past=stats.dribbles_past if stats else None,
                rating=float(stats.rating) if stats and stats.rating is not None else None,
                player_position=position_for_context(
                    row.position.value if hasattr(row.position, "value") else str(row.position),
                    player_name=row.player_name,
                    competition_id=row.competition_id,
                ) or "",
                minutes=stats.minutes if stats else None,
                player_team_strength=player_team_strength,
                rival_team_strength=rival_team_strength,
                player_birth_date=row.player_birth_date,
                fixture_date=row.fixture_date,
            ))

        return dtos

    async def upsert_event_score(self, score: PlayerEventScore) -> None:
        stmt = (
            pg_insert(PlayerEventScoreModel)
            .values(
                event_id=score.event_id,
                player_id=score.player_id,
                fixture_id=score.fixture_id,
                season=score.season,
                competition_id=score.competition_id,
                rules_version_id=score.rules_version_id,
                action_type=score.action_type,
                position=score.position,
                base_points=score.base_points,
                m1=score.m1,
                m2=score.m2,
                m3=score.m3,
                m4=score.m4,
                mvisit=score.mvisit,
                mrating=score.mrating,
                combined_before_clamp=score.combined_before_clamp,
                combined_after_clamp=score.combined_after_clamp,
                final_points=score.final_points,
                calculation_details=score.calculation_details,
                created_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                constraint="uq_pes_event_version",
                set_={
                    "base_points": score.base_points,
                    "position": score.position,
                    "m1": score.m1,
                    "m2": score.m2,
                    "m3": score.m3,
                    "m4": score.m4,
                    "mvisit": score.mvisit,
                    "mrating": score.mrating,
                    "combined_before_clamp": score.combined_before_clamp,
                    "combined_after_clamp": score.combined_after_clamp,
                    "final_points": score.final_points,
                    "calculation_details": score.calculation_details,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def event_score_exists(self, event_id: int, rules_version_id: int) -> bool:
        stmt = select(
            select(PlayerEventScoreModel.id)
            .where(
                PlayerEventScoreModel.event_id == event_id,
                PlayerEventScoreModel.rules_version_id == rules_version_id,
            )
            .exists()
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    async def delete_event_scores_for_version(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None,
    ) -> None:
        filters = [
            PlayerEventScoreModel.rules_version_id == rules_version_id,
            PlayerEventScoreModel.season == season,
        ]
        if competition_id is not None:
            filters.append(PlayerEventScoreModel.competition_id == competition_id)
        await self._session.execute(
            delete(PlayerEventScoreModel).where(*filters)
        )
        await self._session.flush()

    async def get_player_event_totals_for_season(
        self,
        player_id: int,
        season: str,
        competition_id: int,
        rules_version_id: int,
    ) -> tuple[float, int]:
        stmt = select(
            func.coalesce(func.sum(PlayerEventScoreModel.final_points), 0).label("total_pts"),
            func.count(PlayerEventScoreModel.fixture_id.distinct()).label("matches_played"),
        ).where(
            PlayerEventScoreModel.player_id == player_id,
            PlayerEventScoreModel.season == season,
            PlayerEventScoreModel.competition_id == competition_id,
            PlayerEventScoreModel.rules_version_id == rules_version_id,
        )
        result = await self._session.execute(stmt)
        row = result.one()
        return float(row.total_pts), int(row.matches_played)

    async def get_players_with_events_in_scope(
        self,
        season: str,
        competition_id: int | None,
        rules_version_id: int,
    ) -> list[int]:
        filters = [
            PlayerEventScoreModel.season == season,
            PlayerEventScoreModel.rules_version_id == rules_version_id,
        ]
        if competition_id is not None:
            filters.append(PlayerEventScoreModel.competition_id == competition_id)

        stmt = (
            select(PlayerEventScoreModel.player_id)
            .where(*filters)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_competition_name_map(self) -> dict[int, str]:
        from sfa.infrastructure.models.competitions.models import Competition
        stmt = select(Competition.id, Competition.name)
        result = await self._session.execute(stmt)
        return {row.id: row.name for row in result.all()}

    async def get_season_score_breakdown(
        self,
        player_id: int,
        season: str,
        competition_id: int,
        rules_version_id: int,
    ) -> dict:
        stmt = (
            select(
                PlayerEventScoreModel.action_type,
                func.count(PlayerEventScoreModel.id).label("cnt"),
                func.sum(PlayerEventScoreModel.final_points).label("pts"),
            )
            .where(
                PlayerEventScoreModel.player_id == player_id,
                PlayerEventScoreModel.season == season,
                PlayerEventScoreModel.competition_id == competition_id,
                PlayerEventScoreModel.rules_version_id == rules_version_id,
            )
            .group_by(PlayerEventScoreModel.action_type)
        )
        result = await self._session.execute(stmt)
        breakdown: dict = {}
        for action_type, cnt, pts in result.all():
            breakdown[action_type] = {"count": int(cnt), "pts": round(float(pts), 2)}
        return breakdown

    async def bulk_rebuild_season_scores(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None = None,
    ) -> int:
        """Rebuild all season scores in scope with one INSERT ... SELECT."""
        base_filter = "rules_version_id = :rules_version_id AND season = :season"
        if competition_id is not None:
            base_filter += " AND competition_id = :competition_id"

        sql = text(f"""
            WITH per_action AS (
                SELECT
                    player_id,
                    competition_id,
                    season,
                    rules_version_id,
                    action_type,
                    COUNT(*) AS cnt,
                    ROUND(SUM(final_points)::numeric, 2) AS action_pts
                FROM player_event_scores
                WHERE {base_filter}
                GROUP BY player_id, competition_id, season, rules_version_id, action_type
            ),
            player_totals AS (
                SELECT
                    player_id,
                    competition_id,
                    season,
                    rules_version_id,
                    ROUND(SUM(action_pts)::numeric, 2) AS total_pts
                FROM per_action
                GROUP BY player_id, competition_id, season, rules_version_id
            ),
            breakdown_agg AS (
                SELECT
                    pa.player_id,
                    pa.competition_id,
                    pa.season,
                    pa.rules_version_id,
                    jsonb_object_agg(
                        pa.action_type,
                        jsonb_build_object(
                            'count', pa.cnt,
                            'pts', pa.action_pts,
                            'pct', CASE
                                WHEN pt.total_pts = 0 THEN 0.0
                                ELSE ROUND((pa.action_pts / pt.total_pts * 100)::numeric, 1)
                            END
                        )
                    ) AS breakdown
                FROM per_action pa
                JOIN player_totals pt
                    ON pa.player_id = pt.player_id
                    AND pa.competition_id = pt.competition_id
                    AND pa.season = pt.season
                    AND pa.rules_version_id = pt.rules_version_id
                GROUP BY pa.player_id, pa.competition_id, pa.season, pa.rules_version_id
            ),
            match_counts AS (
                SELECT
                    player_id,
                    competition_id,
                    season,
                    rules_version_id,
                    COUNT(DISTINCT fixture_id) AS matches_played
                FROM player_event_scores
                WHERE {base_filter}
                GROUP BY player_id, competition_id, season, rules_version_id
            ),
            team_minutes AS (
                SELECT
                    ps.player_id,
                    f.competition_id,
                    ps.season,
                    ps.team_id,
                    SUM(ps.minutes) AS total_minutes,
                    ROW_NUMBER() OVER (
                        PARTITION BY ps.player_id, f.competition_id, ps.season
                        ORDER BY SUM(ps.minutes) DESC, ps.team_id
                    ) AS rn
                FROM player_stats ps
                JOIN fixtures f ON f.id = ps.fixture_id
                WHERE ps.season = :season
                  AND ps.team_id IS NOT NULL
                  {f"AND f.competition_id = :competition_id" if competition_id is not None else ""}
                GROUP BY ps.player_id, f.competition_id, ps.season, ps.team_id
            ),
            representative_team AS (
                SELECT player_id, competition_id, season, team_id
                FROM team_minutes
                WHERE rn = 1
            )
            INSERT INTO sfa_season_scores (
                player_id,
                competition_id,
                team_id,
                season,
                rules_version_id,
                total_pts,
                achievement_bonus_pts,
                matches_played,
                breakdown,
                last_updated
            )
            SELECT
                pt.player_id,
                pt.competition_id,
                rt.team_id,
                pt.season,
                pt.rules_version_id,
                pt.total_pts,
                0,
                mc.matches_played,
                ba.breakdown,
                NOW()
            FROM player_totals pt
            JOIN representative_team rt
                ON pt.player_id = rt.player_id
                AND pt.competition_id = rt.competition_id
                AND pt.season = rt.season
            JOIN match_counts mc
                ON pt.player_id = mc.player_id
                AND pt.competition_id = mc.competition_id
                AND pt.season = mc.season
                AND pt.rules_version_id = mc.rules_version_id
            JOIN breakdown_agg ba
                ON pt.player_id = ba.player_id
                AND pt.competition_id = ba.competition_id
                AND pt.season = ba.season
                AND pt.rules_version_id = ba.rules_version_id
            ON CONFLICT (player_id, competition_id, season, rules_version_id)
            WHERE rules_version_id IS NOT NULL
            DO UPDATE SET
                team_id = EXCLUDED.team_id,
                total_pts = EXCLUDED.total_pts,
                matches_played = EXCLUDED.matches_played,
                breakdown = EXCLUDED.breakdown,
                last_updated = EXCLUDED.last_updated
            RETURNING player_id
        """)
        params: dict[str, object] = {
            "rules_version_id": rules_version_id,
            "season": season,
        }
        if competition_id is not None:
            params["competition_id"] = competition_id

        result = await self._session.execute(sql, params)
        await self._session.flush()
        return len(result.fetchall())
