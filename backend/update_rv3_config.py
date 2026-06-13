"""Actualiza el config de rules_version id=3 con los nuevos campos de spec 0015."""
import asyncio, json

async def main():
    from sfa.domain.scoring.value_objects import ScoringConfig
    from sfa.infrastructure.database import AsyncSessionLocal
    from sqlalchemy import text

    config = ScoringConfig.default_v2()
    d = config.to_dict()

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("UPDATE scoring_rules_versions SET config_json=:cfg WHERE id=3"),
            {"cfg": json.dumps(d)}
        )
        await session.commit()
        print(f"Updated id=3: m1_stats_weight={d['m1_stats_weight']}, m1_stats_clamp={d['m1_stats_clamp']}")

asyncio.run(main())
