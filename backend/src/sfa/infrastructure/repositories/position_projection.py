"""Shared SQL projection; apply before filtering, counting or paginating."""
from __future__ import annotations

from sqlalchemy import String, cast, func, select

from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.players.models import Player


def scope_position(scope, competition_id, fallback):
    if scope is None:
        return fallback
    from sqlalchemy.dialects.postgresql import array
    competition_ids = sorted({c for source in scope.sources for c in source.competition_ids})
    return func.sfa_scope_position(Player.id, scope.key, competition_id, array(competition_ids), fallback)


def current_position(*, season=None, competition_id=None, scope=None):
    as_of = func.now()
    if scope is not None and not scope.is_latest:
        from sqlalchemy import and_, or_

        filters = [and_(Fixture.season == source.season, Fixture.competition_id.in_(source.competition_ids))
                   for source in scope.sources]
        as_of = select(func.max(Fixture.played_at)).where(or_(*filters)).scalar_subquery()
    return func.sfa_current_position(Player.id, competition_id, season, as_of).label("position")


def historical_position(*, team_id, competition_id, season, played_at, fixture_id):
    return func.coalesce(
        func.sfa_accepted_position(Player.id, team_id, competition_id, season, played_at, fixture_id),
        func.sfa_legacy_position(cast(Player.position, String), Player.name, None, competition_id),
    ).label("position")
