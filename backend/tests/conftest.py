import os

# Set before anything imports app.main, which builds the app (and its settings) at import time.
# Explicit values override a developer's repo-root .env, so tests don't depend on it.
os.environ["ENV"] = "local"
os.environ["SITE_ORIGIN"] = "http://testserver"
os.environ["CORS_ORIGINS"] = ""
os.environ["LOG_LEVEL"] = "INFO"
# Tests never touch the development database: TEST_DATABASE_URL (or this default) is migrated
# from scratch at the start of the run.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/releaseguard_test"
)

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.session import create_db_engine
from app.main import create_app
from app.services import auth_service
from app.services.auth_service import SESSION_COOKIE

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
SITE_ORIGIN = "http://testserver"
BACKEND_DIR = Path(__file__).resolve().parents[1]
ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]


class Payload(BaseModel):
    name: str
    count: int


def _test_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.api_route("/_test/echo", methods=ALL_METHODS, include_in_schema=False)
    async def echo() -> dict[str, bool]:
        return {"ok": True}

    # The two CSRF-exempt endpoints (the real handlers arrive in later Tasks), plus methods and
    # paths next to them that must stay protected.
    @router.api_route("/github/webhooks", methods=["POST", "PUT"], include_in_schema=False)
    async def webhooks() -> dict[str, bool]:
        return {"ok": True}

    @router.post("/github/webhooks/extra")
    async def webhooks_extra() -> dict[str, bool]:
        return {"ok": True}

    @router.api_route("/_test/propfind", methods=["PROPFIND"], include_in_schema=False)
    async def propfind() -> dict[str, bool]:
        return {"ok": True}

    @router.post("/releases/ci")
    async def releases_ci() -> dict[str, bool]:
        return {"ok": True}

    @router.get("/_test/errors/{kind}")
    async def raise_app_error(kind: str) -> None:
        errors = {
            "not_found": NotFoundError(),
            "forbidden": ForbiddenError("Only admins can do this."),
            "conflict": ConflictError(code="environment_busy", details={"environment": "prod"}),
        }
        raise errors[kind]

    @router.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    @router.post("/_test/validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    return router


def build_app(**overrides: Any) -> FastAPI:
    values: dict[str, Any] = {"env": "local", "site_origin": SITE_ORIGIN, "cors_origins": []}
    values.update(overrides)
    app = create_app(Settings(_env_file=None, **values))
    app.include_router(_test_router())
    return app


def client_for(app: FastAPI) -> AsyncClient:
    # raise_app_exceptions=False: Starlette re-raises unhandled errors after sending the 500,
    # and the tests want to inspect that response.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url=SITE_ORIGIN)


@pytest.fixture
def app() -> FastAPI:
    return build_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(app) as c:
        yield c


# --- Database -----------------------------------------------------------------------------


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """The test database, rebuilt from the migrations once per run."""
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_db_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test.

    ``create_savepoint`` turns the services' own ``commit()``/``rollback()`` into savepoint
    operations, so they behave normally while nothing outlives the test.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def db_app(db: Session) -> FastAPI:
    """The app with every request using the test's session."""
    app = build_app()
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
async def db_client(db_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(db_app) as c:
        yield c


def sign_in(client: AsyncClient, db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> str:
    """Give ``client`` a live session without the (slow) password check. Returns the token."""
    token = auth_service.create_session(db, user_id, workspace_id)
    # Set as a plain cookie: the real one is Secure, which httpx won't send to http://testserver.
    client.cookies.set(SESSION_COOKIE, token)
    return token
