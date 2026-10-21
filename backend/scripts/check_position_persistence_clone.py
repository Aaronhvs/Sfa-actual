"""Executable PostgreSQL integration check. Refuses production database names.

Run with PYTHONPATH=src and POSITION_VALIDATION_SNAPSHOT pointing at the retained
JSON corpus. The caller supplies DATABASE_URL for a restored validation clone.
No provider, Redis or scoring writer is constructed.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import text

from sfa.core.config import get_settings
from sfa.core.dependencies import (
    get_position_collection_state,
    get_record_position_evidence_use_case,
    get_review_position_assignment_use_case,
)
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.repositories.player_position_repository import PlayerPositionRepository


async def fingerprints(session):
    result = {}
    for table in ("players", "player_events", "player_event_scores", "sfa_season_scores", "scoring_rules_versions"):
        row = (await session.execute(text(
            f"SELECT count(*), md5(coalesce(string_agg(md5(row_to_json(t)::text),'' ORDER BY id),'')) FROM {table} t"
        ))).one()
        result[table] = {"rows": row[0], "md5": row[1]}
    return result


async def main():
    snapshot = json.loads(Path(os.environ["POSITION_VALIDATION_SNAPSHOT"]).read_text("utf-8"))
    async with AsyncSessionLocal() as session:
        database = await session.scalar(text("SELECT current_database()"))
        if not database.startswith("sfa_positions_validation_"):
            raise RuntimeError("Refusing integration mutations outside the explicit validation clone")
        before = await fingerprints(session)
    uc = get_record_position_evidence_use_case()
    results = []
    for entry in snapshot["cache"]:
        payload = entry["payload"]
        results.append(asdict(await uc.execute(
            payload["fixture"]["external_id"], json.dumps(payload),
            f"retained-corpus:{entry['key']}", snapshot["captured_at"],
        )))
    replay = []
    for entry in snapshot["cache"]:
        payload = entry["payload"]
        replay.append(asdict(await uc.execute(
            payload["fixture"]["external_id"], json.dumps(payload),
            f"retained-corpus:{entry['key']}", snapshot["captured_at"],
        )))
    assert all(r["snapshots"] == r["evidence"] == 0 for r in replay), replay
    redis = Redis.from_url(get_settings().REDIS_URL)
    lease_key = f"position-validation:{uuid.uuid4().hex}:lease"
    first_state = get_position_collection_state(redis, lease_key=lease_key)
    second_state = get_position_collection_state(redis, lease_key=lease_key)
    try:
        assert await first_state.acquire()
        assert not await second_state.acquire()
        assert await first_state.owns_lease()
        await first_state.release()
        assert await second_state.acquire()
        await first_state.release()
        assert await second_state.owns_lease(), "Expired owner deleted a new owner's lease"
        await second_state.checkpoint(987654321, "attempt_started", "{}")
        async with AsyncSessionLocal() as session:
            assert await session.scalar(text("SELECT count(*) FROM position_source_coverage "
                                             "WHERE scope_key='lineup-request:987654321'"))
        pending = await second_state.pending("2026", 10)
        assert len(pending) <= 10
        inventory = json.loads(await second_state.inventory(1, "2026"))
        assert inventory and all("both_starting_elevens" in row for row in inventory)
        fixture = snapshot["cache"][0]["payload"]["fixture"]["external_id"]
        async with AsyncSessionLocal() as session:
            repository = PlayerPositionRepository(session)
            context = await repository.get_fixture_context(fixture)
            for key, value in (("both_starting_elevens", False), ("unresolved_player_ids", [999999]),
                               ("conflicting_lineup_versions", True)):
                async with session.begin_nested():
                    proof = {"both_starting_elevens": True, "unresolved_player_ids": [], key: value}
                    await session.execute(text(
                        "INSERT INTO position_source_coverage(scope_key,proof_hash,proof,status) "
                        "VALUES(:scope,:hash,CAST(:proof AS jsonb),'partial')"
                    ), {"scope": f"fixture:{fixture}", "hash": uuid.uuid4().hex,
                        "proof": json.dumps(proof)})
                    rows = json.loads(await repository.coverage_inventory(context.competition_id, context.season))
                    assert not next(row for row in rows if row["external_id"] == fixture)["both_starting_elevens"]
                await session.rollback()
            async with session.begin():
                proof = {"both_starting_elevens": True, "unresolved_player_ids": [999999],
                         "unresolved_starting_player_ids": [], "unresolved_starting_identity": False}
                await session.execute(text(
                    "INSERT INTO position_source_coverage(scope_key,proof_hash,proof,status) "
                    "VALUES(:scope,:hash,CAST(:proof AS jsonb),'partial')"
                ), {"scope": f"fixture:{fixture}", "hash": uuid.uuid4().hex,
                    "proof": json.dumps(proof)})
                rows = json.loads(await repository.coverage_inventory(context.competition_id, context.season))
                assert next(row for row in rows if row["external_id"] == fixture)["both_starting_elevens"]
                await session.rollback()
    finally:
        await second_state.release()
        await first_state.release()
        await redis.aclose()
    async with AsyncSessionLocal() as session:
        durable = {}
        for table in ("fixture_lineup_snapshots", "player_position_evidence", "position_source_coverage"):
            durable[table] = await session.scalar(text(f"SELECT count(*) FROM {table}"))
        assert durable["fixture_lineup_snapshots"] >= 26
        # A failure after a flush and before commit must not leave a half capture.
        count_before = durable["position_source_coverage"]
        try:
            await session.execute(text("INSERT INTO position_source_coverage(scope_key,proof_hash,proof,status) "
                                       "VALUES('integration-failpoint',repeat('f',64),'{}','partial')"))
            await session.flush()
            raise RuntimeError("intentional-failpoint")
        except RuntimeError:
            await session.rollback()
        assert await session.scalar(text("SELECT count(*) FROM position_source_coverage")) == count_before
        await session.rollback()
        # Confirmed habitual MCO decisions preserve the current baseline row,
        # even when enrichment/manual/repair tries to replace its mapped input.
        for player_id, external_id in ((52, 340626), (517, 1323)):
            async with session.begin():
                row = (await session.execute(text(
                    "SELECT external_id,position::text,position_source FROM players WHERE id=:id"
                ), {"id": player_id})).one()
                assert row[0] == external_id
                reference_uc = get_review_position_assignment_use_case(session)
                accepted_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
                reference = dict(player_id=player_id, external_id=external_id, position="MCO",
                                 source_ref="integration:current-reference", statement="Validation-only MCO reference",
                                 accepted_at=accepted_at, actor="integration-test")
                result = await reference_uc.execute(**reference)
                assert result["inserted"] and not result["published"]
                repeated = await reference_uc.execute(**reference)
                assert not repeated["inserted"] and repeated["revision_id"] == result["revision_id"]
                for source, position in (("apifootball", "MC"), ("transfermarkt", "EXT"), ("manual", "DC")):
                    await session.execute(text("UPDATE players SET position=:position,position_source=:source "
                                               "WHERE id=:id"),
                                          {"id": player_id, "source": source, "position": position})
                    protected = (await session.execute(text(
                        "SELECT position::text,position_source FROM players WHERE id=:id"
                    ), {"id": player_id})).one()
                    assert tuple(protected) == tuple(row[1:])
                assert await session.scalar(text(
                    "SELECT count(*) FROM player_position_evidence WHERE player_id=:id "
                    "AND assertion_kind='incoming_mapped_candidate'"
                ), {"id": player_id}) >= 3
                # Explicit rollback: this test does not seed sporting decisions.
                await session.rollback()
        after = await fingerprints(session)
        assert before == after, "Acquisition changed published inputs, points or rules"
    report = {"database": database, "before": before, "after": after, "durable": durable,
              "imports": results, "replay": replay, "replay_provider_calls": 0,
              "atomic_rollback": "passed", "accepted_position_guard": "passed",
              "redis_lease_owner_cas": "passed", "durable_attempt_checkpoint": "passed"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
