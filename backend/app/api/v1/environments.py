"""``/environments/{id}``: read one environment; Admins edit its health timing and policy."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_capability
from app.core.permissions import Capability
from app.schemas.environments import EnvironmentOut, EnvironmentUpdate
from app.schemas.errors import UNAUTHORIZED_RESPONSE, ErrorResponse
from app.services import environment_service
from app.services.auth_service import Principal

router = APIRouter(
    prefix="/environments",
    tags=["environments"],
    responses={
        **UNAUTHORIZED_RESPONSE,
        404: {"model": ErrorResponse, "description": "Not found (or in another workspace)."},
    },
)

Viewer = Annotated[Principal, Depends(require_capability(Capability.VIEW))]
Configurer = Annotated[Principal, Depends(require_capability(Capability.CONFIGURE_ENVIRONMENTS))]


@router.get("/{environment_id}", summary="One environment")
def get_environment(environment_id: uuid.UUID, principal: Viewer, db: DbSession) -> EnvironmentOut:
    return EnvironmentOut.model_validate(
        environment_service.get_environment(db, principal, environment_id)
    )


@router.patch(
    "/{environment_id}",
    summary="Edit health-check timing and policy (Admin)",
    description="Only the fields sent change; `policy` is merged field by field. "
    "`promote_from_environment_id` must be another environment of the same application and "
    "must not create a cycle (422 `invalid_policy`). The health URL arrives in Sprint 4.",
    responses={409: {"model": ErrorResponse, "description": "The application is archived."}},
)
def update_environment(
    environment_id: uuid.UUID, body: EnvironmentUpdate, principal: Configurer, db: DbSession
) -> EnvironmentOut:
    return EnvironmentOut.model_validate(
        environment_service.update_environment(db, principal, environment_id, body)
    )
