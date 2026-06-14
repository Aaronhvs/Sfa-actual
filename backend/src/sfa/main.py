import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from sfa.api.v1.achievements_router import router as achievements_router
from sfa.api.v1.admin import router as admin_router
from sfa.api.v1.compare import router as compare_router
from sfa.api.v1.competitions import router as competitions_router
from sfa.api.v1.elo_router import router as elo_router
from sfa.api.v1.health import router as health_router
from sfa.api.v1.players import router as players_router
from sfa.api.v1.ranking import router as ranking_router
from sfa.api.v1.scoring_rules_router import router as scoring_rules_router
from sfa.api.v1.seasons import router as seasons_router
from sfa.api.v1.status import router as status_router
from sfa.api.v1.wc_router import router as wc_router
from sfa.core.config import get_settings
from sfa.infrastructure.database import AsyncSessionLocal, engine
from sfa.infrastructure.models import Base  # noqa: F401 — also registers all SQLAlchemy models
from sfa.infrastructure.redis_client import get_redis_client

logger = logging.getLogger(__name__)

settings = get_settings()

tags_metadata = [
    {"name": "ranking", "description": "Rankings de jugadores por temporada"},
    {"name": "seasons", "description": "Temporadas disponibles en el sistema"},
    {"name": "players", "description": "Detalle de jugadores, eventos y fixtures"},
    {"name": "competitions", "description": "Competiciones y clasificaciones"},
    {"name": "compare", "description": "Comparación head-to-head entre dos jugadores"},
    {"name": "status", "description": "Estado del sistema"},
    {"name": "health", "description": "Health check de infraestructura"},
    {"name": "admin", "description": "Administración: disparar ingestas manualmente"},
    {"name": "scoring", "description": "Gestión de versiones de reglas de scoring y recálculo"},
    {"name": "mundial", "description": "Partidos y estado en vivo del Mundial 2026"},
]


@asynccontextmanager
async def lifespan(application: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema: OK")

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection: OK")
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)

    try:
        redis = get_redis_client()
        await redis.ping()
        logger.info("Redis connection: OK")
    except Exception as exc:
        logger.error("Redis connection failed: %s", exc)

    yield


app = FastAPI(
    title="SFA — Stadistic Football Award API",
    description="API REST para consultar rankings, jugadores, eventos y competiciones del sistema SFA.",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(ranking_router, prefix="/api/v1", tags=["ranking"])
app.include_router(seasons_router, prefix="/api/v1", tags=["seasons"])
app.include_router(players_router, prefix="/api/v1", tags=["players"])
app.include_router(competitions_router, prefix="/api/v1", tags=["competitions"])
app.include_router(compare_router, prefix="/api/v1", tags=["compare"])
app.include_router(status_router, prefix="/api/v1", tags=["status"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(elo_router, prefix="/api/v1", tags=["elo"])
app.include_router(scoring_rules_router, prefix="/api/v1", tags=["scoring"])
app.include_router(achievements_router, prefix="/api/v1", tags=["scoring"])
app.include_router(wc_router, prefix="/api/v1", tags=["mundial"])
