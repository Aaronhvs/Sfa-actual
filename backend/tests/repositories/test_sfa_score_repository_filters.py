from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Numeric, Table

from sfa.infrastructure.repositories.sfa_score_repository import (
    _ranking_order_column,
    _stat_profile_filter,
)

_metadata = MetaData()
_stats_table = Table(
    "fake_stats",
    _metadata,
    Column("goals", Integer),
    Column("assists", Integer),
)
_order_table = Table(
    "fake_order",
    _metadata,
    Column("pts", Numeric),
    Column("goals", Integer),
    Column("assists", Integer),
)


def test_stat_profile_filter_returns_none_for_no_profile():
    assert _stat_profile_filter(None, _stats_table.c.goals, _stats_table.c.assists) is None


def test_stat_profile_filter_returns_none_for_bonus_label_values():
    assert _stat_profile_filter("Promesa", _stats_table.c.goals, _stats_table.c.assists) is None
    assert _stat_profile_filter("Veterano", _stats_table.c.goals, _stats_table.c.assists) is None


def test_stat_profile_filter_goleador_filters_by_goals_threshold():
    expr = _stat_profile_filter("Goleador", _stats_table.c.goals, _stats_table.c.assists)

    compiled = str(expr.compile(compile_kwargs={"literal_binds": True}))

    assert "fake_stats.goals >= 1" in compiled


def test_stat_profile_filter_asistidor_filters_by_assists_threshold():
    expr = _stat_profile_filter("Asistidor", _stats_table.c.goals, _stats_table.c.assists)

    compiled = str(expr.compile(compile_kwargs={"literal_binds": True}))

    assert "fake_stats.assists >= 1" in compiled


def test_ranking_order_column_defaults_to_points():
    for label in (None, "Promesa", "Veterano"):
        col = _ranking_order_column(label, _order_table.c.pts, _order_table.c.goals, _order_table.c.assists)
        assert col is _order_table.c.pts


def test_ranking_order_column_goleador_orders_by_goals():
    col = _ranking_order_column("Goleador", _order_table.c.pts, _order_table.c.goals, _order_table.c.assists)
    assert col is _order_table.c.goals


def test_ranking_order_column_asistidor_orders_by_assists():
    col = _ranking_order_column("Asistidor", _order_table.c.pts, _order_table.c.goals, _order_table.c.assists)
    assert col is _order_table.c.assists
