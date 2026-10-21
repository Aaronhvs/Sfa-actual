"""Transaction-wide publication exclusion for all application database sessions."""
from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.orm import Session

POSITION_PUBLICATION_LOCK = 736615320261019


class PositionAwareSession(Session):
    """The publisher must set exclusive mode before opening its transaction."""


class PositionPublicationBusyError(RuntimeError):
    """Close/rollback this transaction and retry with a new dedicated session."""


def _acquire(session, connection):
    transaction = session.get_transaction()
    if session.info.get("position_locked_transaction") is transaction:
        expected = "exclusive" if session.info.get("position_publication_exclusive") else "shared"
        if session.info.get("position_lock_mode") != expected:
            raise RuntimeError("Cannot change position lock mode inside an existing transaction")
        return
    if connection.dialect.name != "postgresql":
        return
    isolation, readonly = connection.execute(text(
        "SELECT current_setting('transaction_isolation'), current_setting('transaction_read_only')"
    )).one()
    if isolation != "read committed" and readonly != "on":
        raise RuntimeError("Position-aware writers require READ COMMITTED isolation")
    function = ("pg_try_advisory_xact_lock" if session.info.get("position_publication_exclusive")
                else "pg_advisory_xact_lock_shared")
    acquired = connection.scalar(text(f"SELECT {function}(:key)"), {"key": POSITION_PUBLICATION_LOCK})
    if session.info.get("position_publication_exclusive") and not acquired:
        # Never enqueue an exclusive waiter: an outer shared orchestration session
        # may need another shared child session before it can finish/commit.
        raise PositionPublicationBusyError("Position publication is busy; rollback and retry in a new session")
    session.info["position_locked_transaction"] = transaction
    session.info["position_lock_mode"] = "exclusive" if session.info.get("position_publication_exclusive") else "shared"


@event.listens_for(PositionAwareSession, "after_begin")
def _begin(session, transaction, connection):
    if not transaction.nested and not session.info.get("position_initial_set_transaction"):
        _acquire(session, connection)


@event.listens_for(PositionAwareSession, "do_orm_execute", retval=True)
def _execute(state):
    session = state.session
    statement = str(state.statement).lstrip().upper()
    initial_set = statement.startswith("SET TRANSACTION ") and not session.in_transaction()
    if initial_set:
        session.info["position_initial_set_transaction"] = True
        try:
            return state.invoke_statement()
        finally:
            session.info.pop("position_initial_set_transaction", None)
    _acquire(session, session.connection())
    return state.invoke_statement()


@event.listens_for(PositionAwareSession, "before_flush")
def _flush(session, flush_context, instances):
    _acquire(session, session.connection())


@event.listens_for(PositionAwareSession, "after_transaction_create")
def _before_savepoint(session, transaction):
    if transaction.nested:
        # Acquire in the root before SAVEPOINT; a nested rollback must not release it.
        _acquire(session, session.connection())
