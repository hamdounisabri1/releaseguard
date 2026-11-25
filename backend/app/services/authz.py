"""Authorization helpers for services: the second check behind the route dependencies, and the
404-for-another-workspace rule.
"""

from app.core.errors import ForbiddenError, NotFoundError
from app.core.permissions import Capability
from app.services.auth_service import Principal


def ensure_can(principal: Principal, capability: Capability) -> None:
    """403 when the caller's role lacks ``capability`` in their own workspace."""
    if not principal.can(capability):
        raise ForbiddenError()


def found[T](resource: T | None) -> T:
    """404 when a workspace-scoped lookup found nothing.

    Repositories filter by the caller's workspace, so a resource in another workspace comes back
    as ``None`` and gets the same 404 as one that doesn't exist (its existence is never confirmed).
    """
    if resource is None:
        raise NotFoundError()
    return resource
