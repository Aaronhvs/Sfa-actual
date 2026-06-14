from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixtureDTO,
    WorldCupLineupPlayerDTO,
    WorldCupTeamDTO,
    WorldCupTeamLineupDTO,
    WorldCupVenueDTO,
)
from sfa.infrastructure.providers.api_football import APIFootballProvider
from sfa.infrastructure.repositories.world_cup_repository import WorldCupRepository


class FakeMappings:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def all(self) -> list[dict]:
        return self._rows


class FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)


class FakeSession:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    async def execute(self, statement: object) -> FakeResult:
        return FakeResult(self._rows)


class FakeRedis:
    async def get(self, key: str) -> None:
        return None

    async def setex(self, key: str, ttl: int, value: str) -> None:
        return None


def make_detail() -> WorldCupFixtureDetailDTO:
    home = WorldCupTeamDTO(external_id=6, name="Brazil")
    away = WorldCupTeamDTO(external_id=31, name="Morocco")
    return WorldCupFixtureDetailDTO(
        fixture=WorldCupFixtureDTO(
            external_id=1489371,
            stage="Group Stage - 1",
            matchday=1,
            played_at=datetime(2026, 6, 13, 22, tzinfo=timezone.utc),
            status="FT",
            status_label="Match Finished",
            elapsed=90,
            home_team=home,
            away_team=away,
            home_goals=2,
            away_goals=1,
        ),
        venue=WorldCupVenueDTO(name="MetLife Stadium", city="New Jersey"),
        referee=None,
        lineups=[
            WorldCupTeamLineupDTO(
                team=home,
                formation="4-3-3",
                coach_name=None,
                coach_photo=None,
                start_xi=[
                    WorldCupLineupPlayerDTO(
                        external_id=100,
                        name="Scored Player",
                        number=10,
                        position="M",
                        grid="3:2",
                    ),
                    WorldCupLineupPlayerDTO(
                        external_id=101,
                        name="Pending Player",
                        number=8,
                        position="M",
                        grid="3:1",
                    ),
                ],
                substitutes=[],
            )
        ],
        statistics=[],
    )


@pytest.mark.anyio
async def test_attach_sfa_scores_enriches_only_processed_players() -> None:
    repository = WorldCupRepository(
        provider=APIFootballProvider("test", "https://example.test"),
        redis=FakeRedis(),  # type: ignore[arg-type]
        session=FakeSession(  # type: ignore[arg-type]
            [{"external_id": 100, "player_id": 77, "sfa_points": 1234.56}]
        ),
    )

    result = await repository._attach_sfa_scores(make_detail())
    scored, pending = result.lineups[0].start_xi

    assert scored.player_id == 77
    assert scored.sfa_points == 1234.56
    assert pending.player_id is None
    assert pending.sfa_points is None
