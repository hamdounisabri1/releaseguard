"""Shared FastAPI dependencies: the database session and the authenticated caller."""

from collections.abc import Iterator
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
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
