import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from sfa.core.config import get_settings

settings = get_settings()

# Celery workers set SFA_NULLPOOL=1 to prevent asyncpg connections from being
# shared across forked processes. The API server uses a real connection pool.
_use_nullpool = os.getenv("SFA_NULLPOOL", "0") == "1"

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool if _use_nullpool else None,
    **({} if _use_nullpool else {"pool_size": 5, "max_overflow": 10}),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
