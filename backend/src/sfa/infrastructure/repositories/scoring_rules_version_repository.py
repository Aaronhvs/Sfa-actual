from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from sfa.domain.scoring.entities import ScoringRulesVersion
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import ScoringRulesVersionRepositoryPort
from sfa.infrastructure.models.scoring_rules.models import ScoringRulesVersion as ScoringRulesVersionModel


class ScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: ScoringRulesVersionModel) -> ScoringRulesVersion:
        config = ScoringConfig.from_dict(row.config_json)
        return ScoringRulesVersion(
            id=row.id,
            name=row.name,
            version=row.version,
            description=row.description or "",
            is_active=row.is_active,
            config=config,
            created_at=row.created_at,
        )

    async def get_active_version(self) -> ScoringRulesVersion | None:
        stmt = select(ScoringRulesVersionModel).where(
            ScoringRulesVersionModel.is_active.is_(True)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_version_by_id(self, version_id: int) -> ScoringRulesVersion | None:
        stmt = select(ScoringRulesVersionModel).where(
            ScoringRulesVersionModel.id == version_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def list_versions(self) -> list[ScoringRulesVersion]:
        stmt = select(ScoringRulesVersionModel).order_by(
            ScoringRulesVersionModel.created_at.desc()
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save_version(
        self,
        name: str,
        version: str,
        description: str,
        config: ScoringConfig,
    ) -> int:
        stmt = (
            pg_insert(ScoringRulesVersionModel)
            .values(
                name=name,
                version=version,
                description=description,
                is_active=False,
                config_json=config.to_dict(),
                created_at=datetime.now(timezone.utc),
            )
            .returning(ScoringRulesVersionModel.id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def set_active_version(self, version_id: int) -> None:
        # Ensure the version exists
        row = await self.get_version_by_id(version_id)
        if row is None:
            raise ValueError(f"ScoringRulesVersion id={version_id} not found")

        # Deactivate all, then activate the target — both in the same flush
        await self._session.execute(
            update(ScoringRulesVersionModel).values(is_active=False)
        )
        await self._session.execute(
            update(ScoringRulesVersionModel)
            .where(ScoringRulesVersionModel.id == version_id)
            .values(is_active=True)
        )
        await self._session.flush()
