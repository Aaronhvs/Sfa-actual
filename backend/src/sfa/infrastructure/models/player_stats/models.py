from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sfa.infrastructure.database import Base


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    goals: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    corner_assists: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    shots_on: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    shots_total: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    passes_key: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    passes_total: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    passes_accuracy: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    dribbles_won: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    dribbles_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    dribbles_past: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    duels_won: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    duels_total: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    tackles_won: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    interceptions: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    blocks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    fouls_drawn: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    fouls_committed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    cards_yellow: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    cards_red: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    penalty_won: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    goals_conceded: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    appearances: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True, default=None)

    __table_args__ = (
        UniqueConstraint("player_id", "fixture_id", name="uq_player_stats"),
        CheckConstraint("goals >= 0", name="ck_ps_goals"),
        CheckConstraint("assists >= 0", name="ck_ps_assists"),
        CheckConstraint("corner_assists >= 0", name="ck_ps_corner_assists"),
        CheckConstraint("shots_on >= 0", name="ck_ps_shots_on"),
        CheckConstraint("shots_total >= 0", name="ck_ps_shots_total"),
        CheckConstraint("passes_key >= 0", name="ck_ps_passes_key"),
        CheckConstraint("passes_total >= 0", name="ck_ps_passes_total"),
        CheckConstraint("passes_accuracy BETWEEN 0 AND 100", name="ck_ps_passes_accuracy"),
        CheckConstraint("dribbles_won >= 0", name="ck_ps_dribbles_won"),
        CheckConstraint("dribbles_attempts >= 0", name="ck_ps_dribbles_attempts"),
        CheckConstraint("dribbles_past >= 0", name="ck_ps_dribbles_past"),
        CheckConstraint("duels_won >= 0", name="ck_ps_duels_won"),
        CheckConstraint("duels_total >= 0", name="ck_ps_duels_total"),
        CheckConstraint("tackles_won >= 0", name="ck_ps_tackles_won"),
        CheckConstraint("interceptions >= 0", name="ck_ps_interceptions"),
        CheckConstraint("blocks >= 0", name="ck_ps_blocks"),
        CheckConstraint("fouls_drawn >= 0", name="ck_ps_fouls_drawn"),
        CheckConstraint("fouls_committed >= 0", name="ck_ps_fouls_committed"),
        CheckConstraint("cards_yellow >= 0", name="ck_ps_cards_yellow"),
        CheckConstraint("cards_red >= 0", name="ck_ps_cards_red"),
        CheckConstraint("penalty_won >= 0", name="ck_ps_penalty_won"),
        CheckConstraint("saves >= 0", name="ck_ps_saves"),
        CheckConstraint("goals_conceded >= 0", name="ck_ps_goals_conceded"),
        CheckConstraint("minutes BETWEEN 0 AND 120", name="ck_ps_minutes"),
        CheckConstraint("appearances >= 0", name="ck_ps_appearances"),
    )
