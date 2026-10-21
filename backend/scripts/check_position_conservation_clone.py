"""Verify legacy reingestion guards and new-match continuity inside a rolled-back clone transaction."""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from sfa.core.dependencies import get_position_correction_use_cases
from sfa.domain.player_positions.publication import PositionCorrectionRequest
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.models.enums import EventType
from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository


async def main():
    async with AsyncSessionLocal(info={"position_publication_exclusive": True}) as session:
        assert (await session.scalar(text("SELECT current_database()"))).startswith("sfa_positions_validation_")
        request = PositionCorrectionRequest(
            35, 1496, 1, 529, "2026", "DEL", (77729, 77735, 77745, 77751, 77761, 77767, 77780, 851982),
            "2026-10-20T00:30:00+00:00", "clone:legacy-conservation", "Curated clone role verification", "clone_check",
        )
        simulation, publication, _ = get_position_correction_use_cases(session)
        plan = await simulation.execute(request, 4)
        await publication.execute(plan)
        await session.execute(text("SELECT set_config('sfa.position_publication','off',true)"))
        original = {}
        for table in ("player_events", "player_stats", "player_event_scores"):
            original[table] = list((await session.execute(text(
                f"SELECT to_jsonb(t) FROM {table} t WHERE player_id=35 AND fixture_id=77729 ORDER BY id"
            ))).scalars())
        repo = IngestionRepository(session)
        await repo.delete_player_events_for_fixture(35, 77729)
        await repo.upsert_player_event(35, 77729, 1, 90, EventType.STATS, None, None, None, 1, 1, 1, 1, 1, 0)
        await repo.upsert_player_stats(35, 77729, 1, "2026", {"minutes": 1, "goals": 99})
        await session.execute(text("UPDATE player_event_scores SET final_points=1,fixture_id=77802 "
                                   "WHERE player_id=35 AND fixture_id=77729 AND rules_version_id=4"))
        await session.execute(text("DELETE FROM sfa_season_scores WHERE player_id=35 AND season='2026' "
                                   "AND competition_id=1 AND rules_version_id=4"))
        for table, before in original.items():
            after = list((await session.execute(text(
                f"SELECT to_jsonb(t) FROM {table} t WHERE player_id=35 AND fixture_id=77729 ORDER BY id"
            ))).scalars())
            assert after == before, table
        assert await session.scalar(text("SELECT count(*) FROM sfa_season_scores WHERE player_id=35 "
                                         "AND season='2026' AND competition_id=1 AND rules_version_id=4")) == 1
        # Inputs that underpin the published replay cannot drift silently.
        before_elo = await session.scalar(text("SELECT pre_match_strength FROM fixture_team_strengths "
                                               "WHERE fixture_id=77729 AND team_id=1"))
        await session.execute(text("UPDATE fixture_team_strengths SET pre_match_strength=99 "
                                   "WHERE fixture_id=77729 AND team_id=1"))
        assert await session.scalar(text("SELECT pre_match_strength FROM fixture_team_strengths "
                                         "WHERE fixture_id=77729 AND team_id=1")) == before_elo
        before_birth = await session.scalar(text("SELECT birth_date FROM players WHERE id=35"))
        await session.execute(text("UPDATE players SET birth_date='1990-01-01' WHERE id=35"))
        assert await session.scalar(text("SELECT birth_date FROM players WHERE id=35")) == before_birth
        # An unapproved aggregate cannot overwrite the scored sum.
        await session.execute(text("UPDATE sfa_season_scores SET total_pts=1 WHERE player_id=35 "
                                   "AND season='2026' AND competition_id=1 AND rules_version_id=4"))
        expected = await session.scalar(text("SELECT sum(final_points) FROM player_event_scores WHERE player_id=35 "
                                             "AND season='2026' AND competition_id=1 AND rules_version_id=4"))
        assert await session.scalar(text("SELECT total_pts FROM sfa_season_scores WHERE player_id=35 "
                                         "AND season='2026' AND competition_id=1 AND rules_version_id=4")) == expected
        # A later noncurated appearance is accepted and the season can increase.
        next_fixture = await session.scalar(text("SELECT id FROM fixtures f WHERE season='2026' AND competition_id=1 "
            "AND 1 IN(home_team_id,away_team_id) AND NOT EXISTS(SELECT 1 FROM player_events e WHERE e.player_id=35 "
            "AND e.fixture_id=f.id) ORDER BY played_at LIMIT 1"))
        assert next_fixture
        event_id = await session.scalar(text("INSERT INTO player_events(player_id,fixture_id,team_id,minute,event_type,"
            "m1,m2,m3,m4,mvisit,pts) VALUES(35,:fixture,1,90,'STATS',1,1,1,1,1,0) RETURNING id"),
                                         {"fixture": next_fixture})
        await session.execute(text("INSERT INTO player_event_scores(event_id,player_id,fixture_id,season,competition_id,"
            "rules_version_id,action_type,position,base_points,m1,m2,m3,m4,mvisit,mrating,combined_before_clamp,"
            "combined_after_clamp,final_points,created_at) VALUES(:event,35,:fixture,'2026',1,4,'stats','DEL',777,1,1,1,"
            "1,1,1,1,1,777,now())"), {"event": event_id, "fixture": next_fixture})
        await session.execute(text("UPDATE sfa_season_scores SET total_pts=1 WHERE player_id=35 "
                                   "AND season='2026' AND competition_id=1 AND rules_version_id=4"))
        assert await session.scalar(text("SELECT total_pts FROM sfa_season_scores WHERE player_id=35 "
                                         "AND season='2026' AND competition_id=1 AND rules_version_id=4")) == expected + 777
        assert await session.scalar(text("SELECT count(*) FROM player_position_evidence WHERE player_id=35 "
                                         "AND assertion_kind='dependency_update_candidate'")) > 0
        print(json.dumps({"checks": ["legacy_delete_insert_preserved_without_duplicates", "raw_stats_preserved",
                          "moved_score_identity_blocked", "rollup_delete_blocked", "elo_and_birthdate_preserved",
                          "unreconciled_rollup_corrected", "new_appearance_increases_total", "pending_updates_audited"],
                          "committed": False}))
        await session.rollback()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
