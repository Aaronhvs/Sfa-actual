import pytest

from sfa.application.use_cases.ingest_competition import IngestCompetitionUseCase
from sfa.infrastructure.models.enums import Position

from .test_ingest_stats_event import _LEAGUE, FakeFootballProvider, FakeIngestionRepository, _fixture, _player_stats


@pytest.mark.anyio
async def test_new_unknown_player_remains_pending_instead_of_becoming_midfielder(caplog):
    repo = FakeIngestionRepository()
    result = await IngestCompetitionUseCase(
        FakeFootballProvider([_fixture()], _player_stats(position="")), repo,
    ).execute(_LEAGUE, 2026)
    assert result.status == "completed"
    assert repo._player_ids == {} and repo.player_events == {}
    assert "Pending position" in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("position", [Position.GK, Position.LAT, Position.MCO])
async def test_missing_provider_position_preserves_existing_known_role(position):
    repo = FakeIngestionRepository()
    pid = await repo.upsert_player(42, "Test Player", position)
    await IngestCompetitionUseCase(
        FakeFootballProvider([_fixture()], _player_stats(position="")), repo,
    ).execute(_LEAGUE, 2026)
    assert repo._player_positions[pid] == position
    assert repo.player_stats
    assert bool(repo.player_events) == (position != Position.GK)


@pytest.mark.anyio
async def test_manual_goalkeeper_overrides_legacy_midfielder_when_provider_position_is_missing():
    repo = FakeIngestionRepository()
    pid = await repo.upsert_player(42, "Test Player", Position.MC)
    repo.manual_positions[pid] = Position.GK
    await IngestCompetitionUseCase(
        FakeFootballProvider([_fixture()], _player_stats(position="")), repo,
    ).execute(_LEAGUE, 2026)
    assert repo.player_stats and not repo.player_events


@pytest.mark.anyio
async def test_legacy_midfielder_is_not_scored_from_missing_provider_position(caplog):
    repo = FakeIngestionRepository()
    await repo.upsert_player(42, "Test Player", Position.MC)
    await IngestCompetitionUseCase(
        FakeFootballProvider([_fixture()], _player_stats(position="")), repo,
    ).execute(_LEAGUE, 2026)
    assert repo.player_stats and not repo.player_events
    assert "scoring pending position" in caplog.text
