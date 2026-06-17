from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class TeamStrength(Base):
    __tablename__ = "team_strengths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    strength: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    elo_raw: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="calculated")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "season", "competition_id", name="uq_team_strength"),
        CheckConstraint("strength BETWEEN 0 AND 100", name="ck_team_strength_range"),
        CheckConstraint(
            "source IN ('calculated', 'default', 'override', 'clubelo_seed', 'elo_v1', 'national_elo_seed')",
            name="ck_team_strength_source",
        ),
    )
