"""``/applications``: application CRUD and archive, and each application's environments."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_capability
from app.core.permissions import Capability
from app.schemas.applications import ApplicationCreate, ApplicationOut, ApplicationUpdate
from app.schemas.common import Page
from app.schemas.environments import EnvironmentOut
from app.schemas.errors import UNAUTHORIZED_RESPONSE, ErrorResponse
from app.services import application_service, environment_service
from app.services.auth_service import Principal

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    responses={
        **UNAUTHORIZED_RESPONSE,
        404: {"model": ErrorResponse, "description": "Not found (or in another workspace)."},
    },
)

Viewer = Annotated[Principal, Depends(require_capability(Capability.VIEW))]
Manager = Annotated[Principal, Depends(require_capability(Capability.MANAGE_APPLICATIONS))]
_CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "Repository taken, or archived."}
}


@router.get("", summary="List applications (archived ones only with include_archived=true)")
def list_applications(
    principal: Viewer,
    db: DbSession,
    include_archived: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ApplicationOut]:
    items, total = application_service.list_applications(
        db, principal, include_archived=include_archived, page=page, page_size=page_size
    )
    return Page[ApplicationOut](
        items=[ApplicationOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses=_CONFLICT,
    summary="Create an application with development, staging and production environments",
)
def create_application(
    body: ApplicationCreate, principal: Manager, db: DbSession
) -> ApplicationOut:
    return ApplicationOut.model_validate(
        application_service.create_application(db, principal, body)
    )


@router.get("/{application_id}", summary="One application (archived ones too)")
def get_application(application_id: uuid.UUID, principal: Viewer, db: DbSession) -> ApplicationOut:
    return ApplicationOut.model_validate(
        application_service.get_application(db, principal, application_id)
    )


@router.patch("/{application_id}", responses=_CONFLICT, summary="Edit an application")
def update_application(
    application_id: uuid.UUID, body: ApplicationUpdate, principal: Manager, db: DbSession
) -> ApplicationOut:
    return ApplicationOut.model_validate(
        application_service.update_application(db, principal, application_id, body)
    )


@router.post(
    "/{application_id}/archive",
    summary="Archive: hidden from lists, history kept (idempotent)",
)
def archive_application(
    application_id: uuid.UUID, principal: Manager, db: DbSession
) -> ApplicationOut:
    return ApplicationOut.model_validate(
        application_service.archive_application(db, principal, application_id)
    )


@router.get(
    "/{application_id}/environments",
    summary="The application's environments, in promotion order",
)
def list_environments(
    application_id: uuid.UUID, principal: Viewer, db: DbSession
) -> list[EnvironmentOut]:
    return [
        EnvironmentOut.model_validate(env)
        for env in environment_service.list_environments(db, principal, application_id)
    ]
