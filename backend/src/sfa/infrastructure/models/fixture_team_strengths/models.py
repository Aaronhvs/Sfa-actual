from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class FixtureTeamStrength(Base):
    __tablename__ = "fixture_team_strengths"

    fixture_id: Mapped[int] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        primary_key=True,
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    competition_id: Mapped[int] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    participant_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    pre_match_elo_raw: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    post_match_elo_raw: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    pre_match_strength: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    post_match_strength: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    seed_source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "participant_kind IN ('club', 'national_team')",
            name="ck_fixture_team_strength_kind",
        ),
        CheckConstraint(
            "pre_match_strength BETWEEN 0 AND 100",
            name="ck_fixture_team_pre_strength",
        ),
        CheckConstraint(
            "post_match_strength BETWEEN 0 AND 100",
            name="ck_fixture_team_post_strength",
        ),
        CheckConstraint(
            "pre_match_elo_raw > 0 AND post_match_elo_raw > 0",
            name="ck_fixture_team_elo_positive",
        ),
    )
