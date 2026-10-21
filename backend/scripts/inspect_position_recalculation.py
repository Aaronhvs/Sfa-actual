"""Read-only replay report. No scoring writer is invoked."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, replace
from decimal import Decimal

from sqlalchemy import text

from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
    _build_b1_contributions_map,
)
from sfa.domain.scoring.services import SFAScoringService
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.repositories.player_event_score_repository import PlayerEventScoreRepository
from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository


async def main():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        rules_repo = ScoringRulesVersionRepository(session)
        repo = PlayerEventScoreRepository(session)
        rules = await rules_repo.get_active_version()
        events = await repo.get_events_for_recalc("2026", None, None, 35)
        stored = (await session.execute(text(
            "SELECT * FROM player_event_scores WHERE player_id=:player AND season=:season "
            "AND rules_version_id=:version ORDER BY fixture_id,event_id"
        ), {"player": 35, "season": "2026", "version": rules.id})).mappings().all()
        rows = {r["event_id"]: dict(r) for r in stored}
        names = await repo.get_competition_name_map()
        engine_ = CalculateScoresForRulesVersionUseCase(rules_repo, repo)
        service = SFAScoringService(rules.config)
        contributions = _build_b1_contributions_map(events)
        eligible = {77729, 77735, 77745, 77751, 851982, 77761, 77767, 77780}
        comparisons = []
        fields = ("base_points", "m1", "m2", "m3", "m4", "mvisit", "mrating",
                  "combined_before_clamp", "combined_after_clamp", "final_points")
        for raw in events:
            old = rows.get(raw.event_id)
            if old is None:
                comparisons.append({"event_id": raw.event_id, "missing_score": True})
                continue
            baseline = engine_._score_event(replace(raw, player_position=old["position"]), service,
                                             rules.id, names, contributions)
            after = engine_._score_event(replace(raw, player_position="DEL"), service,
                                          rules.id, names, contributions) if raw.fixture_id in eligible else baseline
            mismatches = {k: {"stored": str(old[k]), "replay": str(getattr(baseline, k))}
                          for k in fields if Decimal(str(old[k])) != Decimal(str(getattr(baseline, k)))}
            comparisons.append({"raw": asdict(raw), "stored": old, "baseline": asdict(baseline),
                                "after": asdict(after), "eligible": raw.fixture_id in eligible,
                                "mismatches": mismatches})
        output = {"rules": asdict(rules), "comparisons": comparisons,
                  "source_count": len(events), "score_count": len(rows),
                  "mismatched_count": sum(bool(c.get("mismatches") or c.get("missing_score")) for c in comparisons)}
        print(json.dumps(output, default=lambda v: sorted(v) if isinstance(v, (set, frozenset)) else str(v)))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
