from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
)
from sfa.domain.scoring.entities import PlayerEventScore, ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import (
    PlayerEventRawContextDTO,
    PlayerEventScoreRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)


# ─── Fakes ───────────────────────────────────────────────────────────────────


class FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self, version: ScoringRulesVersion | None = None):
        self._version = version

    async def get_active_version(self) -> ScoringRulesVersion | None:
        return self._version

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None:
        if self._version and self._version.id == version_id:
            return self._version
        return None

    async def list_versions(self) -> list[ScoringRulesVersion]:
        return [self._version] if self._version else []

    async def save_version(self, name, version, description, config) -> int:
        return 1

    async def set_active_version(self, version_id: int) -> None:
        pass


class FakePlayerEventScoreRepository(PlayerEventScoreRepositoryPort):
    def __init__(self, events: list[PlayerEventRawContextDTO] | None = None):
        self._events = events or []
        self.upserted: list[PlayerEventScore] = []
        self._existing: set[tuple[int, int]] = set()
        self.bulk_rebuild_calls: list[dict] = []

    async def get_events_for_recalc(self, season, competition_id, match_id, player_id):
        return self._events

    async def upsert_event_score(self, score: PlayerEventScore) -> None:
        self.upserted.append(score)

    async def event_score_exists(self, event_id: int, rules_version_id: int) -> bool:
        return (event_id, rules_version_id) in self._existing

    def mark_existing(self, event_id: int, rules_version_id: int) -> None:
        self._existing.add((event_id, rules_version_id))

    async def delete_event_scores_for_version(self, rules_version_id, season, competition_id):
        pass

    async def get_player_event_totals_for_season(
        self, player_id, season, competition_id, rules_version_id
    ) -> tuple[float, int]:
        pts = sum(s.final_points for s in self.upserted if s.player_id == player_id)
        matches = len({s.fixture_id for s in self.upserted if s.player_id == player_id})
        return float(pts), int(matches)

    async def get_players_with_events_in_scope(self, season, competition_id, rules_version_id):
        return list({s.player_id for s in self.upserted})

    async def get_season_score_breakdown(
        self, player_id, season, competition_id, rules_version_id
    ) -> dict:
        breakdown: dict = {}
        for s in self.upserted:
            if s.player_id != player_id:
                continue
            key = s.action_type
            if key not in breakdown:
                breakdown[key] = {"count": 0, "pts": 0.0}
            breakdown[key]["count"] += 1
            breakdown[key]["pts"] = round(breakdown[key]["pts"] + s.final_points, 2)
        return breakdown

    async def get_competition_name_map(self) -> dict[int, str]:
        return {}

    async def bulk_rebuild_season_scores(
        self,
        rules_version_id: int,
        season: str,
        competition_id: int | None = None,
    ) -> int:
        player_competition_pairs = {
            (score.player_id, score.competition_id) for score in self.upserted
        }
        self.bulk_rebuild_calls.append({
            "rules_version_id": rules_version_id,
            "season": season,
            "competition_id": competition_id,
        })
        return len(player_competition_pairs)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_rules_version(version_id: int = 1, config: ScoringConfig | None = None) -> ScoringRulesVersion:
    return ScoringRulesVersion(
        id=version_id,
        name="v1.0-test",
        version="1.0.0",
        description="Test",
        is_active=True,
        config=config or ScoringConfig.default(),
        created_at=datetime.now(timezone.utc),
    )


def _make_goal_event(
    event_id: int = 1,
    player_id: int = 10,
    fixture_id: int = 100,
    competition_id: int = 1,
    event_type: str = "goal",
    player_birth_date: date | None = None,
    fixture_date: date | None = None,
) -> PlayerEventRawContextDTO:
    return PlayerEventRawContextDTO(
        event_id=event_id,
        player_id=player_id,
        fixture_id=fixture_id,
        competition_id=competition_id,
        season="2024",
        event_type=event_type,
        minute=75,
        score_diff=0,
        psxg=0.32 if event_type in {"goal", "goal_penalty", "goal_shootout"} else None,
        player_team_pos=10,
        rival_team_pos=5,
        is_away=False,
        stage_factor=1.0,
        goals=1, assists=0, shots_on=2, passes_key=1,
        passes_total=30, passes_accuracy=80.0,
        dribbles_won=1, duels_won=2, tackles_won=0,
        interceptions=0, blocks=0, fouls_drawn=1,
        fouls_committed=0, cards_yellow=0, cards_red=0,
        penalty_won=0, dribbles_past=0,
        rating=7.5,
        player_position="MC",
        minutes=90,
        player_team_strength=None,
        rival_team_strength=None,
        player_birth_date=player_birth_date,
        fixture_date=fixture_date,
    )


def _make_stats_event(
    event_id: int = 2,
    player_id: int = 20,
    fixture_id: int = 200,
    competition_id: int = 1,
) -> PlayerEventRawContextDTO:
    return PlayerEventRawContextDTO(
        event_id=event_id,
        player_id=player_id,
        fixture_id=fixture_id,
        competition_id=competition_id,
        season="2024",
        event_type="stats",
        minute=90,
        score_diff=None,
        psxg=None,
        player_team_pos=8,
        rival_team_pos=12,
        is_away=True,
        stage_factor=1.0,
        goals=0, assists=0, shots_on=0, passes_key=2,
        passes_total=50, passes_accuracy=85.0,
        dribbles_won=3, duels_won=5, tackles_won=2,
        interceptions=1, blocks=0, fouls_drawn=2,
        fouls_committed=1, cards_yellow=0, cards_red=0,
        penalty_won=0, dribbles_past=0,
        rating=8.2,
        player_position="MC",
        minutes=90,
        player_team_strength=None,
        rival_team_strength=None,
    )


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestCalculateScoresForRulesVersionUseCase:
    @pytest.mark.anyio
    async def test_goal_event_recalculated_with_config(self):
        version = _make_rules_version()
        event = _make_goal_event()
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024")

        assert result.status == "completed"
        assert result.events_calculated == 1
        assert len(events_repo.upserted) == 1
        score = events_repo.upserted[0]
        assert score.action_type == "goal"
        assert score.final_points > 0
        assert score.rules_version_id == 1

    @pytest.mark.anyio
    async def test_decisive_shootout_goal_uses_direct_impact_model(self):
        version = _make_rules_version(config=ScoringConfig.default_v2())
        event = replace(
            _make_goal_event(event_type="goal_shootout_decisive"),
            stage_factor=1.15,
            player_team_strength=50.0,
            rival_team_strength=95.0,
            player_position="MC",
        )
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024")

        assert result.status == "completed"
        score = events_repo.upserted[0]
        assert score.action_type == "goal_shootout_decisive"
        assert score.base_points == 300
        assert score.m1 == 1.45
        assert score.m2 == 1.15
        assert score.m3 == 1.0
        assert score.final_points == 500.25

    @pytest.mark.anyio
    async def test_decisive_shootout_miss_can_subtract_points(self):
        version = _make_rules_version(config=ScoringConfig.default_v2())
        event = replace(
            _make_goal_event(event_type="missed_shootout_decisive"),
            stage_factor=1.15,
            player_team_strength=50.0,
            rival_team_strength=95.0,
            player_position="MC",
        )
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024")

        assert result.status == "completed"
        score = events_repo.upserted[0]
        assert score.action_type == "missed_shootout_decisive"
        assert score.base_points == -220
        assert score.m1 == 1.45
        assert score.m2 == 1.15
        assert score.m3 == 1.0
        assert score.final_points == -366.85

    @pytest.mark.anyio
    async def test_stats_event_recalculated_with_config(self):
        version = _make_rules_version()
        event = _make_stats_event()
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024")

        assert result.status == "completed"
        assert result.events_calculated == 1
        score = events_repo.upserted[0]
        assert score.action_type == "stats"
        assert score.final_points > 0

    @pytest.mark.anyio
    async def test_skip_existing_when_force_false(self):
        version = _make_rules_version()
        event = _make_goal_event(event_id=5)
        events_repo = FakePlayerEventScoreRepository(events=[event])
        events_repo.mark_existing(event_id=5, rules_version_id=1)
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024", force_recalculate=False)

        assert result.events_calculated == 0
        assert len(events_repo.upserted) == 0

    @pytest.mark.anyio
    async def test_overwrite_existing_when_force_true(self):
        version = _make_rules_version()
        event = _make_goal_event(event_id=5)
        events_repo = FakePlayerEventScoreRepository(events=[event])
        events_repo.mark_existing(event_id=5, rules_version_id=1)
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        result = await use_case.execute(rules_version_id=1, season="2024", force_recalculate=True)

        assert result.events_calculated == 1
        assert len(events_repo.upserted) == 1

    @pytest.mark.anyio
    async def test_nonexistent_rules_version_returns_failed(self):
        events_repo = FakePlayerEventScoreRepository()
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version=None), events_repo,
        )

        result = await use_case.execute(rules_version_id=999, season="2024")

        assert result.status == "failed"
        assert result.events_calculated == 0

    @pytest.mark.anyio
    async def test_season_scores_rebuilt_after_recalculation(self):
        version = _make_rules_version()
        event = _make_goal_event(player_id=10, competition_id=1)
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version), events_repo,
        )

        await use_case.execute(rules_version_id=1, season="2024")

        assert events_repo.bulk_rebuild_calls == [{
            "rules_version_id": 1,
            "season": "2024",
            "competition_id": None,
        }]

    @pytest.mark.anyio
    async def test_calculation_details_contains_all_intermediates(self):
        version = _make_rules_version()
        event = _make_goal_event()
        events_repo = FakePlayerEventScoreRepository(events=[event])
        use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(version),
            events_repo,
        )

        await use_case.execute(rules_version_id=1, season="2024")

        details = events_repo.upserted[0].calculation_details
        for key in ("action", "position", "base", "M1", "M2", "M3", "M4",
                    "Mvisit", "combined_before_clamp", "combined_after_clamp", "final_points"):
            assert key in details, f"Missing key '{key}' in calculation_details"

    @pytest.mark.anyio
    async def test_changed_base_points_affect_final_score(self):
        import copy

        default_config = ScoringConfig.default()
        modified_bp = {g: dict(v) for g, v in default_config.base_points.items()}
        from sfa.domain.scoring.value_objects import ActionType, PositionGroup
        modified_bp[PositionGroup.MF][ActionType.GOAL] = 1400  # double the default 700 (MC→MF)

        modified_config = ScoringConfig(
            base_points=modified_bp,
            m1_clamp=default_config.m1_clamp,
            m1_divisor=default_config.m1_divisor,
            m4_psxg_multiplier=default_config.m4_psxg_multiplier,
            m4_clamp=default_config.m4_clamp,
            mvisit_bonus=default_config.mvisit_bonus,
            mvisit_eligible_actions=default_config.mvisit_eligible_actions,
            mrating_thresholds=default_config.mrating_thresholds,
            mrating_top_value=default_config.mrating_top_value,
            mrating_none_value=default_config.mrating_none_value,
            combined_clamp=default_config.combined_clamp,
        )

        event = _make_goal_event()

        # Score with default config
        default_repo = FakePlayerEventScoreRepository(events=[event])
        default_use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(_make_rules_version(1, default_config)),
            default_repo,
        )
        await default_use_case.execute(rules_version_id=1, season="2024")

        # Score with modified config (GOAL = 1000 instead of 500)
        modified_repo = FakePlayerEventScoreRepository(events=[event])
        modified_use_case = CalculateScoresForRulesVersionUseCase(
            FakeScoringRulesVersionRepository(_make_rules_version(2, modified_config)),
            modified_repo,
        )
        await modified_use_case.execute(rules_version_id=2, season="2024")

        default_pts = default_repo.upserted[0].final_points
        modified_pts = modified_repo.upserted[0].final_points

        assert abs(modified_pts - default_pts * 2) < 0.1, (
            f"Expected modified_pts ≈ {default_pts * 2}, got {modified_pts}"
        )


@pytest.mark.anyio
async def test_b1_bonus_is_added_and_split_across_goal_assist_contributions():
    match_date = date(2024, 6, 24)
    birth_date = date(1987, 6, 24)
    events = [
        _make_goal_event(
            event_id=101,
            player_id=10,
            fixture_id=100,
            competition_id=350,
            event_type="goal",
            player_birth_date=birth_date,
            fixture_date=match_date,
        ),
        _make_goal_event(
            event_id=102,
            player_id=10,
            fixture_id=100,
            competition_id=350,
            event_type="assist",
            player_birth_date=birth_date,
            fixture_date=match_date,
        ),
        _make_goal_event(
            event_id=103,
            player_id=10,
            fixture_id=100,
            competition_id=350,
            event_type="corner_assist",
            player_birth_date=birth_date,
            fixture_date=match_date,
        ),
    ]

    disabled_config = replace(ScoringConfig.default(), b1_enabled=False)
    disabled_repo = FakePlayerEventScoreRepository(events=events)
    disabled_use_case = CalculateScoresForRulesVersionUseCase(
        FakeScoringRulesVersionRepository(_make_rules_version(1, disabled_config)),
        disabled_repo,
    )
    await disabled_use_case.execute(rules_version_id=1, season="2024")

    enabled_config = replace(ScoringConfig.default(), b1_enabled=True)
    enabled_repo = FakePlayerEventScoreRepository(events=events)
    enabled_use_case = CalculateScoresForRulesVersionUseCase(
        FakeScoringRulesVersionRepository(_make_rules_version(2, enabled_config)),
        enabled_repo,
    )
    await enabled_use_case.execute(rules_version_id=2, season="2024")

    disabled_total = sum(score.final_points for score in disabled_repo.upserted)
    enabled_total = sum(score.final_points for score in enabled_repo.upserted)

    assert round(enabled_total - disabled_total, 2) == 600.0
    assert [
        score.calculation_details["b1_bonus"]["b1_per_event"]
        for score in enabled_repo.upserted
    ] == [200.0, 200.0, 200.0]
    assert enabled_repo.upserted[0].calculation_details["b1_bonus"]["total_contributions"] == 3


@pytest.mark.anyio
async def test_b1_bonus_is_ignored_outside_world_cup_beta_competition():
    match_date = date(2024, 6, 24)
    birth_date = date(1987, 6, 24)
    events = [
        _make_goal_event(
            event_id=201,
            player_id=10,
            fixture_id=200,
            competition_id=39,
            event_type="goal",
            player_birth_date=birth_date,
            fixture_date=match_date,
        ),
    ]

    disabled_config = replace(ScoringConfig.default(), b1_enabled=False)
    disabled_repo = FakePlayerEventScoreRepository(events=events)
    disabled_use_case = CalculateScoresForRulesVersionUseCase(
        FakeScoringRulesVersionRepository(_make_rules_version(1, disabled_config)),
        disabled_repo,
    )
    await disabled_use_case.execute(rules_version_id=1, season="2024")

    enabled_config = replace(ScoringConfig.default(), b1_enabled=True)
    enabled_repo = FakePlayerEventScoreRepository(events=events)
    enabled_use_case = CalculateScoresForRulesVersionUseCase(
        FakeScoringRulesVersionRepository(_make_rules_version(2, enabled_config)),
        enabled_repo,
    )
    await enabled_use_case.execute(rules_version_id=2, season="2024")

    assert enabled_repo.upserted[0].final_points == disabled_repo.upserted[0].final_points
    assert enabled_repo.upserted[0].calculation_details["b1_bonus"] == {
        "enabled": True,
        "applied": False,
        "competition_allowed": False,
    }
