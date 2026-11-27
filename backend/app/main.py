"""ASGI entrypoint: ``uvicorn app.main:app``."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.request_id import REQUEST_ID_HEADER, RequestIdMiddleware
from app.core.security import OriginCheckMiddleware
from app.db.session import create_db_engine, create_session_factory
from app.schemas.errors import COMMON_ERROR_RESPONSES

API_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
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
            allow_headers=["Content-Type", "Idempotency-Key", REQUEST_ID_HEADER],
            expose_headers=[REQUEST_ID_HEADER],
        )
    # Outermost, so every response (a CSRF 403 or a CORS preflight too) carries the request id.
    app.add_middleware(RequestIdMiddleware)
    # Outermost of all: the client address comes from X-Forwarded-For only when the socket peer
    # is a configured proxy (Caddy); anyone else's header is ignored. Login throttling keys on it.
    # Run uvicorn with --no-proxy-headers: its CLI otherwise trusts X-Forwarded-For from
    # loopback on its own, whatever TRUSTED_PROXIES says.
    if settings.trusted_proxies:
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_proxies)
    elif settings.env == "production":
        # Behind Caddy every request would come from the proxy's address, so all clients would
        # share one login-throttle bucket: a few bad passwords would lock everyone out.
        get_logger(__name__).warning(
            "TRUSTED_PROXIES is empty in production: the login throttle keys every client on "
            "the reverse proxy's address; set it to Caddy's address or network"
        )

    app.include_router(health_router)
    app.include_router(api_router)
    return app


# Built at import time so a missing or invalid setting stops the process at startup.
app = create_app()
