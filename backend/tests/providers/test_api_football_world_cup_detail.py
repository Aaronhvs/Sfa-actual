from __future__ import annotations

import pytest

from sfa.infrastructure.providers.api_football import APIFootballProvider


def fixture_payload() -> dict:
    return {
        "response": [
            {
                "fixture": {
                    "id": 1489371,
                    "date": "2026-06-13T22:00:00+00:00",
                    "referee": "Example Referee",
                    "venue": {"name": "MetLife Stadium", "city": "New Jersey"},
                    "status": {
                        "short": "FT",
                        "long": "Match Finished",
                        "elapsed": 90,
                    },
                },
                "league": {"round": "Group Stage - 1"},
                "teams": {
                    "home": {"id": 6, "name": "Brazil"},
                    "away": {"id": 31, "name": "Morocco"},
                },
                "goals": {"home": 2, "away": 1},
            }
        ]
    }


@pytest.mark.anyio
async def test_fixture_detail_parses_venue_lineups_and_statistics() -> None:
    provider = APIFootballProvider("test", "https://example.test")

    async def fake_get(endpoint: str, params: dict | None = None) -> dict:
        if endpoint == "fixtures":
            return fixture_payload()
        if endpoint == "fixtures/lineups":
            return {
                "response": [
                    {
                        "team": {"id": 6, "name": "Brazil"},
                        "formation": "4-3-3",
                        "coach": {"name": "Coach Brazil", "photo": "coach.png"},
                        "startXI": [
                            {
                                "player": {
                                    "id": 1,
                                    "name": "Player One",
                                    "number": 10,
                                    "pos": "M",
                                    "grid": "2:2",
                                }
                            }
                        ],
                        "substitutes": [],
                    }
                ]
            }
        return {
            "response": [
                {
                    "team": {"id": 6},
                    "statistics": [
                        {"type": "Ball Possession", "value": "58%"},
                        {"type": "Total Shots", "value": 12},
                    ],
                },
                {
                    "team": {"id": 31},
                    "statistics": [
                        {"type": "Ball Possession", "value": "42%"},
                        {"type": "Total Shots", "value": 8},
                    ],
                },
            ]
        }

    provider._get = fake_get  # type: ignore[method-assign]

    detail = await provider.fetch_world_cup_fixture_detail(1489371)

    assert detail is not None
    assert detail.venue.name == "MetLife Stadium"
    assert detail.lineups[0].formation == "4-3-3"
    assert detail.lineups[0].start_xi[0].number == 10
    assert detail.statistics[0].home_numeric == 58
    assert detail.statistics[0].away_value == "42%"


@pytest.mark.anyio
async def test_fixture_detail_accepts_missing_optional_sections() -> None:
    provider = APIFootballProvider("test", "https://example.test")

    async def fake_get(endpoint: str, params: dict | None = None) -> dict:
        if endpoint == "fixtures":
            payload = fixture_payload()
            payload["response"][0]["fixture"]["venue"] = None
            payload["response"][0]["fixture"]["referee"] = None
            return payload
        return {"response": []}

    provider._get = fake_get  # type: ignore[method-assign]

    detail = await provider.fetch_world_cup_fixture_detail(1489371)

    assert detail is not None
    assert detail.venue.name is None
    assert detail.referee is None
    assert detail.lineups == []
    assert detail.statistics == []


def test_world_cup_knockout_rounds_map_to_scoring_stages() -> None:
    provider = APIFootballProvider("test", "https://example.test")

    assert provider.get_stage("Round of 32 - 1", "World Cup") == "round_of_32"
    assert provider.get_stage("Round of 16 - 2", "World Cup") == "round_of_16"
    assert provider.get_stage("Quarter-finals", "World Cup") == "quarter"
    assert provider.get_stage("Semi-finals", "World Cup") == "semi"
    assert provider.get_stage("3rd Place Final", "World Cup") == "third_place"
    assert provider.get_stage("Final", "World Cup") == "final"
