from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class TeamEloSeed(Base):
    __tablename__ = "team_elo_seeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    participant_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    elo_raw: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    effective_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provenance_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "season", "participant_kind", name="uq_team_elo_seed"),
        CheckConstraint(
            "participant_kind IN ('club', 'national_team')",
            name="ck_team_elo_seed_kind",
        ),
        CheckConstraint("elo_raw > 0", name="ck_team_elo_seed_positive"),
    )
