from sqlalchemy import and_, func, or_, select

from sfa.domain.player_name_aliases import normalize_search_name
from sfa.infrastructure.models.player_name_aliases import PlayerNameAlias


def player_name_filter(player_id, display_name, query: str):
    """All tokens in one observed name; EXISTS never multiplies score rows."""
    tokens = normalize_search_name(query).split()
    if not tokens:
        return display_name == query

    def matches(column):
        normalized = func.regexp_replace(func.lower(func.unaccent(column)), r"[^[:alnum:]]+", " ", "g")
        return and_(*(normalized.ilike(func.concat("%", func.unaccent(token), "%")) for token in tokens))

    aliases = select(PlayerNameAlias.id).where(
        PlayerNameAlias.player_id == player_id, matches(PlayerNameAlias.normalized_alias),
    ).correlate_except(PlayerNameAlias).exists()
    return or_(matches(display_name), aliases)
