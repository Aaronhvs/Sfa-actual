"""Create the B1 age-exceptionality scoring rules version.

By default this script is idempotent and non-disruptive: it creates or updates
the B1 version from the current active config, but it does not activate it.

Usage:
    python scripts/create_b1_scoring_rules_version.py --dry-run
    python scripts/create_b1_scoring_rules_version.py
    python scripts/create_b1_scoring_rules_version.py --activate
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import sys

from sqlalchemy import select, update

sys.path.insert(0, "src")

from sfa.domain.scoring.value_objects import ScoringConfig  # noqa: E402
from sfa.infrastructure.database import AsyncSessionLocal  # noqa: E402
from sfa.infrastructure.models.scoring_rules.models import (  # noqa: E402
    ScoringRulesVersion,
)

B1_NAME = "v2.2-b1-age-exceptionality"
B1_VERSION = "2.2"
B1_DESCRIPTION = (
    "Adds B1 age exceptionality bonus for goals and assists by young or veteran players."
)


def _b1_config_from_active(active_config: dict) -> dict:
    config = ScoringConfig.from_dict(active_config)
    data = config.to_dict()
    data.update({
        "b1_enabled": True,
        "b1_young_min_age": 17,
        "b1_young_max_age": 20,
        "b1_veteran_min_age": 35,
        "b1_bonus_table": {"1": 200, "2": 400, "3": 600},
        "b1_competition_ids": [350],
    })
    ScoringConfig.from_dict(data)
    return data


async def run(dry_run: bool, activate: bool) -> None:
    async with AsyncSessionLocal() as session:
        active = (
            await session.execute(
                select(ScoringRulesVersion).where(ScoringRulesVersion.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if active is None:
            raise RuntimeError("No active scoring rules version found")

        b1_config = _b1_config_from_active(active.config_json)

        existing = (
            await session.execute(
                select(ScoringRulesVersion).where(ScoringRulesVersion.name == B1_NAME)
            )
        ).scalar_one_or_none()

        print(
            f"Active source: id={active.id} name={active.name} "
            f"version={active.version} is_active={active.is_active}"
        )
        print(f"B1 target: name={B1_NAME} version={B1_VERSION} activate={activate}")

        if dry_run:
            action = "update" if existing else "insert"
            print(f"[DRY RUN] Would {action} B1 scoring rules version.")
            if activate:
                print("[DRY RUN] Would deactivate all versions and activate B1.")
            return

        if existing:
            existing.version = B1_VERSION
            existing.description = B1_DESCRIPTION
            existing.config_json = b1_config
            b1_row = existing
        else:
            b1_row = ScoringRulesVersion(
                name=B1_NAME,
                version=B1_VERSION,
                description=B1_DESCRIPTION,
                is_active=False,
                config_json=b1_config,
                created_at=datetime.now(UTC),
            )
            session.add(b1_row)

        await session.flush()

        if activate:
            await session.execute(update(ScoringRulesVersion).values(is_active=False))
            b1_row.is_active = True

        await session.commit()
        print(
            f"B1 ready: id={b1_row.id} name={b1_row.name} "
            f"version={b1_row.version} is_active={b1_row.is_active}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, activate=args.activate))
