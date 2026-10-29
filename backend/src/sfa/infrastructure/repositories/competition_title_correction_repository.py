from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sfa.domain.title_correction import (
    TitleCorrectionRepositoryPort,
    TitleCorrectionSnapshot,
    fingerprint,
    validate_evidence,
)
from sfa.domain.trophy_results import INTERCONTINENTAL_NAME
from sfa.infrastructure.models.competitions.models import Competition
from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.player_stats.models import PlayerStats
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.teams.models import Team
from sfa.infrastructure.repositories.competition_achievement_repository import CompetitionAchievementRepository

TABLES = (
    "competitions", "teams", "players", "fixtures", "player_stats", "competition_achievements",
    "player_achievement_bonuses", "sfa_season_scores", "individual_honors",
)
GUARDS = (
    "player_events", "player_event_scores", "fixture_team_strengths", "scoring_rules_versions",
    "player_position_assignments", "position_scope_classifications", "position_correction_batches",
    "standing_snapshots",
)


class CompetitionTitleCorrectionRepository(TitleCorrectionRepositoryPort):
    """Private, bounded 2025 repair; no provider calls or scoring logic here."""

    def __init__(self, session, achievements: CompetitionAchievementRepository) -> None:
        self._session = session
        self._achievements = achievements

    async def lock(self) -> None:
        self._session.info["position_publication_exclusive"] = True
        if not await self._session.scalar(text("SELECT pg_try_advisory_xact_lock(736615320261019)")):
            raise ValueError("Title publication busy; retry a fresh transaction")
        await self._session.execute(text("SET LOCAL lock_timeout='5s'"))
        await self._session.execute(text("SET LOCAL work_mem='32MB'"))

    async def allow_publication(self, allowed: bool) -> None:
        await self._session.execute(text("SELECT set_config('sfa.position_publication',:value,true)"),
                                    {"value": "on" if allowed else "off"})

    @staticmethod
    def _conditions(evidence: str) -> dict[str, str]:
        data = validate_evidence(evidence)
        players = data["intercontinental-players"]["payload"]["response"]
        player_ids = sorted({int(p["player"]["id"]) for team in players for p in team["players"]})
        teams = {85, 47, 127}
        for f in data["ligue1-fixtures"]["payload"]["response"]:
            if f["fixture"]["id"] == 1388000:
                teams.update(int(t["id"]) for t in f["teams"].values())
        comp = "competition_id IN(SELECT id FROM competitions WHERE name IN " \
               "('Ligue 1','UEFA Super Cup','FIFA Intercontinental Cup')) AND season='2025'"
        return {
            "competitions": "name IN('Ligue 1','UEFA Super Cup','FIFA Intercontinental Cup')",
            "teams": "external_id IN(" + ",".join(map(str, sorted(teams))) + ")",
            "players": "external_id IN(" + ",".join(map(str, player_ids)) + ")",
            "fixtures": comp,
            "player_stats": f"fixture_id IN(SELECT id FROM fixtures WHERE {comp})",
            "competition_achievements": comp,
            "player_achievement_bonuses": comp,
            "sfa_season_scores": comp,
            "individual_honors": "scope_key='season-2025'",
        }

    async def snapshot(self, evidence: str) -> TitleCorrectionSnapshot:
        conditions = self._conditions(evidence)
        rows, guards = {}, {}
        for table, condition in conditions.items():
            rows[table] = (await self._session.execute(text(
                f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]'::jsonb) FROM {table} t WHERE {condition}"
            ))).scalar_one()
        for table in (*GUARDS, *TABLES):
            condition = "TRUE" if table in GUARDS else f"({conditions[table]}) IS NOT TRUE"
            guards[table] = (await self._session.execute(text(f"""
                SELECT count(*) n,
                  coalesce(sum(pg_catalog.hash_record_extended(t,0)::numeric),0)::text hash_a,
                  coalesce(sum(pg_catalog.hash_record_extended(t,1)::numeric),0)::text hash_b
                FROM {table} t WHERE {condition}
            """))).mappings().one()
            guards[table] = dict(guards[table])
        return TitleCorrectionSnapshot(json.dumps({"rows": rows, "guards": guards}, sort_keys=True))

    async def _fixture(self, source: dict, competition_id: int, source_hash: str, *, duration: int | None = None):
        team_ids = []
        for side in ("home", "away"):
            team = source["teams"][side]
            existing = await self._session.scalar(select(Team.id).where(Team.external_id == team["id"]))
            if existing is None:
                existing = await self._session.scalar(pg_insert(Team).values(
                    external_id=team["id"], name=team["name"], competition_id=competition_id,
                ).returning(Team.id))
            team_ids.append(existing)
        external_id = source["fixture"]["id"]
        old = await self._session.scalar(select(Fixture).where(Fixture.external_id == external_id))
        goals, penalty = source["goals"], source["score"].get("penalty") or {}
        status = source["fixture"]["status"]["short"]
        provenance = {
            "provider": "api-football", "source_hash": source_hash, "verified": True,
            "ordinary_score": [goals["home"], goals["away"]],
            "penalty_score": [penalty.get("home"), penalty.get("away")],
            "policy_version": "intercontinental-title-v1" if duration else None,
            "duration_minutes": duration,
        }
        if old is not None:
            if (old.competition_id, old.season, old.home_team_id, old.away_team_id,
                    old.status, old.home_goals, old.away_goals) != (
                    competition_id, "2025", *team_ids, status, goals["home"], goals["away"]):
                raise ValueError("Persisted fixture conflicts with authoritative result")
            if old.result_provenance and old.result_provenance != provenance:
                raise ValueError("Existing verified result requires a new reviewed correction")
            old.home_penalty_goals, old.away_penalty_goals = penalty.get("home"), penalty.get("away")
            old.result_provenance = provenance
            await self._session.flush()
            return old.id, team_ids
        stage = "regular" if external_id == 1388000 else "final"
        fixture_id = await self._session.scalar(pg_insert(Fixture).values(
            external_id=external_id, competition_id=competition_id, home_team_id=team_ids[0],
            away_team_id=team_ids[1], stage=stage, season="2025",
            played_at=datetime.fromisoformat(source["fixture"]["date"]),
            matchday=34 if stage == "regular" else None, status=status,
            home_goals=goals["home"], away_goals=goals["away"], score_source="api_football",
            home_penalty_goals=penalty.get("home"), away_penalty_goals=penalty.get("away"),
            result_provenance=provenance,
        ).returning(Fixture.id))
        return fixture_id, team_ids

    async def import_evidence(self, evidence: str) -> tuple[int, int, int]:
        data = validate_evidence(evidence)
        competitions = dict((await self._session.execute(select(Competition.name, Competition.id))).all())
        league, supercup = competitions["Ligue 1"], competitions["UEFA Super Cup"]
        inter = competitions.get(INTERCONTINENTAL_NAME)
        if inter is None:
            inter = await self._session.scalar(pg_insert(Competition).values(
                name=INTERCONTINENTAL_NAME, country="INT", competition_factor=1, participant_kind="club",
            ).returning(Competition.id))
        fixtures = data["ligue1-fixtures"]["payload"]["response"]
        missing = next(f for f in fixtures if f["fixture"]["id"] == 1388000)
        await self._fixture(missing, league, fingerprint(data["ligue1-fixtures"]))
        regular_ids = set((await self._session.execute(select(Fixture.external_id).where(
            Fixture.competition_id == league, Fixture.season == "2025", Fixture.stage == "regular",
        ))).scalars())
        if regular_ids != {f["fixture"]["id"] for f in fixtures
                           if f["league"]["round"].startswith("Regular Season - ")}:
            raise ValueError("Stored league calendar differs from authoritative season")
        standings = (await self._session.execute(text("""
            SELECT t.external_id,s.position,s.points FROM standing_snapshots s JOIN teams t ON t.id=s.team_id
            WHERE s.competition_id=:league AND s.season='2025' AND s.matchday=34 ORDER BY s.position
        """), {"league": league})).all()
        expected = data["ligue1-standings"]["payload"]["response"][0]["league"]["standings"][0]
        if list(map(tuple, standings)) != [(r["team"]["id"], r["rank"], r["points"]) for r in expected]:
            raise ValueError("Stored final standings differ from authoritative source")
        final = data["supercup-final"]["payload"]["response"][0]
        await self._fixture(final, supercup, fingerprint(data["supercup-final"]))
        final = next(f for f in data["intercontinental-fixtures"]["payload"]["response"]
                     if f["fixture"]["id"] == 1491683)
        fixture_id, team_ids = await self._fixture(
            final, inter, fingerprint(data["intercontinental-fixtures"]), duration=120,
        )
        for team in data["intercontinental-players"]["payload"]["response"]:
            team_id = team_ids[0] if team["team"]["id"] == final["teams"]["home"]["id"] else team_ids[1]
            for participant in team["players"]:
                games = participant["statistics"][0]["games"]
                if not games.get("minutes"):
                    continue
                player = participant["player"]
                player_id = await self._session.scalar(select(Player.id).where(Player.external_id == player["id"]))
                if player_id is None:
                    position = {"G": "GK", "D": "DC", "M": "MC", "F": "DEL"}.get(games.get("position"))
                    if position is None:
                        raise ValueError("New participant has no provider position; no default allowed")
                    player_id = await self._session.scalar(pg_insert(Player).values(
                        external_id=player["id"], name=player["name"], position=position,
                        photo_url=player.get("photo"), position_source="apifootball",
                    ).returning(Player.id))
                # Retain the provider's raw stats and participation. Performance
                # remains unevaluated: no invented context, M1 or scored events.
                existing = await self._session.scalar(select(PlayerStats).where(
                    PlayerStats.player_id == player_id, PlayerStats.fixture_id == fixture_id,
                ))
                if existing is not None:
                    if (existing.team_id, existing.minutes) != (team_id, games["minutes"]):
                        raise ValueError("Participation changed; prepare a new correction")
                    continue
                await self._session.execute(pg_insert(PlayerStats).values(
                    player_id=player_id, fixture_id=fixture_id, team_id=team_id, season="2025",
                    minutes=games["minutes"], appearances=1, **self._statistics(participant["statistics"][0]),
                ))
        # Retire only the two verified relegation-playoff facts, including all
        # their dependants. Other league placements are deliberately untouched.
        false_facts = (await self._session.execute(text("""
            SELECT a.id FROM competition_achievements a JOIN teams t ON t.id=a.team_id
            WHERE a.competition_id=:league AND a.season='2025'
              AND ((t.name='Nice' AND a.phase='winner') OR (t.name='Saint Etienne' AND a.phase='runner_up'))
        """), {"league": league})).scalars().all()
        for achievement_id in false_facts:
            await self._achievements.retire_achievement(achievement_id)
        await self._session.flush()
        return league, supercup, inter

    @staticmethod
    def _statistics(stats: dict) -> dict:
        fields = {
            "goals": ("goals", "total"), "assists": ("goals", "assists"),
            "saves": ("goals", "saves"), "goals_conceded": ("goals", "conceded"),
            "shots_on": ("shots", "on"), "shots_total": ("shots", "total"),
            "passes_key": ("passes", "key"), "passes_total": ("passes", "total"),
            "passes_completed": ("passes", "accuracy"), "dribbles_won": ("dribbles", "success"),
            "dribbles_attempts": ("dribbles", "attempts"), "dribbles_past": ("dribbles", "past"),
            "duels_won": ("duels", "won"), "duels_total": ("duels", "total"),
            "tackles_won": ("tackles", "total"), "interceptions": ("tackles", "interceptions"),
            "blocks": ("tackles", "blocks"), "fouls_drawn": ("fouls", "drawn"),
            "fouls_committed": ("fouls", "committed"), "cards_yellow": ("cards", "yellow"),
            "cards_red": ("cards", "red"), "penalty_won": ("penalty", "won"),
        }
        values = {field: int((stats.get(group) or {}).get(key) or 0) for field, (group, key) in fields.items()}
        total, completed = values["passes_total"], values["passes_completed"]
        values["passes_accuracy"] = round(min(total, completed) * 100 / total) if total else 0
        rating = stats["games"].get("rating")
        values["rating"] = float(rating) if rating is not None else None
        return values

    async def verify(self, before: TitleCorrectionSnapshot, evidence: str) -> TitleCorrectionSnapshot:
        after = await self.snapshot(evidence)
        original, current = json.loads(before.document), json.loads(after.document)
        if original["guards"] != current["guards"]:
            changed = [t for t in original["guards"] if original["guards"][t] != current["guards"][t]]
            raise ValueError(f"Unrelated data changed: {changed}")
        for table in ("players", "teams", "competitions", "player_stats"):
            by_id = {r["id"]: r for r in current["rows"][table]}
            if any(by_id.get(row["id"]) != row for row in original["rows"][table]):
                raise ValueError(f"Existing {table} changed")
        for row in original["rows"]["fixtures"]:
            actual = next((r for r in current["rows"]["fixtures"] if r["id"] == row["id"]), None)
            ignored = {"home_penalty_goals", "away_penalty_goals", "result_provenance"} \
                if row["external_id"] == 1377400 else set()
            if actual is None or any(actual[k] != value for k, value in row.items() if k not in ignored):
                raise ValueError("An unrelated fixture changed")
        for row in current["rows"]["sfa_season_scores"]:
            old = next((r for r in original["rows"]["sfa_season_scores"] if r["id"] == row["id"]), None)
            if old and any(old[k] != row[k] for k in row if k not in {"achievement_bonus_pts", "sfa_total_pts"}):
                raise ValueError("Existing performance rollup changed")
            if abs(row["sfa_total_pts"] - row["total_pts"] - row["achievement_bonus_pts"]) > .015:
                raise ValueError("Generated bonus total is inconsistent")
            bonuses = [r["final_bonus"] for r in current["rows"]["player_achievement_bonuses"]
                       if (r["player_id"], r["competition_id"], r["season"], r["rules_version_id"]) ==
                       (row["player_id"], row["competition_id"], row["season"], row["rules_version_id"])]
            if abs(sum(bonuses) - row["achievement_bonus_pts"]) > .015:
                raise ValueError("Bonus rollup is inconsistent")
        champions = (await self._session.execute(text("""
            SELECT c.name,a.phase FROM competition_achievements a JOIN competitions c ON c.id=a.competition_id
            JOIN teams t ON t.id=a.team_id WHERE t.external_id=85 AND a.season='2025'
        """))).all()
        if not {("Ligue 1", "champion"), ("UEFA Super Cup", "winner"),
                (INTERCONTINENTAL_NAME, "winner")}.issubset(set(champions)):
            raise ValueError("Expected PSG titles are missing")
        return after

    async def restore(self, before: TitleCorrectionSnapshot, after: TitleCorrectionSnapshot, evidence: str) -> None:
        if (await self.snapshot(evidence)).fingerprint != after.fingerprint:
            raise ValueError("Restore CAS failed")
        original, current = json.loads(before.document)["rows"], json.loads(after.document)["rows"]
        # Delete only newly inserted IDs, in dependency order. Existing rows are
        # restored in place, including their IDs and timestamps.
        for table in reversed(TABLES):
            old_ids = {r["id"] for r in original[table]}
            new_ids = [r["id"] for r in current[table] if r["id"] not in old_ids]
            if new_ids:
                await self._session.execute(text(f"DELETE FROM {table} WHERE id=ANY(:ids)"), {"ids": new_ids})
        for table in TABLES:
            columns = (await self._session.execute(text("""
                SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(:table)
                  AND attnum>0 AND NOT attisdropped AND attgenerated='' ORDER BY attnum
            """), {"table": table})).scalars().all()
            if not original[table]:
                continue
            names = ",".join('"' + c + '"' for c in columns)
            updates = ",".join(f'"{c}"=excluded."{c}"' for c in columns if c != "id")
            await self._session.execute(text(f"""
                INSERT INTO {table} ({names}) SELECT {names} FROM jsonb_populate_recordset(NULL::{table},
                  CAST(:rows AS jsonb)) ON CONFLICT(id) DO UPDATE SET {updates}
            """), {"rows": json.dumps(original[table])})
        await self._session.flush()
