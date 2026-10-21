from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class PlayerNameAlias(Base):
    __tablename__ = "player_name_aliases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), index=True)
    external_player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    alias: Mapped[str] = mapped_column(String(250), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(250), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("player_id", "provider", "normalized_alias", name="uq_player_name_alias"),)
