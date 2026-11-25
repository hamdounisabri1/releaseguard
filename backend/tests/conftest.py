import os

# Set before anything imports app.main, which builds the app (and its settings) at import time.
# Explicit values override a developer's repo-root .env, so tests don't depend on it.
os.environ["ENV"] = "local"
os.environ["SITE_ORIGIN"] = "http://testserver"
os.environ["CORS_ORIGINS"] = ""
os.environ["LOG_LEVEL"] = "INFO"

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.main import create_app

SITE_ORIGIN = "http://testserver"
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
