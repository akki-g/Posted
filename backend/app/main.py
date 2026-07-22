from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.seed import seed_demo_data
from app.db.session import create_engine, create_session_factory
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(json_logs=settings.app_env != "development")
    logger = structlog.get_logger()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if settings.demo_mode:
            async with session_factory() as session:
                await seed_demo_data(session, settings)
        logger.info("application_started", environment=settings.app_env)
        yield
        await engine.dispose()
        logger.info("application_stopped")

    app = FastAPI(
        title="Posted API",
        version="0.1.0",
        description="Portfolio intelligence for brokerage holdings and material events.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
