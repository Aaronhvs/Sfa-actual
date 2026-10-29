from __future__ import annotations

from dataclasses import dataclass

FINAL_STATUSES = frozenset({"FT", "AET", "PEN", "AWD", "WO"})
INTERCONTINENTAL_NAME = "FIFA Intercontinental Cup"
INTERCONTINENTAL_POLICY = "intercontinental-title-v1"


def title_policy(competition_name: str, phase: str) -> tuple[int, float, str] | None:
    if competition_name != INTERCONTINENTAL_NAME:
        return None
    return (4000 if phase == "winner" else 0, 0.5, INTERCONTINENTAL_POLICY)


@dataclass(frozen=True)
class AuthoritativeFixtureResultDTO:
    fixture_id: int
    home_team_id: int
    away_team_id: int
    status: str
    home_goals: int | None
    away_goals: int | None
    home_penalty_goals: int | None = None
    away_penalty_goals: int | None = None
    verified: bool = False

    def winner(self) -> tuple[int | None, int | None]:
        if not self.verified or self.status not in FINAL_STATUSES:
            return None, None
        if self.home_goals is None or self.away_goals is None:
            return None, None
        if min(self.home_goals, self.away_goals) < 0:
            return None, None
        if self.status == "PEN":
            if self.home_goals != self.away_goals:
                return None, None
            h, a = self.home_penalty_goals, self.away_penalty_goals
            if h is None or a is None or min(h, a) < 0 or h == a:
                return None, None
        else:
            h, a = self.home_goals, self.away_goals
            if h == a:
                return None, None
        return (self.home_team_id, self.away_team_id) if h > a else (self.away_team_id, self.home_team_id)
