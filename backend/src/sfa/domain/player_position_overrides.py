from __future__ import annotations

import unicodedata

WORLD_CUP_COMPETITION_ID = 350

_OVERRIDE_NAMES_BY_POSITION: dict[str, tuple[str, ...]] = {
    "EXT": ("messi", "lionel messi"),
    "LAT": ("kimmich", "joshua kimmich"),
}


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_value.casefold().split())


def override_name_terms_for_position(position: str | None) -> tuple[str, ...]:
    if position is None:
        return ()
    return _OVERRIDE_NAMES_BY_POSITION.get(position.upper(), ())


def position_for_context(
    default_position: str | None,
    *,
    player_name: str | None,
    team_name: str | None = None,
    competition_id: int | None = None,
) -> str | None:
    """Return the tactical position for the current context.

    These are explicit World Cup beta overrides. They intentionally do not mutate
    the player's global position because club and national-team roles can differ.
    """
    name = _normalize(player_name)
    team = _normalize(team_name)
    is_world_cup = competition_id == WORLD_CUP_COMPETITION_ID

    if "messi" in name and (is_world_cup or team == "argentina"):
        return "EXT"

    if "kimmich" in name and (is_world_cup or team in {"germany", "alemania"}):
        return "LAT"

    return default_position
