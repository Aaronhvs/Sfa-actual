from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base
from sfa.infrastructure.models.enums import Position


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    # deprecated: do not write; team identity belongs to appearance snapshots.
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=True
    )
    position: Mapped[Position] = mapped_column(
        Enum(Position, native_enum=False), nullable=False
    )
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbref_id: Mapped[str | None] = mapped_column(String(150), nullable=True, unique=True)
    understat_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    position_source: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="apifootball"
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Migration:
    # ALTER TABLE players ADD COLUMN fbref_id VARCHAR(150) UNIQUE;
    # ALTER TABLE players ADD COLUMN understat_id INTEGER UNIQUE;
    # ALTER TABLE players ADD COLUMN IF NOT EXISTS position_source VARCHAR(20) NOT NULL DEFAULT 'apifootball';
    # ALTER TABLE players ADD COLUMN IF NOT EXISTS birth_date DATE NULL;  -- 0034
