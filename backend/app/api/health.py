"""Liveness and readiness of ReleaseGuard itself, at the root (outside ``/api/v1``) for container
health checks. Public: no session needed.
"""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.errors import ServiceUnavailableError
from app.schemas.errors import ErrorResponse
from app.services.health_service import database_is_ready

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/healthz", summary="Liveness: the process is up")
def healthz() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/readyz",
    summary="Readiness: the database is reachable",
    responses={503: {"model": ErrorResponse, "description": "The database is unreachable."}},
)
def readyz(request: Request) -> HealthResponse:
    if not database_is_ready(request.app.state.engine):
        raise ServiceUnavailableError()
    return HealthResponse()
