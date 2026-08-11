from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
from sfa.domain.scoring_ports import (
    FixtureEloRow,
    FixtureTeamStrengthDTO,
    TeamCompetitionRow,
    TeamEloRow,
    TeamEloSeedDTO,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.services.elo_calculator import ELO_DEFAULT, EloCalculatorService


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, seeded=None, fixtures=None) -> None:
        self.seeded = seeded or []
        self.fixtures = fixtures or []
        self.active_competitions: dict[int, list[int]] = {}
        self.upserted_elos: list[dict] = []
        self.replaced_snapshots: list[FixtureTeamStrengthDTO] = []
        self.snapshot_replacements = 0

    async def get_team_strength(self, team_id, season, competition_id):
        return None

    async def upsert_team_strength(self, team_id, season, competition_id, strength, source):
        pass

    async def get_team_standings_for_season(self, competition_id, season) -> list[TeamStandingRow]:
        return []

    async def get_team_strength_with_elo(self, team_id, season, competition_id):
        return None, None

    async def upsert_team_elo(
        self,
        team_id,
        season,
        elo_raw,
        strength_normalized,
        source,
        competition_ids,
        elo_seed_raw=None,
    ) -> None:
        self.upserted_elos.append({
            "team_id": team_id,
            "season": season,
            "elo_raw": elo_raw,
            "strength_normalized": strength_normalized,
            "source": source,
            "competition_ids": competition_ids,
            "elo_seed_raw": elo_seed_raw,
        })

    async def get_all_teams_with_elo(self, season, competition_ids=None) -> list[TeamEloRow]:
        self.requested_competition_ids = competition_ids
        return self.seeded

    async def get_fixtures_for_elo_recalc(self, season, competition_ids) -> list[FixtureEloRow]:
        return sorted(self.fixtures, key=lambda fixture: (fixture.played_at, fixture.fixture_id))

    async def upsert_team_elo_seed(self, seed) -> None:
        pass

    async def get_team_elo_seeds(self, season, participant_kind):
        self.requested_participant_kind = participant_kind
        return [
            TeamEloSeedDTO(
                team_id=row.team_id,
                season=season,
                participant_kind=participant_kind,
                elo_raw=row.elo_seed_raw,
                effective_at=datetime(2025, 8, 1, tzinfo=timezone.utc),
                source="test_seed",
            )
            for row in self.seeded
            if row.elo_seed_raw is not None
        ]

    async def replace_fixture_team_strengths(
        self,
        season,
        participant_kind,
        competition_ids,
        snapshots,
    ) -> None:
        self.snapshot_replacements += 1
        self.replaced_snapshots = list(snapshots)

    async def get_team_name_id_map(self, season, participant_kind=None):
        return {}

    async def get_active_competition_ids_for_team(self, team_id, season):
        return self.active_competitions.get(team_id, [1])

    async def get_competition_ids_for_participant_kind(self, season, participant_kind):
        return [1]

    async def get_competition_id_by_name(self, name):
        return None

    async def get_teams_for_competition_season(self, competition_id, season) -> list[TeamCompetitionRow]:
        return []

    async def get_team_strength_coverage(self, competition_id, season) -> list[TeamStrengthCoverageRow]:
        return []


def _fixture(fixture_id, home, away, home_goals, away_goals, played_at, competition_id=1):
    return FixtureEloRow(
        fixture_id=fixture_id,
        home_team_id=home,
        away_team_id=away,
        played_at=played_at,
        competition_id=competition_id,
        home_goals=home_goals,
        away_goals=away_goals,
        season="2024",
    )


@pytest.mark.anyio
async def test_single_fixture_updates_both_teams():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 2, 0, datetime(2024, 8, 1, tzinfo=timezone.utc))
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    result = await use_case.execute("2024", [1], {}, 30.0)

    assert result.status == "completed"
    assert result.fixtures_processed == 1
    by_team = {row["team_id"]: row for row in repo.upserted_elos}
    assert by_team[10]["elo_raw"] > ELO_DEFAULT
    assert by_team[20]["elo_raw"] < ELO_DEFAULT


@pytest.mark.anyio
async def test_fixtures_processed_in_chronological_order():
    fixtures = [
        _fixture(2, 20, 10, 2, 0, datetime(2024, 8, 8, tzinfo=timezone.utc)),
        _fixture(1, 10, 20, 2, 0, datetime(2024, 8, 1, tzinfo=timezone.utc)),
    ]
    repo = FakeTeamStrengthRepository(fixtures=fixtures)
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    by_team = {row["team_id"]: row["elo_raw"] for row in repo.upserted_elos}
    inverted_home_after_first = EloCalculatorService.update_elo(1500, 1500, 2, 0, True, 30.0)
    inverted_away_after_first = EloCalculatorService.update_elo(1500, 1500, 2, 0, False, 30.0)
    inverted_final_team_10 = EloCalculatorService.update_elo(
        inverted_away_after_first, inverted_home_after_first, 2, 0, False, 30.0
    )
    assert by_team[10] != pytest.approx(inverted_final_team_10)


@pytest.mark.anyio
async def test_fixture_snapshots_store_pre_match_elo_in_chronological_order():
    first = _fixture(1, 10, 20, 2, 0, datetime(2025, 8, 1, tzinfo=timezone.utc))
    second = _fixture(2, 10, 20, 0, 1, datetime(2025, 8, 8, tzinfo=timezone.utc))
    repo = FakeTeamStrengthRepository(
        seeded=[
            TeamEloRow(10, "2025", 1900.0, 71.43, 1900.0),
            TeamEloRow(20, "2025", 1650.0, 35.71, 1650.0),
        ],
        fixtures=[second, first],
    )
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    result = await use_case.execute(
        "2025",
        [1],
        {},
        30.0,
        source="club_elo_v2",
        use_seed_baseline=True,
        require_seed_baseline=True,
    )

    assert result.status == "completed"
    by_fixture_team = {
        (snapshot.fixture_id, snapshot.team_id): snapshot
        for snapshot in repo.replaced_snapshots
    }
    assert by_fixture_team[(1, 10)].pre_match_elo_raw == pytest.approx(1900.0)
    assert by_fixture_team[(1, 20)].pre_match_elo_raw == pytest.approx(1650.0)
    expected_liverpool_after_first = EloCalculatorService.update_elo(
        1900.0, 1650.0, 2, 0, True, 30.0
    )
    assert by_fixture_team[(2, 10)].pre_match_elo_raw == pytest.approx(
        expected_liverpool_after_first
    )
    assert (
        by_fixture_team[(1, 10)].pre_match_strength
        > by_fixture_team[(1, 20)].pre_match_strength
    )


@pytest.mark.anyio
async def test_seed_replay_produces_idempotent_fixture_snapshots():
    repo = FakeTeamStrengthRepository(
        seeded=[
            TeamEloRow(10, "2025", 1920.0, 74.29, 1900.0),
            TeamEloRow(20, "2025", 1630.0, 32.86, 1650.0),
        ],
        fixtures=[
            _fixture(1, 10, 20, 2, 0, datetime(2025, 8, 1, tzinfo=timezone.utc)),
            _fixture(2, 20, 10, 1, 1, datetime(2025, 8, 8, tzinfo=timezone.utc)),
        ],
    )
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute(
        "2025", [1], {}, source="club_elo_v2", use_seed_baseline=True,
        require_seed_baseline=True,
    )
    first_run = list(repo.replaced_snapshots)
    await use_case.execute(
        "2025", [1], {}, source="club_elo_v2", use_seed_baseline=True,
        require_seed_baseline=True,
    )

    assert repo.snapshot_replacements == 2
    assert repo.replaced_snapshots == first_run


@pytest.mark.anyio
async def test_team_without_seed_gets_default_elo():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 0, 0, datetime(2024, 8, 1, tzinfo=timezone.utc))
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    assert {row["elo_raw"] for row in repo.upserted_elos} == {ELO_DEFAULT}


@pytest.mark.anyio
async def test_k_factor_applied_per_competition():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 1, 0, datetime(2024, 8, 1, tzinfo=timezone.utc), competition_id=1),
        _fixture(2, 30, 40, 1, 0, datetime(2024, 8, 1, tzinfo=timezone.utc), competition_id=2),
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1, 2], {1: 10.0, 2: 40.0}, 30.0)

    by_team = {row["team_id"]: row["elo_raw"] for row in repo.upserted_elos}
    assert by_team[30] - ELO_DEFAULT == pytest.approx((by_team[10] - ELO_DEFAULT) * 4)


@pytest.mark.anyio
async def test_elo_written_normalized_and_raw():
    repo = FakeTeamStrengthRepository(seeded=[
        TeamEloRow(team_id=10, season="2024", elo_raw=1950.0, strength=78.57)
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    assert repo.upserted_elos[0]["elo_raw"] == pytest.approx(1950.0)
    assert repo.upserted_elos[0]["strength_normalized"] == pytest.approx(78.57, abs=0.01)
    assert repo.upserted_elos[0]["source"] == "elo_v1"


@pytest.mark.anyio
async def test_seed_baseline_recalculates_from_original_seed():
    repo = FakeTeamStrengthRepository(
        seeded=[
            TeamEloRow(
                team_id=10,
                season="2026",
                elo_raw=2025.0,
                strength=89.29,
                elo_seed_raw=2000.0,
            ),
            TeamEloRow(
                team_id=20,
                season="2026",
                elo_raw=1810.0,
                strength=58.57,
                elo_seed_raw=1800.0,
            ),
        ],
        fixtures=[
            _fixture(1, 10, 20, 0, 1, datetime(2026, 6, 15, tzinfo=timezone.utc))
        ],
    )
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute(
        "2026",
        [350],
        {},
        20.0,
        source="national_elo_v1",
        use_seed_baseline=True,
    )

    by_team = {row["team_id"]: row for row in repo.upserted_elos}
    expected_home = EloCalculatorService.update_elo(2000.0, 1800.0, 0, 1, True, 20.0)
    expected_away = EloCalculatorService.update_elo(1800.0, 2000.0, 0, 1, False, 20.0)
    assert by_team[10]["elo_raw"] == pytest.approx(expected_home)
    assert by_team[20]["elo_raw"] == pytest.approx(expected_away)
    assert {row["source"] for row in repo.upserted_elos} == {"national_elo_v1"}
    assert repo.requested_participant_kind == "national_team"


@pytest.mark.anyio
async def test_strict_seed_baseline_fails_when_fixture_team_has_no_seed():
    repo = FakeTeamStrengthRepository(
        seeded=[
            TeamEloRow(
                team_id=10,
                season="2026",
                elo_raw=2000.0,
                strength=85.71,
                elo_seed_raw=2000.0,
            )
        ],
        fixtures=[
            _fixture(1, 10, 20, 1, 0, datetime(2026, 6, 15, tzinfo=timezone.utc))
        ],
    )
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    result = await use_case.execute(
        "2026",
        [350],
        {},
        20.0,
        use_seed_baseline=True,
        require_seed_baseline=True,
    )

    assert result.status == "failed"
    assert result.error == "Missing ELO seed baseline for team_ids: 20"
    assert repo.upserted_elos == []
    assert repo.snapshot_replacements == 0


@pytest.mark.anyio
async def test_non_strict_replay_can_initialize_and_persist_missing_seed_baseline():
    repo = FakeTeamStrengthRepository(
        fixtures=[
            _fixture(1, 10, 20, 1, 0, datetime(2025, 8, 15, tzinfo=timezone.utc))
        ],
    )
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    result = await use_case.execute(
        "2025",
        [1],
        {},
        30.0,
        source="club_elo_v2",
        use_seed_baseline=True,
        require_seed_baseline=False,
        initialize_missing_seed_baseline=True,
    )

    assert result.status == "completed"
    assert {row["elo_seed_raw"] for row in repo.upserted_elos} == {ELO_DEFAULT}
    assert {row["source"] for row in repo.upserted_elos} == {"club_elo_v2"}
