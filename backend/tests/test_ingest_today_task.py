from datetime import datetime, timezone

from sfa.tasks.ingest_today_task import (
    ACTIVE_COMPETITIONS,
    _collect_relevant_fixtures,
    _dates_to_check,
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


def test_checks_yesterday_only_near_utc_midnight():
    assert _dates_to_check(
        datetime(2026, 8, 17, 2, tzinfo=timezone.utc),
    ) == ["2026-08-16", "2026-08-17"]
    assert _dates_to_check(
        datetime(2026, 8, 17, 12, tzinfo=timezone.utc),
    ) == ["2026-08-17"]
