from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class CompetitionAchievementModel(Base):
    __tablename__ = "competition_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "competition_id", "team_id", "season", "phase",
            name="uq_competition_achievement",
        ),
        CheckConstraint("bonus_points >= 0", name="ck_achievement_bonus_positive"),
        CheckConstraint("weight > 0 AND weight <= 1.0", name="ck_achievement_weight_range"),
    )


class PlayerAchievementBonusModel(Base):
    __tablename__ = "player_achievement_bonuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    rules_version_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_rules_versions.id"), nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("competition_achievements.id", ondelete="CASCADE"), nullable=False
    )
    participation_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    final_bonus: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    calculation_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "player_id", "achievement_id", "rules_version_id",
            name="uq_player_achievement_bonus",
        ),
        CheckConstraint(
            "participation_ratio BETWEEN 0 AND 1",
            name="ck_participation_ratio_range",
        ),
        CheckConstraint("final_bonus >= 0", name="ck_final_bonus_positive"),
    )
