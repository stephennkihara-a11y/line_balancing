import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import engine, Base
from .routers import (
    auth, lines, machines, operators, styles, balance, imports,
    production, dashboard, rebalance, timestudy, iot, odoo,
)
from .schemas.common import HealthResponse
from .seed.bootstrap import bootstrap_if_empty

logger = logging.getLogger("line_balancing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables created by db/init.sql; this is a fallback for sqlite/dev without the migration
    Base.metadata.create_all(bind=engine)
    try:
        bootstrap_if_empty()
    except Exception as e:
        logger.warning("Bootstrap skipped: %s", e)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        description="AI-powered line balancing for apparel manufacturing.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=settings.environment)

    app.include_router(auth.router)
    app.include_router(lines.router)
    app.include_router(machines.router)
    app.include_router(operators.router)
    app.include_router(styles.router)
    app.include_router(balance.router)
    app.include_router(imports.router)
    # Phase 2
    app.include_router(production.router)
    app.include_router(dashboard.router)
    app.include_router(rebalance.router)
    # Phase 3
    app.include_router(timestudy.router)
    app.include_router(iot.router)
    app.include_router(odoo.router)

    return app


app = create_app()
