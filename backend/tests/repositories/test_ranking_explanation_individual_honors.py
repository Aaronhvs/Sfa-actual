from __future__ import annotations

from decimal import Decimal

import pytest

from sfa.domain.ranking_explanation_ports import RankingExplanationRequestDTO
from sfa.domain.season_scope import AwardPeriodScope, ScopeKind, ScoreSource
from sfa.infrastructure.repositories.ranking_explanation_repository import (
    RankingExplanationRepository,
)


class FakeMappingsResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappingsResult:
        return self

    def all(self) -> list[dict]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeMappingsResult(self.rows)


def _request(*, use_total: bool = True) -> RankingExplanationRequestDTO:
    return RankingExplanationRequestDTO(
        season="2025",
        competition_id=10,
        rules_version_id=4,
        scope="award_period",
        use_total=use_total,
        scope_key="season-2025",
    )


def _scope() -> AwardPeriodScope:
    return AwardPeriodScope(
        key="season-2025",
        label="2025/2026",
        kind=ScopeKind.AWARD_PERIOD,
        sources=(ScoreSource("2025", (10,)),),
    )


@pytest.mark.anyio
async def test_individual_honors_are_exposed_as_explanation_evidence() -> None:
    session = FakeSession([
        {
            "honor_type": "top_scorer",
            "context_label": "Champions League",
            "metric_value": Decimal("13"),
            "metric_total": None,
            "metric_rate": None,
            "bonus_pts": 2200,
        }
    ])
    repository = RankingExplanationRepository(session)

    result = await repository._individual_honors(42, _request(), _scope())

    assert result == [
        {
            "honor_type": "top_scorer",
            "label": "Bota de oro",
            "context_label": "Champions League",
            "metric_value": 13.0,
            "metric_total": None,
            "metric_rate": None,
            "bonus_pts": 2200,
        }
    ]
    sql = str(session.statements[0])
    assert "individual_honors.competition_id" in sql
    assert "individual_honors.scope_key" in sql


@pytest.mark.anyio
async def test_individual_honors_are_omitted_when_total_points_are_disabled() -> None:
    session = FakeSession([])
    repository = RankingExplanationRepository(session)

    assert await repository._individual_honors(
        42, _request(use_total=False), _scope()
    ) == []
    assert session.statements == []
