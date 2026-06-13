from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol


@dataclass(frozen=True)
class SeasonsResult:
    seasons: list[SeasonDTO]


@runtime_checkable
class GetSeasonsUseCaseProtocol(Protocol):
    async def execute(self) -> SeasonsResult: ...


class GetSeasonsUseCase(GetSeasonsUseCaseProtocol):
    def __init__(self, season_repo: SeasonRepositoryProtocol) -> None:
        self._season_repo = season_repo

    async def execute(self) -> SeasonsResult:
        seasons = await self._season_repo.get_available_seasons()
        return SeasonsResult(seasons=seasons)
