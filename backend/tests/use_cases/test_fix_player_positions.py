import pytest

from sfa.application.use_cases.fix_player_positions import FixPlayerPositionsUseCase, classify_player_from_stats


@pytest.mark.parametrize("values", [(2.5, .1, 0, 10), (0, 1.4, 0, 8), (0, .7, .12, 12)])
def test_statistics_never_determine_a_position(values):
    assert classify_player_from_stats(*values) is None


class ForbiddenSession:
    async def execute(self, *args, **kwargs):
        pytest.fail("Retired repair must never access SQL")

    async def flush(self):
        pytest.fail("Retired repair must never flush")


@pytest.mark.anyio
async def test_legacy_callable_fails_closed_without_database_access():
    with pytest.raises(RuntimeError, match="retired"):
        await FixPlayerPositionsUseCase(ForbiddenSession()).execute()
