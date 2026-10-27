"""Offline preparation and isolated rehearsal. Does not fetch from external providers."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import text

from sfa.core.dependencies import (
    get_season_event_integrity_recalculation_use_cases,
    get_season_event_integrity_use_cases,
)
from sfa.domain.event_integrity import (
    Action,
    ActionRevision,
    Appearance,
    AppearanceRevision,
    IntegrityPlan,
    StoredAction,
)
from sfa.infrastructure.database import AsyncSessionLocal
from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository
from sfa.infrastructure.repositories.season_repository import SeasonRepository


def decode_plan(row: dict) -> IntegrityPlan:
    changes = tuple(
        ActionRevision(
            StoredAction(**c["before"]) if c["before"] else None, Action(**c["after"]) if c["after"] else None
        )
        for c in row["changes"]
    )
    appearance_changes = tuple(
        AppearanceRevision(Appearance(**c["before"]), Appearance(**c["after"]))
        for c in row.get("appearance_changes", [])
    )
    return IntegrityPlan(
        **{
            **row,
            "changes": changes,
            "pending": tuple(row["pending"]),
            "appearance_changes": appearance_changes,
            "warnings": tuple(row.get("warnings", [])),
            "fixture_goals": tuple(row["fixture_goals"]) if row.get("fixture_goals") is not None else None,
        }
    )


async def run(args) -> None:
    folder = Path(args.directory)
    report_path = folder / args.plan_file
    async with AsyncSessionLocal() as session:
        database = await session.scalar(text("SELECT current_database()"))
        if args.command != "prepare" and not database.endswith("_test"):
            raise ValueError("This CLI rehearses in an isolated *_test database only")
        scope = await SeasonRepository(session).resolve_scope("season-2025")
        if not scope:
            raise ValueError("Missing season-2025 scope")
        active = await ScoringRulesVersionRepository(session).get_active_version()
        if not active:
            raise ValueError("Missing active rules version")
        await session.rollback()
        if args.command == "prepare":
            plans = []
            fixtures = json.loads((folder / "manifest.json").read_text())["fixtures"]
            if args.fixture_id:
                fixtures = [f for f in fixtures if f["external_id"] in args.fixture_id]
            prepare, _ = get_season_event_integrity_use_cases(session, folder / "journal")
            for fixture in fixtures:
                source = folder / f"{fixture['external_id']}-events.json"
                if not source.exists():
                    continue
                async with session.begin():
                    stats_file = folder / f"{fixture['external_id']}-players.json"
                    stats_source = json.loads(stats_file.read_text())["payload"] if stats_file.exists() else None
                    fixture_file = folder / f"{fixture['external_id']}-fixture.json"
                    fixture_source = json.loads(fixture_file.read_text())["payload"] if fixture_file.exists() else None
                    plan = await prepare.execute(
                        fixture["fixture_id"], json.loads(source.read_text())["payload"], stats_source, fixture_source
                    )
                    plans.append(asdict(plan))
                if len(plans) % 200 == 0:
                    print(json.dumps({"prepared": len(plans)}), flush=True)
            result = {
                "scope": asdict(scope),
                "rules_version_id": active.id,
                "plans": plans,
                "pending": dict(Counter(reason for plan in plans for reason in plan["pending"])),
                "warnings": dict(Counter(reason.split(":")[0] for plan in plans for reason in plan["warnings"])),
            }
            temporary = report_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result), encoding="utf-8")
            temporary.replace(report_path)
            print(
                json.dumps(
                    {
                        "fixtures": len(fixtures),
                        "prepared": len(plans),
                        "changed": sum(
                            bool(p["changes"] or p["appearance_changes"] or p["fixture_goals"]) for p in plans
                        ),
                        "pending": result["pending"],
                        "warnings": result["warnings"],
                    }
                ),
                flush=True,
            )
            return
        if args.command == "apply":
            report = json.loads(report_path.read_text())
            applied = 0
            _, apply = get_season_event_integrity_use_cases(session, folder / "journal")
            for row in report["plans"]:
                plan = decode_plan(row)
                if plan.pending or (not plan.changes and not plan.appearance_changes and plan.fixture_goals is None):
                    continue
                async with session.begin():
                    applied += await apply.execute(plan)
                if applied % 100 == 0:
                    print(json.dumps({"applied_changes": applied}), flush=True)
            print(json.dumps({"applied_changes": applied}), flush=True)
            return
        if args.command == "normalize-context":
            _, apply = get_season_event_integrity_use_cases(session, folder / "journal")
            async with session.begin():
                count = await apply.normalize_contexts()
            print(json.dumps({"normalized_contexts": count}), flush=True)
            return
        if args.command == "recalculate":
            # One transaction publishes a complete projection in the isolated clone.
            session.info["position_publication_exclusive"] = True
            async with session.begin():
                locked = await session.scalar(text("SELECT pg_try_advisory_xact_lock(736615320261019)"))
                if not locked:
                    raise ValueError("Isolated recalculation publication lock is busy")
                await session.execute(text("SELECT set_config('sfa.position_publication','on',true)"))
                calculate, bonuses, honors = get_season_event_integrity_recalculation_use_cases(session)
                for source in scope.sources:
                    for competition_id in source.competition_ids:
                        if args.competition_id and competition_id not in args.competition_id:
                            continue
                        parameters = {
                            "season": source.season,
                            "competition_id": competition_id,
                            "rules_version_id": active.id,
                        }
                        # Clear first: an upsert cannot remove formerly eligible or reassigned actors.
                        for table in ["player_event_scores", "sfa_season_scores", "player_achievement_bonuses"]:
                            await session.execute(
                                text(
                                    f"DELETE FROM {table} WHERE season=:season AND competition_id=:competition_id "
                                    "AND rules_version_id=:rules_version_id"
                                ),
                                parameters,
                            )
                        result = await calculate.execute(**parameters, force_recalculate=True)
                        if result.status != "completed":
                            raise ValueError(result.error)
                        bonus = await bonuses.execute(**parameters)
                        if bonus.status != "completed":
                            raise ValueError(bonus.error)
                        print(
                            json.dumps(
                                {
                                    "season": source.season,
                                    "competition": competition_id,
                                    "scores": result.events_calculated,
                                    "bonuses": bonus.bonuses_created,
                                }
                            ),
                            flush=True,
                        )
                await honors.execute(scope.key, active.id)
                await session.execute(text("SELECT set_config('sfa.position_publication','off',true)"))
            return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "apply", "normalize-context", "recalculate"])
    parser.add_argument("--directory", required=True)
    parser.add_argument("--plan-file", default="plans.json")
    parser.add_argument("--fixture-id", action="append", type=int)
    parser.add_argument("--competition-id", action="append", type=int)
    asyncio.run(run(parser.parse_args()))
