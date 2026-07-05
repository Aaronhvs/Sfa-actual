from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, Table

from sfa.infrastructure.repositories.sfa_score_repository import _stat_profile_filter

_metadata = MetaData()
_stats_table = Table(
    "fake_stats",
    _metadata,
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
