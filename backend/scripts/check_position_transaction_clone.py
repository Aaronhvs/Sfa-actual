"""Exercise real session exclusion including the stale scorer interleaving."""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.position_transaction import POSITION_PUBLICATION_LOCK, PositionPublicationBusyError


async def main():
    async with AsyncSessionLocal() as check:
        assert (await check.scalar(text("SELECT current_database()"))).startswith("sfa_positions_validation_")
    writer = AsyncSessionLocal()
    publisher = AsyncSessionLocal(info={"position_publication_exclusive": True})
    try:
        # A scorer owns shared exclusion before reading. Publication fails fast;
        # it must never queue and block a shared child of this outer session.
        await writer.scalar(text("SELECT position FROM players WHERE id=35"))
        try:
            await publisher.scalar(text("SELECT 1"))
        except PositionPublicationBusyError:
            pass
        else:
            raise AssertionError("Publisher passed an active scorer's initial read lock")
        assert publisher.info.get("position_lock_mode") is None
        await publisher.rollback()
        async with AsyncSessionLocal() as child:
            assert await asyncio.wait_for(child.scalar(text("SELECT 1")), 5) == 1
        await writer.execute(text("UPDATE players SET position=position WHERE id=35"))
        await writer.commit()
        await publisher.close()
        publisher = AsyncSessionLocal(info={"position_publication_exclusive": True})
        assert await publisher.scalar(text("SELECT 1")) == 1
        task = asyncio.create_task(writer.scalar(text("SELECT position FROM players WHERE id=35")))
        try:
            await asyncio.wait_for(asyncio.shield(task), 0.25)
        except asyncio.TimeoutError:
            pass
        else:
            raise AssertionError("New scorer read while publication exclusive was held")
        await publisher.rollback()
        await asyncio.wait_for(task, 5)
        await writer.rollback()
        await writer.scalar(text("SELECT 1"))
        writer.info["position_publication_exclusive"] = True
        try:
            await writer.scalar(text("SELECT 1"))
        except RuntimeError as error:
            assert "Cannot change" in str(error)
        else:
            raise AssertionError("Shared transaction upgraded after reading")
        writer.info.pop("position_publication_exclusive")
        await writer.rollback()
        # Savepoint rollback must preserve root exclusion.
        nested = await writer.begin_nested()
        await writer.scalar(text("SELECT 1"))
        await nested.rollback()
        async with engine.connect() as connection:
            available = await connection.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"),
                                                  {"key": POSITION_PUBLICATION_LOCK})
            assert available is False
        await writer.rollback()
        # Initial SET TRANSACTION must be executed before any query; readonly RR
        # is permitted, while snapshot writers are conservatively refused.
        await writer.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        assert await writer.scalar(text("SELECT 1")) == 1
        await writer.rollback()
        await writer.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        try:
            await writer.scalar(text("SELECT 1"))
        except RuntimeError as error:
            assert "READ COMMITTED" in str(error)
        else:
            raise AssertionError("Snapshot writer bypassed stale-snapshot protection")
        await writer.rollback()
        print(json.dumps({"checks": ["scorer_read_excludes_publisher", "publisher_excludes_new_scorer",
                                      "savepoint_rollback_preserves_root_lock", "initial_readonly_rr",
                                      "snapshot_writer_rejected", "new_transaction_reacquires", "upgrade_rejected",
                                      "busy_does_not_queue_or_block_shared_child", "fresh_session_retry"]}))
    finally:
        await writer.close()
        await publisher.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
