"""Shared FastAPI dependencies: the database session, the authenticated caller, and the CI
caller's verified OIDC claims.
"""

from collections.abc import Awaitable, Callable, Iterator
from typing import Annotated

import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.oidc import GitHubOidcClaims, InvalidOidcTokenError, OidcVerifier
from app.core.permissions import Capability, Role, roles_with
from app.services import auth_service
from app.services.auth_service import SESSION_COOKIE, Principal


def get_db(request: Request) -> Iterator[Session]:
    """One session per request. Services own the transaction (they commit); anything left
    uncommitted is rolled back when the session closes.
    """
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]


def _resolve_principal(request: Request, db: DbSession) -> Principal:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UnauthorizedError()
    return auth_service.resolve_session(db, token)


async def get_principal(
    principal: Annotated[Principal, Depends(_resolve_principal)],
) -> Principal:
    """The authenticated caller, or 401.

    ``async`` on purpose: it runs in the request's own context, so the ids bound here reach every
    later log line of the request (sync dependencies run in a copied context in the threadpool).
    """
    structlog.contextvars.bind_contextvars(
        user_id=str(principal.user_id), workspace_id=str(principal.workspace_id)
    )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_role(*roles: Role) -> Callable[[Principal], Awaitable[Principal]]:
    """Dependency: the caller must hold one of ``roles`` in their workspace, else 403."""
    allowed = frozenset(roles)

    async def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.role not in allowed:
            raise ForbiddenError()
        return principal

    return dependency


def require_capability(capability: Capability) -> Callable[[Principal], Awaitable[Principal]]:
    """Dependency: the caller's role must hold ``capability`` (guide §3.1 matrix), else 403.

    Prefer this over ``require_role``: the matrix stays the single source of truth.
    """
    return require_role(*roles_with(capability))


_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="GitHubOidc",
    description="A GitHub Actions OIDC token (audience `GITHUB_OIDC_AUDIENCE`).",
)


def get_oidc_verifier(request: Request) -> OidcVerifier:
    verifier: OidcVerifier = request.app.state.oidc_verifier
    return verifier


def _ci_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[OidcVerifier, Depends(get_oidc_verifier)],
) -> GitHubOidcClaims:
    """Plain ``def``: the first verification may fetch GitHub's JWKS (blocking)."""
    if credentials is None:
        raise InvalidOidcTokenError()
    return verifier.verify(credentials.credentials)


async def get_ci_claims(
    claims: Annotated[GitHubOidcClaims, Depends(_ci_claims)],
) -> GitHubOidcClaims:
    """The CI caller's verified claims, or 401. Bound to the log context like ``get_principal``."""
    structlog.contextvars.bind_contextvars(
        repository_id=claims.repository_id, workflow_run_id=claims.run_id
    )
    return claims


CiClaims = Annotated[GitHubOidcClaims, Depends(get_ci_claims)]
