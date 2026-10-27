from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.event_integrity import ACTION_TYPES, Appearance, FixtureSnapshot, IntegrityPlan, StoredAction, digest
from sfa.domain.event_integrity_ports import SeasonEventIntegrityRepositoryPort
from sfa.infrastructure.repositories.season_repository import SeasonRepository


class SeasonEventIntegrityRepository(SeasonEventIntegrityRepositoryPort):
    """Narrow raw-event delta. Caller controls transactions and current-version rebuilding."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._scope = None

    async def get_context_conflict_fixture_ids(self) -> tuple[int, ...]:
        scope = await SeasonRepository(self._session).resolve_scope("season-2025")
        parameters, clauses = {}, []
        for index, source in enumerate(scope.sources):
            parameters[f"season{index}"] = source.season
            parameters[f"competitions{index}"] = list(source.competition_ids)
            clauses.append(f"(f.season=:season{index} AND f.competition_id=ANY(:competitions{index}))")
        condition = " OR ".join(clauses)
        rows = await self._session.execute(
            text(f"""
            SELECT DISTINCT pe.fixture_id FROM player_events pe JOIN fixtures f ON f.id=pe.fixture_id
            WHERE ({condition}) AND pe.team_id IN(f.home_team_id,f.away_team_id) AND (
              pe.is_away IS DISTINCT FROM (pe.team_id=f.away_team_id)
              OR (pe.score_before ~ '^[0-9]+:[0-9]+$' AND pe.score_diff IS DISTINCT FROM
                CASE WHEN pe.team_id=f.away_team_id
                  THEN split_part(pe.score_before,':',2)::int-split_part(pe.score_before,':',1)::int
                  ELSE split_part(pe.score_before,':',1)::int-split_part(pe.score_before,':',2)::int END))
            ORDER BY pe.fixture_id
        """),
            parameters,
        )
        return tuple(rows.scalars())

    async def snapshot(self, fixture_id: int) -> FixtureSnapshot:
        fixture = (
            (
                await self._session.execute(
                    text("""
            SELECT f.*, h.external_id home_external_id, a.external_id away_external_id
            FROM fixtures f JOIN teams h ON h.id=f.home_team_id JOIN teams a ON a.id=f.away_team_id
            WHERE f.id=:id
        """),
                    {"id": fixture_id},
                )
            )
            .mappings()
            .one()
        )
        if self._scope is None:
            self._scope = await SeasonRepository(self._session).resolve_scope("season-2025")
        scope = self._scope
        if not scope or not any(
            fixture["season"] == s.season and fixture["competition_id"] in s.competition_ids for s in scope.sources
        ):
            raise ValueError("Fixture is outside season-2025")
        if fixture["status"] not in {"FT", "AET", "PEN"}:
            raise ValueError("Fixture is not final")
        images = {}
        # These are fixed table identifiers, never values supplied by a caller.
        for table in ["player_events", "player_stats", "player_event_scores", "fixture_team_strengths"]:
            order = "team_id" if table == "fixture_team_strengths" else "id"
            rows = await self._session.execute(
                text(f"SELECT to_jsonb(t) image FROM {table} t WHERE fixture_id=:id ORDER BY {order}"),
                {"id": fixture_id},
            )
            images[table] = list(rows.scalars())
        images["fixture"] = dict(fixture)
        players = (
            (
                await self._session.execute(
                    text("""
            SELECT ps.player_id,p.external_id,ps.team_id,t.external_id team_external_id,
                   ps.goals,ps.assists,ps.minutes
            FROM player_stats ps JOIN players p ON p.id=ps.player_id LEFT JOIN teams t ON t.id=ps.team_id
            WHERE ps.fixture_id=:id ORDER BY ps.player_id
        """),
                    {"id": fixture_id},
                )
            )
            .mappings()
            .all()
        )
        images["actors"] = [dict(row) for row in players]
        appearances = tuple(Appearance(**dict(row)) for row in players)
        actions = tuple(
            StoredAction(
                **{
                    k: row[k]
                    for k in ["player_id", "team_id", "minute", "event_type", "score_before", "score_diff", "is_away"]
                },
                event_id=row["id"],
            )
            for row in images["player_events"]
            if row["event_type"] in ACTION_TYPES
        )
        stats_actions = tuple(
            StoredAction(
                event_id=row["id"],
                **{
                    k: row[k]
                    for k in [
                        "player_id",
                        "team_id",
                        "minute",
                        "event_type",
                        "score_before",
                        "score_diff",
                        "is_away",
                    ]
                },
            )
            for row in images["player_events"]
            if row["event_type"] == "STATS"
        )
        image_json = json.dumps(images, sort_keys=True, default=str)
        stats_players = {row["player_id"] for row in images["player_events"] if row["event_type"] == "STATS"}
        missing_stats = tuple(a.player_id for a in appearances if a.player_id not in stats_players)
        return FixtureSnapshot(
            fixture_id,
            fixture["external_id"],
            fixture["competition_id"],
            fixture["season"],
            fixture["home_external_id"],
            fixture["away_external_id"],
            fixture["home_goals"],
            fixture["away_goals"],
            appearances,
            actions,
            digest(images),
            image_json,
            missing_stats,
            stats_actions,
            fixture["home_team_id"],
            fixture["away_team_id"],
            fixture["status"],
        )

    async def apply(self, plan: IntegrityPlan) -> int:
        if plan.pending:
            raise ValueError("Pending plans cannot be applied")
        await self._session.execute(
            text("SELECT id FROM fixtures WHERE id=:id FOR UPDATE NOWAIT"), {"id": plan.fixture_id}
        )
        before = await self.snapshot(plan.fixture_id)
        if before.fingerprint != plan.fingerprint:
            raise ValueError("Concurrent fixture update; integrity CAS failed")
        if plan.fixture_goals is not None:
            result = await self._session.execute(
                text("""
                UPDATE fixtures SET home_goals=:home,away_goals=:away
                WHERE id=:id RETURNING home_goals,away_goals
            """),
                {"id": plan.fixture_id, "home": plan.fixture_goals[0], "away": plan.fixture_goals[1]},
            )
            if tuple(result.one()) != plan.fixture_goals:
                raise ValueError("Normalized final-score repair was blocked")
        for revision in plan.appearance_changes:
            old, new = revision.before, revision.after
            if (old.player_id, old.external_id, old.team_id, old.team_external_id) != (
                new.player_id,
                new.external_id,
                new.team_id,
                new.team_external_id,
            ):
                raise ValueError("Appearance identity cannot change in a counter repair")
            result = await self._session.execute(
                text("""
                UPDATE player_stats SET goals=:goals,assists=:assists,minutes=:minutes
                WHERE player_id=:player_id AND fixture_id=:fixture_id
                  AND goals=:old_goals AND assists=:old_assists AND minutes=:old_minutes
                RETURNING goals,assists,minutes
            """),
                {
                    "goals": new.goals,
                    "assists": new.assists,
                    "minutes": new.minutes,
                    "player_id": old.player_id,
                    "fixture_id": plan.fixture_id,
                    "old_goals": old.goals,
                    "old_assists": old.assists,
                    "old_minutes": old.minutes,
                },
            )
            actual = result.mappings().one_or_none()
            if actual is None or dict(actual) != {"goals": new.goals, "assists": new.assists, "minutes": new.minutes}:
                raise ValueError("Appearance counter repair was blocked")
        for revision in plan.changes:
            old, new = revision.before, revision.after
            if old:
                # Scores will be recreated as a complete current-version projection. No implicit cascade.
                await self._session.execute(
                    text("DELETE FROM player_event_scores WHERE event_id=:id"), {"id": old.event_id}
                )
            if new is None:
                result = await self._session.execute(
                    text("DELETE FROM player_events WHERE id=:id AND fixture_id=:fixture"),
                    {"id": old.event_id, "fixture": plan.fixture_id},
                )
                if result.rowcount != 1:
                    raise ValueError("Raw event retirement was blocked")
                continue
            values = asdict(new)
            values.pop("source_sequence")
            values["fixture_id"] = plan.fixture_id
            if old:
                values["id"] = old.event_id
                result = await self._session.execute(
                    text("""
                    UPDATE player_events SET player_id=:player_id,team_id=:team_id,minute=:minute,
                      event_type=:event_type,score_before=:score_before,score_diff=:score_diff,is_away=:is_away,
                      psxg=CASE WHEN player_id=:player_id THEN psxg ELSE NULL END
                    WHERE id=:id AND fixture_id=:fixture_id RETURNING id
                """),
                    values,
                )
            else:
                result = await self._session.execute(
                    text("""
                    INSERT INTO player_events(player_id,fixture_id,team_id,minute,event_type,score_before,
                      score_diff,is_away,m1,m2,m3,m4,mvisit,pts)
                    VALUES(:player_id,:fixture_id,:team_id,:minute,:event_type,:score_before,:score_diff,
                      :is_away,1,1,1,1,1,0) RETURNING id
                """),
                    values,
                )
            event_id = result.scalar_one_or_none()
            if event_id is None:
                raise ValueError("Raw event write was blocked")
            actual = (
                (
                    await self._session.execute(
                        text("""
                SELECT player_id,team_id,minute,event_type,score_before,score_diff,is_away
                FROM player_events WHERE id=:id
            """),
                        {"id": event_id},
                    )
                )
                .mappings()
                .one()
            )
            expected = {k: v for k, v in asdict(new).items() if k != "source_sequence"}
            if dict(actual) != expected:
                raise ValueError("Raw event guard retained different values")
        await self._session.execute(
            text("UPDATE fixtures SET score_source='sfa_integrity_v1' WHERE id=:id"), {"id": plan.fixture_id}
        )
        return len(plan.changes) + len(plan.appearance_changes) + int(plan.fixture_goals is not None)
