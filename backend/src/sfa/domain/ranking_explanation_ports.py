from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sfa.domain.ports import RankedPlayerDTO


@dataclass(frozen=True)
class RankingExplanationRequestDTO:
    season: str
    competition_id: int | None
    rules_version_id: int | None
    scope: str
    limit: int = 10
    use_total: bool = True
    force: bool = False


@dataclass(frozen=True)
class RankingExplanationEvidenceDTO:
    player_id: int
    season: str
    competition_id: int | None
    rules_version_id: int | None
    scope: str
    rank: int
    source_hash: str
    evidence: dict


@dataclass(frozen=True)
class RankingExplanationWriteResultDTO:
    short_text: str
    long_text: str
    bullets: list[str]
    variant: str
    status: str
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_estimate_usd: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class RankingPlayerExplanationDTO:
    id: int
    player_id: int
    player_name: str | None
    team_name: str | None
    team_logo_url: str | None
    season: str
    competition_id: int | None
    rules_version_id: int | None
    scope: str
    rank: int
    variant: str
    status: str
    short_text: str
    long_text: str
    bullets: list[str]
    evidence: dict
    model_name: str | None
    prompt_version: str
    generated_at: datetime


@dataclass(frozen=True)
class RankingExplanationGenerationSummaryDTO:
    season: str
    competition_id: int | None
    rules_version_id: int | None
    scope: str
    generated: int
    fallback: int
    skipped: int
    failed: int
    estimated_cost_usd: float


@runtime_checkable
class RankingExplanationRepositoryProtocol(Protocol):
    async def build_evidence(
        self,
        request: RankingExplanationRequestDTO,
        ranked_players: list[RankedPlayerDTO],
    ) -> list[RankingExplanationEvidenceDTO]: ...

    async def get_cached_for_scope(
        self,
        request: RankingExplanationRequestDTO,
    ) -> list[RankingPlayerExplanationDTO]: ...

    async def get_cached_for_player(
        self,
        player_id: int,
        request: RankingExplanationRequestDTO,
    ) -> RankingPlayerExplanationDTO | None: ...

    async def get_source_hash(
        self,
        player_id: int,
        request: RankingExplanationRequestDTO,
    ) -> str | None: ...

    async def upsert_explanation(
        self,
        evidence: RankingExplanationEvidenceDTO,
        result: RankingExplanationWriteResultDTO,
        prompt_version: str,
    ) -> None: ...

    async def mark_stale_for_scope(
        self,
        request: RankingExplanationRequestDTO,
        fresh_hashes: dict[int, str],
    ) -> int: ...


@runtime_checkable
class RankingExplanationWriterPort(Protocol):
    async def write(
        self,
        evidence: RankingExplanationEvidenceDTO,
    ) -> RankingExplanationWriteResultDTO: ...
