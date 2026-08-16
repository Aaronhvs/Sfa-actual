from datetime import datetime, timezone

from sfa.tasks.ingest_today_task import (
    ACTIVE_COMPETITIONS,
    _collect_relevant_fixtures,
)


def _fixture(fixture_id: int, league_id: int, season: int, status: str) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": datetime.now(timezone.utc).isoformat(),
            "status": {"short": status},
        },
        "league": {"id": league_id, "season": season},
    }


def test_current_club_competitions_replace_world_cup():
    assert (531, 2026) in ACTIVE_COMPETITIONS
    assert (528, 2026) in ACTIVE_COMPETITIONS
    assert (39, 2026) in ACTIVE_COMPETITIONS
    assert (2, 2026) in ACTIVE_COMPETITIONS
    assert (1, 2026) not in ACTIVE_COMPETITIONS


def test_collects_only_live_or_recent_current_season_fixture_ids():
    selected = _collect_relevant_fixtures(
        [
            _fixture(10, 39, 2026, "1H"),
            _fixture(11, 39, 2026, "NS"),
            _fixture(12, 1, 2026, "FT"),
            _fixture(13, 39, 2025, "FT"),
        ],
        {1, 39},
    )

    assert selected == {(39, 2026): {10}}
