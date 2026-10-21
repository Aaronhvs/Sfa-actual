from __future__ import annotations

from datetime import datetime

from sfa.domain.player_name_aliases import (
    NameAliasEnrichmentResult,
    PlayerNameAliasRepositoryProtocol,
    PlayerNameProfileDTO,
)


class EnrichPlayerNameAliasesUseCase:
    def __init__(self, repository: PlayerNameAliasRepositoryProtocol):
        self._repository = repository

    async def execute(self, profiles: tuple[PlayerNameProfileDTO, ...], *, provider: str,
                      source_ref: str, captured_at: datetime) -> NameAliasEnrichmentResult:
        if not provider.strip() or not source_ref.strip() or captured_at.tzinfo is None:
            raise ValueError("Name aliases require provider, provenance and timezone-aware capture")
        if len(provider) > 80:
            raise ValueError("Provider exceeds 80 characters")
        added, unknown = 0, set()
        for profile in profiles:
            if type(profile.external_id) is not int or profile.external_id <= 0:
                raise ValueError("Invalid external player identity")
            player_id = await self._repository.find_player_id(profile.external_id)
            if player_id is None:
                unknown.add(profile.external_id)
                continue
            added += await self._repository.add_aliases(
                player_id, profile.external_id, profile.aliases(), provider=provider,
                source_ref=source_ref, captured_at=captured_at,
            )
        return NameAliasEnrichmentResult(len(profiles), added, tuple(sorted(unknown)))
