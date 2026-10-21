"""Shared SQL projection; apply before filtering, counting or paginating."""
from __future__ import annotations

from sqlalchemy import ARRAY, Integer, String, cast, column, func, or_, select, table

from sfa.infrastructure.models.fixtures.models import Fixture
from sfa.infrastructure.models.players.models import Player
from sfa.infrastructure.models.player_positions.models import PlayerPositionAssignment


def scope_position(scope, competition_id, fallback):
    if scope is None:
        return fallback
    from sqlalchemy.dialects.postgresql import array
    competition_ids = sorted({c for source in scope.sources for c in source.competition_ids})
    classifications = table('position_scope_classifications',column('player_id',Integer),
        column('scope_key',String),column('position',String),column('batch_id',String),
        column('competition_ids',ARRAY(Integer)),column('scope_competition_ids',ARRAY(Integer))).alias('reviewed_scope')
    batches = table('position_correction_batches',column('batch_id',String),column('status',String)).alias('scope_publication')
    lookup = (select(classifications.c.position).select_from(classifications.join(batches,
        batches.c.batch_id==classifications.c.batch_id)).where(classifications.c.player_id==Player.id,
        classifications.c.scope_key==scope.key,batches.c.status=='published',
        classifications.c.scope_competition_ids==array(competition_ids)))
    if competition_id is not None:
        lookup=lookup.where(classifications.c.competition_ids.any(competition_id))
    return func.coalesce(lookup.correlate(Player).scalar_subquery(),fallback)


def scope_reference_position(*, scope, season, team_id, competition_id, fallback):
    as_of = func.now()
    if not scope.is_latest:
        from sqlalchemy import and_
        filters = [and_(Fixture.season == s.season, Fixture.competition_id.in_(s.competition_ids))
                   for s in scope.sources]
        as_of = select(func.max(Fixture.played_at)).where(or_(*filters)).scalar_subquery()
    # Keep the complete projection visible to the PostgreSQL planner. Calling
    # scalar SQL/PLpgSQL resolvers for every candidate hides this indexed lookup.
    assignment=PlayerPositionAssignment.__table__.alias('habitual_reference')
    batches=table('position_correction_batches',column('batch_id',String),column('status',String)).alias('reference_publication')
    lookup=(select(assignment.c.position).select_from(assignment.outerjoin(batches,
        batches.c.batch_id==assignment.c.publication_batch_id)).where(
        assignment.c.player_id==Player.id,assignment.c.status=='accepted',
        assignment.c.assertion_kind=='habitual_football_role',assignment.c.applicable_fixture_ids.is_(None),
        assignment.c.effective_from<=as_of,or_(assignment.c.effective_until.is_(None),as_of<assignment.c.effective_until),
        or_(assignment.c.team_id.is_(None),assignment.c.team_id==team_id),
        or_(assignment.c.competition_id.is_(None),assignment.c.competition_id==competition_id),
        or_(assignment.c.season.is_(None),assignment.c.season==season),
        or_(assignment.c.publication_batch_id.is_(None),batches.c.status=='published'))
        .order_by(assignment.c.effective_from.desc(),assignment.c.id.desc()).limit(1)
        .correlate_except(assignment,batches).scalar_subquery())
    return func.coalesce(lookup,fallback)


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
