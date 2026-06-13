ELO_FLOOR = 1400.0
ELO_RANGE = 700.0
ELO_DEFAULT = 1500.0

DEFAULT_K_FACTORS: dict[int, float] = {}


class EloCalculatorService:
    @staticmethod
    def normalize(elo: float) -> float:
        """Convert raw ELO to the normalized 0-100 team strength scale."""
        normalized = (elo - ELO_FLOOR) / ELO_RANGE * 100.0
        return max(0.0, min(100.0, normalized))

    @staticmethod
    def expected_score(player_elo: float, rival_elo: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rival_elo - player_elo) / 400.0))

    @staticmethod
    def actual_score(home_goals: int, away_goals: int, is_home: bool) -> float:
        if home_goals > away_goals:
            return 1.0 if is_home else 0.0
        if home_goals == away_goals:
            return 0.5
        return 0.0 if is_home else 1.0

    @staticmethod
    def update_elo(
        current_elo: float,
        rival_elo: float,
        home_goals: int,
        away_goals: int,
        is_home: bool,
        k_factor: float,
    ) -> float:
        expected = EloCalculatorService.expected_score(current_elo, rival_elo)
        actual = EloCalculatorService.actual_score(home_goals, away_goals, is_home)
        return current_elo + k_factor * (actual - expected)
