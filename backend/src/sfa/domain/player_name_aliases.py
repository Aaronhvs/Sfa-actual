"""Observed identity texts for search; never expand an initial into a name."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sfa.domain.name_matching import normalize


def normalize_search_name(value: str) -> str:
    return re.sub(r"[\W_]+", " ", normalize(value), flags=re.UNICODE).strip()


@dataclass(frozen=True)
class PlayerNameProfileDTO:
    external_id: int
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None

    def aliases(self) -> tuple[str, ...]:
        values = [self.display_name, self.full_name]
        if self.first_name and self.last_name:
            values.append(f"{self.first_name} {self.last_name}")
        found = {}
        for value in values:
            if value and value.strip():
                alias = " ".join(value.split())
                if len(alias) > 250:
                    raise ValueError("Player name alias exceeds 250 characters")
                key = normalize_search_name(alias)
                if key:
                    found.setdefault(key, alias)
        return tuple(found.values())


@dataclass(frozen=True)
class PlayerNameProfilePageDTO:
    profiles: tuple[PlayerNameProfileDTO, ...]
    page: int
    total_pages: int


@dataclass(frozen=True)
class NameAliasEnrichmentResult:
    profiles: int
    aliases_added: int
    unknown_external_ids: tuple[int, ...]


class PlayerNameAliasRepositoryProtocol(Protocol):
    async def find_player_id(self, external_id: int) -> int | None: ...
    async def add_aliases(self, player_id: int, external_id: int, aliases: tuple[str, ...], *,
                          provider: str, source_ref: str, captured_at: datetime) -> int: ...


class PlayerNameProfileProviderProtocol(Protocol):
    async def fetch_player_name_profile(self, player_id: int, season: int) -> PlayerNameProfileDTO | None: ...
    async def fetch_team_name_profiles(self, team_id: int, season: int, page: int = 1) -> PlayerNameProfilePageDTO: ...
