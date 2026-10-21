"""Shared transaction/CAS primitives; contains no business orchestration or commit."""
from sqlalchemy import bindparam, text
from sfa.domain.player_positions.publication import canonical

_EVENT_FIELDS = ("position", "base_points", "m1", "m2", "m3", "m4", "mvisit", "mrating",
                 "combined_before_clamp", "combined_after_clamp", "final_points", "calculation_details")
_ROLLUP_FIELDS = ("total_pts", "breakdown")


class PositionPublicationSQL:
    def __init__(self, session):
        self._session = session

    def _exclusive(self):
        if not self._session.info.get("position_publication_exclusive"):
            raise RuntimeError("Publication requires a dedicated exclusive transaction from its first query")
        transaction = self._session.sync_session.get_transaction()
        if transaction is not None and (self._session.info.get("position_locked_transaction") is not transaction
                                        or self._session.info.get("position_lock_mode") != "exclusive"):
            raise RuntimeError("Publication cannot upgrade an already started shared transaction")

    async def _rows(self, table, where, params, *, expanding=()):
        order = "t.fixture_id,t.team_id" if table == "fixture_team_strengths" else "t.id"
        statement = text(f"SELECT to_jsonb(t) FROM {table} t WHERE {where} ORDER BY {order}")
        if expanding:
            statement = statement.bindparams(*(bindparam(k, expanding=True) for k in expanding))
        return list((await self._session.execute(statement, params)).scalars())

    async def _replace_row(self, table, before, after, fields):
        # Both CAS and values use PostgreSQL's own record types/JSON conversion.
        sets = ",".join(f"{k}=x.{k}" for k in fields)
        statement = text(f"UPDATE {table} t SET {sets} FROM "
                         f"jsonb_populate_record(NULL::{table},CAST(:after AS jsonb)) x "
                         "WHERE t.id=x.id AND to_jsonb(t)=CAST(:before AS jsonb) RETURNING t.id")
        changed = await self._session.scalar(statement, {"after": canonical(after), "before": canonical(before)})
        if changed is None:
            raise ValueError(f"Concurrent mutation detected in {table} id={before['id']}")
