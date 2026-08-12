from __future__ import annotations

import pytest

from sfa.infrastructure.providers.api_football import APIFootballProvider


class FixtureScoreProvider(APIFootballProvider):
    def __init__(self, response: dict) -> None:
        super().__init__("key", "https://example.test")
        self.response = response
        self.calls: list[tuple[str, dict | None]] = []

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        self.calls.append((endpoint, params))
        return self.response


@pytest.mark.anyio
async def test_fetch_fixture_scores_batches_ids_and_keeps_shootout_separate() -> None:
    provider = FixtureScoreProvider({
        "response": [{
            "fixture": {"id": 1001, "status": {"short": "PEN"}},
            "teams": {"home": {"id": 10}, "away": {"id": 20}},
            "goals": {"home": 1, "away": 1},
            "score": {
                "fulltime": {"home": 1, "away": 1},
                "extratime": {"home": 1, "away": 1},
                "penalty": {"home": 5, "away": 4},
            },
        }]
    })

    rows = await provider.fetch_fixture_scores([1001, 1002])

    assert provider.calls == [("fixtures", {"ids": "1001-1002"})]
    assert len(rows) == 1
    assert rows[0].home_goals == 1
    assert rows[0].away_goals == 1
    assert rows[0].extratime_home_goals == 1
    assert rows[0].extratime_away_goals == 1
    assert rows[0].shootout_home_goals == 5
    assert rows[0].shootout_away_goals == 4


@pytest.mark.anyio
async def test_fetch_fixture_scores_rejects_more_than_twenty_ids() -> None:
    provider = FixtureScoreProvider({"response": []})

    with pytest.raises(ValueError, match="at most 20"):
        await provider.fetch_fixture_scores(list(range(21)))
