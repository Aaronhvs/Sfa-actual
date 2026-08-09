from __future__ import annotations

COMPETITION_CATEGORY_MAP: dict[str, str] = {
    "World Cup": "world_cup",
    "Champions League": "champions_league",
    "Europa League": "europa_league",
    "Conference League": "conference_league",
    "Premier League": "domestic_league",
    "La Liga": "domestic_league",
    "Serie A": "domestic_league",
    "Bundesliga": "domestic_league",
    "Ligue 1": "domestic_league",
    "Primeira Liga": "domestic_league",
    "Eredivisie": "domestic_league",
    "Jupiler Pro League": "domestic_league",
    "S\u00fcper Lig": "domestic_league",
    "Scottish Premiership": "domestic_league",
    "FA Cup": "domestic_cup_major",
    "Copa del Rey": "domestic_cup_major",
    "DFB-Pokal": "domestic_cup_major",
    "Coppa Italia": "domestic_cup_major",
    "Coupe de France": "domestic_cup_major",
    "EFL Cup": "domestic_cup_minor",
    "Community Shield": "domestic_cup_minor",
    "Supercopa de Espa\u00f1a": "domestic_cup_minor",
    "Supercoppa Italiana": "domestic_cup_minor",
    "DFL-Supercup": "domestic_cup_minor",
    "Troph\u00e9e des Champions": "domestic_cup_minor",
    "UEFA Super Cup": "domestic_cup_minor",
}

SINGULAR_ACHIEVEMENT_PHASES = frozenset({"champion", "runner_up", "winner"})
TERMINAL_KNOCKOUT_PHASES = frozenset({"runner_up", "winner"})

UNSCORED_PHASES_BY_CATEGORY: dict[str, frozenset[str]] = {
    "champions_league": frozenset({"runner_up"}),
    "europa_league": frozenset({"runner_up"}),
    "conference_league": frozenset({"runner_up"}),
}


def get_competition_category(competition_name: str) -> str | None:
    return COMPETITION_CATEGORY_MAP.get(competition_name)
