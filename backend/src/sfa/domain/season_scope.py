from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScopeKind(str, Enum):
    AWARD_PERIOD = "award_period"
    TOURNAMENT = "tournament"
    ALL_TIME = "all_time"


@dataclass(frozen=True)
class ScoreSource:
    season: str
    competition_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        season = self.season.strip()
        competition_ids = tuple(sorted(set(self.competition_ids)))
        if not season:
            raise ValueError("ScoreSource season cannot be empty")
        if not competition_ids or any(item <= 0 for item in competition_ids):
            raise ValueError("ScoreSource competition_ids must contain positive IDs")
        object.__setattr__(self, "season", season)
        object.__setattr__(self, "competition_ids", competition_ids)

    @property
    def pairs(self) -> frozenset[tuple[str, int]]:
        return frozenset((self.season, item) for item in self.competition_ids)


@dataclass(frozen=True)
class AwardPeriodScope:
    key: str
    label: str
    kind: ScopeKind
    sources: tuple[ScoreSource, ...]
    is_latest: bool = False
    includes_world_cup: bool = False

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.label.strip():
            raise ValueError("AwardPeriodScope key and label cannot be empty")
        if self.kind != ScopeKind.ALL_TIME and not self.sources:
            raise ValueError("A non-all-time scope requires at least one source")
        pairs = [pair for source in self.sources for pair in source.pairs]
        if len(pairs) != len(set(pairs)):
            raise ValueError("AwardPeriodScope sources cannot overlap")
        if self.kind == ScopeKind.TOURNAMENT:
            if len(self.sources) != 1 or len(self.sources[0].competition_ids) != 1:
                raise ValueError("Tournament scope requires exactly one competition")
        if self.is_latest and self.kind != ScopeKind.AWARD_PERIOD:
            raise ValueError("Only an award period can be latest")

    @property
    def pairs(self) -> frozenset[tuple[str, int]]:
        return frozenset(pair for source in self.sources for pair in source.pairs)


class ScopeNotFoundError(ValueError):
    def __init__(self, scope_key: str) -> None:
        super().__init__(f"Unknown season scope: {scope_key}")
        self.scope_key = scope_key


class InconsistentScopeRulesVersionError(ValueError):
    def __init__(self, scope_key: str) -> None:
        super().__init__(f"No rules version covers every source in scope {scope_key}")
        self.scope_key = scope_key
