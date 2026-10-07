from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_team_ranking import (
    GetTeamRankingUseCase,
    GetTeamRankingUseCaseProtocol,
    _percentiles,
    _prior_season,
)
from sfa.domain.team_ranking_ports import (
    TeamRankingDataDTO,
    TeamRankingEloDTO,
    TeamRankingInputDTO,
    TeamRankingPlayerDTO,
    TeamRankingRepositoryProtocol,
)

CUTOFF = datetime(2026, 9, 30, tzinfo=timezone.utc)


class FakeTeamRankingRepository(TeamRankingRepositoryProtocol):
    def __init__(self, data=TeamRankingDataDTO(), latest="2026"):
        self.data = data
        self.latest = latest
        self.calls = []

    async def latest_season(self, participant_kind):
        self.calls.append(("latest", participant_kind))
        return self.latest

    async def get_ranking_data(self, season, prior_season, participant_kind, as_of, recent_matches):
        self.calls.append((season, prior_season, participant_kind, as_of, recent_matches))
        return self.data


def team(id, name=None, competition_ids=(3,)):
    return TeamRankingInputDTO(id, name or f"Team {id}", id + 100, 3, "Premier League", competition_ids)


def player(
    team_id, player_id=None, points=100, minutes=900, position="DEL", season="2026", observed=10, scored=10,
):
    return TeamRankingPlayerDTO(
        team_id, player_id or team_id, season, position, observed, scored, minutes, points, CUTOFF,
    )


def data():
    return TeamRankingDataDTO(
        teams=(team(1, "Arsenal", (3, 9)), team(2, "Liverpool"), team(3, "Chelsea")),
        elos=(TeamRankingEloDTO(1, "2026", 1900, "club_elo_v2"),
              TeamRankingEloDTO(2, "2026", 1800, "club_elo_v2")),
        players=(player(1, points=200), player(2, points=100),
                 player(3, points=None, minutes=0, scored=0)), rules_version_id=3,
    )


def test_protocols_and_percentile_ties():
    repo = FakeTeamRankingRepository()
    assert isinstance(repo, TeamRankingRepositoryProtocol)
    assert isinstance(GetTeamRankingUseCase(repo), GetTeamRankingUseCaseProtocol)
    assert _percentiles({}) == {}
    assert _percentiles({1: 99}) == {1: 50}
    assert _percentiles({1: 10, 2: 10}) == {1: 50, 2: 50}
    assert _percentiles({1: 10, 2: 10, 3: 20}) == {1: 25, 2: 25, 3: 100}


@pytest.mark.parametrize(("season", "prior"), [("2026", "2025"), ("2026-27", "2025-26"), ("1999-00", "1998-99")])
def test_prior_season(season, prior):
    assert _prior_season(season) == prior


class TestGetTeamRankingUseCase:
    @pytest.mark.anyio
    async def test_happy_path_formula_metadata_and_unknowns(self):
        result = await GetTeamRankingUseCase(FakeTeamRankingRepository(data())).execute(scope="season-2026")
        first, second, unknown = result.ranking
        assert first.id == 1
        assert first.squad_score == pytest.approx(83.3333)
        assert first.score == pytest.approx(96.6667)
        assert second.score == pytest.approx(3.3333)
        assert first.effective_elo_weight == .8
        assert first.effective_squad_weight == .2
        assert first.coverage == 1
        assert first.squad_data_cutoff == CUTOFF
        assert first.elo_data_cutoff is None
        assert first.availability is None
        assert unknown.score is None
        assert unknown.coverage == 0
        assert unknown.elo_raw is None
        assert result.model.rules_version_id == 3
        assert result.model.experimental and result.model.descriptive_only
        assert not result.model.feeds_m1
        assert result.model.data_cutoff == CUTOFF
        assert result.model.as_of > CUTOFF
        assert "M1/context" in result.model.caveats[0]
        assert result.model.population_teams == 3

    @pytest.mark.anyio
    async def test_empty_and_latest_resolution(self):
        repo = FakeTeamRankingRepository(latest=None)
        result = await GetTeamRankingUseCase(repo).execute()
        assert result.total == 0 and result.ranking == ()
        assert result.season == "" and result.scope is None
        assert result.pagination.total_pages == 0
        assert repo.calls == [("latest", "club")]
        repo = FakeTeamRankingRepository()
        result = await GetTeamRankingUseCase(repo).execute(participant_kind="national")
        assert result.season == "2026"
        assert repo.calls[1][:3] == ("2026", "2025", "national_team")
        assert result.model.participant_kind == "national_team"
        assert repo.calls[1][-1] == 10

    @pytest.mark.anyio
    @pytest.mark.parametrize("kwargs", [
        {"season": "2026", "scope": "season-2026"}, {"scope": "world-cup-2026"},
        {"scope": "season-"}, {"season": "all"}, {"season": "2026-29"},
        {"season": ""}, {"page": 0}, {"limit": 51}, {"limit": 0},
        {"participant_kind": "unknown"}, {"competition_id": 0},
    ])
    async def test_invalid_inputs_do_not_read_ranking(self, kwargs):
        repo = FakeTeamRankingRepository()
        with pytest.raises(ValueError):
            await GetTeamRankingUseCase(repo).execute(**kwargs)
        assert not any(call[0] != "latest" for call in repo.calls)

    @pytest.mark.anyio
    async def test_scores_stable_under_filters_and_pages(self):
        uc = GetTeamRankingUseCase(FakeTeamRankingRepository(data()))
        full = await uc.execute(season="2026")
        filtered = await uc.execute(season="2026", name=" arsenal ", competition_id=9)
        assert filtered.total == 1
        assert filtered.ranking[0].score == full.ranking[0].score
        assert filtered.model.population_teams == 3
        paged = await uc.execute(season="2026", page=2, limit=1)
        assert paged.ranking[0].id == 2 and paged.ranking[0].rank == 2
        assert paged.pagination.has_next and paged.pagination.has_prev
        assert (await uc.execute(season="2026", page=9)).ranking == ()
        assert (await uc.execute(season="2026", name="%_", competition_id=99)).total == 0

    @pytest.mark.anyio
    async def test_prior_fallback_per_component_and_current_precedence(self):
        inputs = TeamRankingDataDTO(
            teams=(team(1), team(2)),
            elos=(TeamRankingEloDTO(1, "2025", 1800, "elo_v1"),
                  TeamRankingEloDTO(2, "2025", 2000, "elo_v1"),
                  TeamRankingEloDTO(2, "2026", 1900, "club_elo_v2")),
            players=(player(1, season="2025"), player(1, points=None, minutes=0, scored=0),
                     player(2), player(2, season="2025", points=9999)),
        )
        result = await GetTeamRankingUseCase(FakeTeamRankingRepository(inputs)).execute(season="2026")
        rows = {r.id: r for r in result.ranking}
        assert rows[1].squad_season == rows[1].elo_season == "2025"
        assert rows[1].elo_source == "elo_v1"
        assert rows[2].squad_season == rows[2].elo_season == "2026"
        assert rows[2].elo_raw == 1900
        assert rows[1].observed_players == 1

    @pytest.mark.anyio
    async def test_components_renormalize_and_missing_is_not_zero(self):
        inputs = TeamRankingDataDTO(
            teams=(team(2), team(1), replace(team(3), external_id=None), team(4)),
            elos=(TeamRankingEloDTO(1, "2026", 1800, "elo_v1"),),
            players=(player(2, points=0), player(3, points=0)),
        )
        result = await GetTeamRankingUseCase(FakeTeamRankingRepository(inputs)).execute(season="2026")
        assert [r.id for r in result.ranking] == [1, 2, 3, 4]
        rows = {r.id: r for r in result.ranking}
        assert rows[1].effective_elo_weight == 1 and rows[1].squad_score is None
        assert rows[2].effective_squad_weight == 1 and rows[2].elo_score is None
        assert rows[2].score == 50  # actual zero points is observed, not missing
        assert rows[3].team_logo_url is None
        assert rows[4].coverage is None and rows[4].squad_season is None

    @pytest.mark.anyio
    async def test_position_normalization_and_small_sample_shrinkage(self):
        inputs = TeamRankingDataDTO(
            teams=(team(1), team(2), team(3), team(4)),
            players=(player(1, points=100, minutes=90), player(2, points=0, minutes=90),
                     player(3, points=1, minutes=900, position="GK"),
                     player(4, points=0, minutes=900, position="GK")),
        )
        result = await GetTeamRankingUseCase(FakeTeamRankingRepository(inputs)).execute(season="2026")
        scores = {r.id: r.squad_score for r in result.ranking}
        assert scores[1] == pytest.approx(58.3333)
        assert scores[3] == pytest.approx(83.3333)

    @pytest.mark.anyio
    async def test_transferred_player_is_unique_in_cohort_and_attributed_to_both_teams(self):
        inputs = TeamRankingDataDTO(
            teams=(team(1), team(2), team(3)),
            players=(player(1, player_id=10, points=100), player(2, player_id=10, points=100),
                     player(3, player_id=20, points=0)),
        )
        result = await GetTeamRankingUseCase(FakeTeamRankingRepository(inputs)).execute(season="2026")
        rows = {r.id: r for r in result.ranking}
        assert rows[1].squad_score == rows[2].squad_score == pytest.approx(83.3333)
        assert rows[1].scored_players == rows[2].scored_players == 1

    @pytest.mark.anyio
    async def test_coverage_counts_appearances_not_players(self):
        inputs = TeamRankingDataDTO(
            teams=(team(1),), players=(player(1, observed=10, scored=2, minutes=180),
                                      player(1, player_id=2, points=None, minutes=0, observed=5, scored=0)),
        )
        item = (await GetTeamRankingUseCase(FakeTeamRankingRepository(inputs)).execute(season="2026")).ranking[0]
        assert item.coverage == pytest.approx(2 / 15)
        assert item.observed_players == 2 and item.scored_players == 1
        assert item.squad_score == 50
