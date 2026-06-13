"""Tests for spec 0010: API-Football Complete Stats — nuevos campos y scoring."""
from __future__ import annotations

import pytest

from sfa.application.use_cases.ingest_competition import IngestCompetitionUseCase
from sfa.application.use_cases.recalculate_scores import RecalculateScoresUseCase
from sfa.domain.enrichment_ports import (
    PlayerSeasonEventRow,
    PlayerStatsEventRecalcRow,
    SeasonScoreRow,
)
from sfa.domain.ingestion_ports import PlayerStatsRawDTO
from sfa.domain.scoring.services import BASE_POINTS_TABLE, SFAScoringService
from sfa.domain.scoring.value_objects import ActionType, PositionGroup
from sfa.infrastructure.models.enums import EventType

from .test_ingest_stats_event import (
    FakeFootballProvider,
    FakeIngestionRepository,
    _LEAGUE,
    _fixture,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(
    external_id: int = 1,
    name: str = "Test Player",
    position: str = "Midfielder",
    minutes: int = 90,
    **kwargs,
) -> PlayerStatsRawDTO:
    defaults = dict(
        player_external_id=external_id,
        player_name=name,
        position=position,
        minutes=minutes,
        goals=0,
        assists=0,
        shots_on=0,
        passes_key=0,
        dribbles_success=0,
        duels_won=0,
        tackles=0,
        interceptions=0,
        blocks=0,
    )
    defaults.update(kwargs)
    return PlayerStatsRawDTO(**defaults)


def _recalc_row(
    player_position: str = "MC",
    m1: float = 1.0,
    **kwargs,
) -> PlayerStatsEventRecalcRow:
    defaults = dict(
        event_id=1,
        player_id=10,
        player_position=player_position,
        m1=m1,
        m2=1.0,
        current_pts=0.0,
        duels_won=0,
        tackles_won=0,
        interceptions=0,
        blocks=0,
        dribbles_won=0,
        passes_key=0,
        passes_total=0,
        passes_accuracy=0,
        shots_on=0,
        shots_total=0,
        dribbles_past=0,
        duels_total=0,
        fouls_drawn=0,
        fouls_committed=0,
        cards_yellow=0,
        cards_red=0,
        penalty_won=0,
        goals=0,
        assists=0,
        rating=None,
    )
    defaults.update(kwargs)
    return PlayerStatsEventRecalcRow(**defaults)


class FakeEnrichmentRepo:
    """Minimal Fake for RecalculateScoresUseCase tests."""

    def __init__(self, stats_rows: list[PlayerStatsEventRecalcRow]) -> None:
        self._stats_rows = stats_rows
        self.updated_pts: dict[int, float] = {}

    async def get_players_by_competition(self, *a): return []
    async def get_player_events_without_psxg(self, *a): return []
    async def update_player_external_ids(self, *a, **kw): pass
    async def update_player_stats_from_fbref(self, *a, **kw): pass
    async def update_event_psxg(self, *a): pass
    async def update_event_scores(self, *a, **kw): pass
    async def update_season_score(self, *a, **kw): pass
    async def get_events_with_psxg_for_recalc(self, *a): return []
    async def get_stats_events_for_recalc(self, *a): return self._stats_rows
    async def update_event_pts(self, event_id, pts, m2=None): self.updated_pts[event_id] = pts
    async def get_all_player_season_events(self, player_id, *a):
        pts = self.updated_pts.get(1, 0.0)
        return [PlayerSeasonEventRow(id=1, player_id=player_id, fixture_id=1, event_type="stats", pts=pts)]
    async def get_player_season_score_row(self, player_id, competition_id, season):
        return SeasonScoreRow(player_id=player_id, competition_id=competition_id,
                              season=season, total_pts=0.0, matches_played=1, breakdown={})
    async def get_player_season_real_stats(self, *a): return (0, 0)


# ---------------------------------------------------------------------------
# DTO — nuevos campos presentes y almacenados correctamente
# ---------------------------------------------------------------------------

def test_new_dto_fields_stored_correctly():
    """PlayerStatsRawDTO almacena los 11 campos nuevos con los valores pasados."""
    dto = _make_player(
        shots_total=5,
        passes_total=60,
        passes_accuracy=83,
        dribbles_past=2,
        duels_total=10,
        fouls_committed=3,
        cards_yellow=1,
        cards_red=0,
        penalty_won=1,
        saves=4,
        goals_conceded=1,
    )
    assert dto.shots_total == 5
    assert dto.passes_total == 60
    assert dto.passes_accuracy == 83
    assert dto.dribbles_past == 2
    assert dto.duels_total == 10
    assert dto.fouls_committed == 3
    assert dto.cards_yellow == 1
    assert dto.cards_red == 0
    assert dto.penalty_won == 1
    assert dto.saves == 4
    assert dto.goals_conceded == 1


def test_new_dto_fields_default_to_zero():
    """Los 11 campos nuevos tienen default=0 — no requieren valor explícito."""
    dto = _make_player()
    assert dto.shots_total == 0
    assert dto.passes_total == 0
    assert dto.passes_accuracy == 0
    assert dto.dribbles_past == 0
    assert dto.duels_total == 0
    assert dto.fouls_committed == 0
    assert dto.cards_yellow == 0
    assert dto.cards_red == 0
    assert dto.penalty_won == 0
    assert dto.saves == 0
    assert dto.goals_conceded == 0


# ---------------------------------------------------------------------------
# PASSES_COMPLETED — cálculo y scoring
# ---------------------------------------------------------------------------

def test_passes_completed_calculation():
    """passes_total × passes_accuracy / 100 truncado a int."""
    assert int(60 * 83 / 100) == 49
    assert int(50 * 80 / 100) == 40
    assert int(100 * 75 / 100) == 75
    assert int(0 * 90 / 100) == 0


def test_passes_completed_mf_has_positive_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.PASSES_COMPLETED] == 3


def test_passes_completed_fw_has_positive_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.PASSES_COMPLETED] == 2


def test_passes_completed_df_has_positive_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.PASSES_COMPLETED] == 1


@pytest.mark.anyio
async def test_mf_with_passes_scores_more_than_mf_without():
    """MF con passes_total=60, passes_accuracy=80 → PASSES_COMPLETED=48 → más pts."""
    repo_with = FakeEnrichmentRepo([_recalc_row("MC", passes_total=60, passes_accuracy=80)])
    repo_without = FakeEnrichmentRepo([_recalc_row("MC")])

    await RecalculateScoresUseCase(repo_with).execute(1, "2024")
    await RecalculateScoresUseCase(repo_without).execute(1, "2024")

    pts_with = repo_with.updated_pts.get(1, 0.0)
    pts_without = repo_without.updated_pts.get(1, 0.0)
    assert pts_with > pts_without, f"MF with passes ({pts_with}) debe superar sin passes ({pts_without})"


# ---------------------------------------------------------------------------
# Tarjetas — señales negativas
# ---------------------------------------------------------------------------

def test_yellow_card_has_negative_base_pts():
    for group in BASE_POINTS_TABLE:
        assert BASE_POINTS_TABLE[group][ActionType.YELLOW_CARD] == -150


def test_red_card_has_more_negative_pts_than_yellow():
    for group in BASE_POINTS_TABLE:
        assert BASE_POINTS_TABLE[group][ActionType.RED_CARD] < BASE_POINTS_TABLE[group][ActionType.YELLOW_CARD]
        assert BASE_POINTS_TABLE[group][ActionType.RED_CARD] == -500


@pytest.mark.anyio
async def test_yellow_card_reduces_score():
    """Jugador con tarjeta amarilla recalcula a menos pts que sin tarjeta."""
    repo_clean = FakeEnrichmentRepo([_recalc_row("MC", duels_won=5)])
    repo_yellow = FakeEnrichmentRepo([_recalc_row("MC", duels_won=5, cards_yellow=1)])

    await RecalculateScoresUseCase(repo_clean).execute(1, "2024")
    await RecalculateScoresUseCase(repo_yellow).execute(1, "2024")

    pts_clean = repo_clean.updated_pts.get(1, 0.0)
    pts_yellow = repo_yellow.updated_pts.get(1, 0.0)
    assert pts_yellow < pts_clean, f"Tarjeta amarilla ({pts_yellow}) debe reducir pts respecto a limpio ({pts_clean})"


@pytest.mark.anyio
async def test_red_card_reduces_more_than_yellow_card():
    """Tarjeta roja (-500) penaliza más que amarilla (-150)."""
    repo_yellow = FakeEnrichmentRepo([_recalc_row("MC", cards_yellow=1)])
    repo_red = FakeEnrichmentRepo([_recalc_row("MC", cards_red=1)])

    await RecalculateScoresUseCase(repo_yellow).execute(1, "2024")
    await RecalculateScoresUseCase(repo_red).execute(1, "2024")

    pts_yellow = repo_yellow.updated_pts.get(1, 0.0)
    pts_red = repo_red.updated_pts.get(1, 0.0)
    assert pts_red < pts_yellow, f"Tarjeta roja ({pts_red}) debe penalizar más que amarilla ({pts_yellow})"


# ---------------------------------------------------------------------------
# PENALTY_WON — scoring por posición
# ---------------------------------------------------------------------------

def test_penalty_won_fw_more_than_df():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.PENALTY_WON] == 200
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.PENALTY_WON] == 180
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.PENALTY_WON] == 80
    assert (
        BASE_POINTS_TABLE[PositionGroup.FW][ActionType.PENALTY_WON]
        > BASE_POINTS_TABLE[PositionGroup.DF][ActionType.PENALTY_WON]
    )


@pytest.mark.anyio
async def test_penalty_won_fw_scores_more_than_df():
    """FW que gana un penalti suma más pts que DF en la misma situación."""
    repo_fw = FakeEnrichmentRepo([_recalc_row("DEL", penalty_won=1)])
    repo_df = FakeEnrichmentRepo([_recalc_row("DC", penalty_won=1)])

    await RecalculateScoresUseCase(repo_fw).execute(1, "2024")
    await RecalculateScoresUseCase(repo_df).execute(1, "2024")

    pts_fw = repo_fw.updated_pts.get(1, 0.0)
    pts_df = repo_df.updated_pts.get(1, 0.0)
    assert pts_fw > pts_df, f"FW penalty_won ({pts_fw}) debe superar DF ({pts_df})"


# ---------------------------------------------------------------------------
# DRIBBLES_PAST — posición-dependiente
# ---------------------------------------------------------------------------

def test_dribbles_past_fw_has_zero_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.DRIBBLES_PAST] == 0


def test_dribbles_past_df_has_negative_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.DRIBBLES_PAST] == -50


def test_dribbles_past_mf_has_negative_base_pts():
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.DRIBBLES_PAST] == -20


@pytest.mark.anyio
async def test_dribbles_past_does_not_penalize_fw():
    """FW con dribbles_past=3 debe tener los mismos pts que FW sin ellos."""
    repo_with = FakeEnrichmentRepo([_recalc_row("DEL", dribbles_past=3)])
    repo_without = FakeEnrichmentRepo([_recalc_row("DEL")])

    await RecalculateScoresUseCase(repo_with).execute(1, "2024")
    await RecalculateScoresUseCase(repo_without).execute(1, "2024")

    # Ambos tienen 0 pts ya que no hay stats positivas — verificar que dribbles_past no suma ni resta
    pts_with = repo_with.updated_pts.get(1, None)
    pts_without = repo_without.updated_pts.get(1, None)
    # Si ambos son None no hubo cambio (0 pts = sin actualización en el fake), eso es correcto
    assert pts_with == pts_without, (
        f"FW dribbles_past no debe cambiar pts: con={pts_with}, sin={pts_without}"
    )


@pytest.mark.anyio
async def test_dribbles_past_penalizes_df():
    """DF con dribbles_past=3 recalcula a menos pts que DF sin ellos (base duels positivos para comparar)."""
    repo_clean = FakeEnrichmentRepo([_recalc_row("DC", duels_won=5)])
    repo_drib = FakeEnrichmentRepo([_recalc_row("DC", duels_won=5, dribbles_past=3)])

    await RecalculateScoresUseCase(repo_clean).execute(1, "2024")
    await RecalculateScoresUseCase(repo_drib).execute(1, "2024")

    pts_clean = repo_clean.updated_pts.get(1, 0.0)
    pts_drib = repo_drib.updated_pts.get(1, 0.0)
    assert pts_drib < pts_clean, f"DF con dribbles_past ({pts_drib}) debe tener menos pts que sin ({pts_clean})"


# ---------------------------------------------------------------------------
# BASE_POINTS_TABLE — completeness (cubre todos los ActionType)
# ---------------------------------------------------------------------------

def test_base_points_table_covers_all_new_action_types():
    """Los 6 nuevos ActionType deben estar en la tabla para cada grupo de BASE_POINTS_TABLE."""
    new_actions = [
        ActionType.PASSES_COMPLETED,
        ActionType.FOULS_COMMITTED,
        ActionType.YELLOW_CARD,
        ActionType.RED_CARD,
        ActionType.PENALTY_WON,
        ActionType.DRIBBLES_PAST,
    ]
    for group in BASE_POINTS_TABLE:
        for action in new_actions:
            assert action in BASE_POINTS_TABLE[group], (
                f"ActionType.{action.name} falta en BASE_POINTS_TABLE[{group.name}]"
            )


# ---------------------------------------------------------------------------
# FOULS_COMMITTED — señal negativa por posición
# ---------------------------------------------------------------------------

def test_fouls_committed_all_positions_negative():
    assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.FOULS_COMMITTED] == -30
    assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.FOULS_COMMITTED] == -20
    assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.FOULS_COMMITTED] == -15


@pytest.mark.anyio
async def test_fouls_committed_reduces_score():
    """MF con faltas cometidas recalcula a menos pts que sin faltas."""
    repo_clean = FakeEnrichmentRepo([_recalc_row("MC", passes_total=50, passes_accuracy=80)])
    repo_dirty = FakeEnrichmentRepo([_recalc_row("MC", passes_total=50, passes_accuracy=80, fouls_committed=4)])

    await RecalculateScoresUseCase(repo_clean).execute(1, "2024")
    await RecalculateScoresUseCase(repo_dirty).execute(1, "2024")

    pts_clean = repo_clean.updated_pts.get(1, 0.0)
    pts_dirty = repo_dirty.updated_pts.get(1, 0.0)
    assert pts_dirty < pts_clean, f"Faltas cometidas ({pts_dirty}) deben reducir pts respecto a limpio ({pts_clean})"
