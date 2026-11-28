"""``/integrations``: link the GitHub App installation to the workspace, list, disconnect."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import DbSession, require_capability
from app.core.permissions import Capability
from app.schemas.errors import UNAUTHORIZED_RESPONSE, ErrorResponse
from app.schemas.integrations import GitHubInstallCallback, IntegrationOut
from app.services import integration_service
from app.services.auth_service import Principal

router = APIRouter(prefix="/integrations", tags=["integrations"], responses=UNAUTHORIZED_RESPONSE)

Admin = Annotated[Principal, Depends(require_capability(Capability.MANAGE_GITHUB_INTEGRATION))]


@router.get("", summary="The workspace's integrations, newest first (Admin)")
def list_integrations(principal: Admin, db: DbSession) -> list[IntegrationOut]:
    return [
        IntegrationOut.model_validate(item)
        for item in integration_service.list_integrations(db, principal)
    ]


@router.post(
    "/github/callback",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {"model": IntegrationOut, "description": "Already linked to this workspace."},
        409: {
            "model": ErrorResponse,
            "description": "Linked elsewhere (`installation_unavailable`), or the workspace "
            "already has another one (`integration_exists`).",
        },
    },
    summary="Link a GitHub App installation (Admin); the worker verifies it with GitHub",
)
def github_install_callback(
    body: GitHubInstallCallback, principal: Admin, db: DbSession, response: Response
) -> IntegrationOut:
    integration, created = integration_service.connect_github(db, principal, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return IntegrationOut.model_validate(integration)


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Not found (or in another workspace)."}
    },
    summary="Disconnect: dispatches stop at once; the record stays as history (idempotent)",
)
def disconnect_integration(integration_id: uuid.UUID, principal: Admin, db: DbSession) -> None:
    integration_service.disconnect(db, principal, integration_id)
