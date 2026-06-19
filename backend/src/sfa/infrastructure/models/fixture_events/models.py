from sqlalchemy import Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class FixtureEvent(Base):
    __tablename__ = "fixture_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    extra_minute: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    team_external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    player_name: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    assist_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_sequence: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    __table_args__ = (
        Index("ix_fixture_events_fixture_external_id", "fixture_external_id"),
    )
