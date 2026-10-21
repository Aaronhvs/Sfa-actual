"""Real PostgreSQL publication/reversal tests. Refuses a production database."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from sqlalchemy import text

from sfa.core.dependencies import get_position_correction_use_cases
from sfa.domain.player_positions.publication import PositionCorrectionRequest
from sfa.infrastructure.database import AsyncSessionLocal, engine


def request():
    return PositionCorrectionRequest(
        player_id=35, external_player_id=1496, team_id=1, external_team_id=529, season="2026", position="DEL",
        fixture_ids=(77729, 77735, 77745, 77751, 77761, 77767, 77780, 851982),
        accepted_at="2026-10-20T00:30:00+00:00", source_ref="user:raphinha-central-role:2026-10-19",
        statement="User confirms current central-forward role; eight retained CF starts support curated historical scope.",
        actor="user_authorized_curated_pilot",
    )


async def fingerprints(session, excluded=None):
    result = {}
    for table in ("players", "player_events", "player_event_scores", "sfa_season_scores", "scoring_rules_versions",
                  "player_achievement_bonuses", "individual_honors", "ranking_player_explanations"):
        ids = (excluded or {}).get(table, [])
        where = " WHERE id NOT IN (" + ",".join(str(int(i)) for i in ids) + ")" if ids else ""
        row = (await session.execute(text(
            f"SELECT count(*),md5(coalesce(string_agg(md5(row_to_json(t)::text),'' ORDER BY id),'')) FROM {table} t{where}"
        ))).one()
        result[table] = {"rows": row[0], "md5": row[1]}
    return result


async def exclusive():
    session = AsyncSessionLocal(info={"position_publication_exclusive": True})
    database = await session.scalar(text("SELECT current_database()"))
    if not database.startswith("sfa_positions_validation_"):
        await session.close()
        raise RuntimeError("Refusing mutations outside restored validation clone")
    return session


async def main():
    session = await exclusive()
    try:
        simulation, publication, reversal = get_position_correction_use_cases(session)
        plan = await simulation.execute(request(), 4)
        excluded = {"player_event_scores": [r["before"]["id"] for r in json.loads(plan.event_changes_json)],
                    "sfa_season_scores": [r["before"]["id"] for r in json.loads(plan.rollup_changes_json)],
                    "ranking_player_explanations": [r["id"] for r in json.loads(plan.dependencies_json)["source"]["explanations"]]}
        before = await fingerprints(session, excluded)
        # Mid-batch failure must roll back every score, assignment, aggregate and journal.
        session.info["position_publication_failpoint"] = "after_first_score"
        try:
            await publication.execute(plan)
        except RuntimeError as error:
            assert "failpoint" in str(error)
        else:
            raise AssertionError("Failpoint did not fire")
        await session.rollback()
        session.info.pop("position_publication_failpoint")
        assert await fingerprints(session, excluded) == before
        assert not await session.scalar(text("SELECT count(*) FROM position_correction_batches"))
        # Reproduce CAS failure after fresh preview but before applying it.
        await session.execute(text("UPDATE players SET photo_url=coalesce(photo_url,'')||'?clone-cas=1' WHERE id=35"))
        try:
            await publication.execute(plan)
        except ValueError as error:
            assert "changed after approval" in str(error)
        else:
            raise AssertionError("Stale manifest accepted")
        await session.rollback()
        published = await publication.execute(plan)
        assert await publication.execute(plan) == published
        await session.commit()
        position = await session.scalar(text("SELECT sfa_current_position(35,NULL,'2026',now())"))
        assert position == "DEL", position
        historical = (await session.execute(text("""
            SELECT f.id,sfa_accepted_position(35,1,f.competition_id,f.season,f.played_at,f.id)
            FROM fixtures f WHERE f.id IN (77729,77802,40103,42280) ORDER BY f.id
        """))).all()
        assert dict(historical) == {77729: "DEL", 77802: None, 40103: None, 42280: None}
        after = await fingerprints(session, excluded)
        assert after == before
        # Refuse to compensate over a later writer.
        row_id = json.loads(plan.event_changes_json)[0]["before"]["id"]
        await session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
        await session.execute(text("UPDATE player_event_scores SET final_points=final_points+1 WHERE id=:id"),
                              {"id": row_id})
        try:
            await reversal.execute(plan.batch_id, "clone_check")
        except ValueError as error:
            assert "changed afterwards" in str(error)
        else:
            raise AssertionError("Reversal overwrote later mutation")
        await session.rollback()
        reverted = await reversal.execute(plan.batch_id, "clone_validation")
        await session.commit()
        assert await fingerprints(session, excluded) == before
        # JSONB numeric formatting may normalize 1.000 to 1.0; verify complete
        # restored records by PostgreSQL JSONB value equality, not printed scale.
        for table, changes in (("player_event_scores", json.loads(plan.event_changes_json)),
                                ("sfa_season_scores", json.loads(plan.rollup_changes_json))):
            for change in changes:
                assert await session.scalar(text(f"SELECT to_jsonb(t)=CAST(:before AS jsonb) FROM {table} t WHERE id=:id"),
                                             {"before": json.dumps(change["before"]), "id": change["before"]["id"]})
        assert (await reversal.execute(plan.batch_id, "clone_validation")).status == "reverted"
        print(json.dumps({"plan": asdict(plan), "batch_id": plan.batch_id, "publication": asdict(published),
                          "reversion": asdict(reverted), "historical": dict(historical),
                          "restored_fingerprints": before, "checks": ["baseline_parity", "failpoint_atomicity",
                          "input_cas", "publication_idempotence", "scoped_resolution", "reversion_cas",
                          "full_reversion", "excluded_records_unchanged"]}, default=str))
    finally:
        await session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
