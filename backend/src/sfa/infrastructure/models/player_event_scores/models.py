from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class PlayerEventScore(Base):
    __tablename__ = "player_event_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("player_events.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id"), nullable=False
    )
    rules_version_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_rules_versions.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[str] = mapped_column(String(10), nullable=False)
    base_points: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    m1: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    m2: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    m3: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    m4: Mapped[float] = mapped_column(Numeric(5, 3), nullable=False)
    mvisit: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.0)
    mrating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=1.0)
    combined_before_clamp: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    combined_after_clamp: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    final_points: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    calculation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "rules_version_id", name="uq_pes_event_version"),
    )
