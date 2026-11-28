"""``/releases``: registration from CI (GitHub OIDC, no session) and manual registration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CiClaims, DbSession, require_capability
from app.core.permissions import Capability
from app.schemas.errors import UNAUTHORIZED_RESPONSE, ErrorResponse
from app.schemas.releases import ReleaseCiCreate, ReleaseCreate, ReleaseOut
from app.services import release_service
from app.services.auth_service import Principal

router = APIRouter(prefix="/releases", tags=["releases"])

Registrar = Annotated[Principal, Depends(require_capability(Capability.REGISTER_RELEASES))]


@router.post(
    "/ci",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ReleaseOut, "description": "Replay: this version and build exist already."},
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired OIDC token."},
        403: {
            "model": ErrorResponse,
            "description": "The token's repository, workflow, ref, event, branch, SHA or run "
            "doesn't match a registered application (`oidc_binding_mismatch`).",
        },
        409: {
            "model": ErrorResponse,
            "description": "The version exists with another build, or the run registered "
            "another version already (`release_version_exists`); the repository is bound in "
            "more than one workspace (`repository_ambiguous`).",
        },
        503: {"model": ErrorResponse, "description": "GitHub's OIDC keys are unreachable."},
    },
    summary="Register a release from CI with a GitHub Actions OIDC token (ADR-0006)",
)
def register_ci_release(
    body: ReleaseCiCreate, claims: CiClaims, db: DbSession, response: Response
) -> ReleaseOut:
    release, created = release_service.register_ci_release(db, claims, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ReleaseOut.model_validate(release)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        **UNAUTHORIZED_RESPONSE,
        404: {"model": ErrorResponse, "description": "No such application in this workspace."},
        409: {"model": ErrorResponse, "description": "Version exists, or application archived."},
    },
    summary="Register a release manually (Admin/Developer fallback)",
)
def register_release(body: ReleaseCreate, principal: Registrar, db: DbSession) -> ReleaseOut:
    return ReleaseOut.model_validate(release_service.register_manual_release(db, principal, body))
