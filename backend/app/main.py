"""ASGI entrypoint: ``uvicorn app.main:app``."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.security import OriginCheckMiddleware
from app.db.session import create_db_engine, create_session_factory
from app.schemas.errors import COMMON_ERROR_RESPONSES

API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="ReleaseGuard API",
        version=API_VERSION,
        description="Deployment approval and rollback manager.",
        # Documents the real error shape on every route (and replaces FastAPI's default 422).
        responses=COMMON_ERROR_RESPONSES,
    )
    app.state.settings = settings
    # Lazy: nothing connects until the first query, so the app starts without a database
    # (/readyz reports it).
    app.state.engine = create_db_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)

    register_exception_handlers(app)

    # add_middleware wraps the stack, so the last one added runs first.
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.allowed_origins)
    if settings.cors_enabled:  # local development only: frontend and API on different ports
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
        )

    app.include_router(api_router)
    return app


# Built at import time so a missing or invalid setting stops the process at startup.
app = create_app()
