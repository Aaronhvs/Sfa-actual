"""Eligibility for a period; maximum is measured before user/profile filters."""


def ranking_min_matches(max_matches: int) -> int:
    return min(5, max(1, (max_matches + 3) // 4))
