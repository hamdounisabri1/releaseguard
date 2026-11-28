"""The lookup behind ``POST /releases/ci``: which application a verified OIDC token is for.

Not scoped to one workspace: the caller is a CI workflow with no session, so its workspace is
only known once its token's ``repository_id`` names an application. ``tests/test_scoping.py``
lists the exemption. Nothing else belongs here.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application
from app.models.enums import ApplicationStatus


def find_active_applications_by_repository_id(
    db: Session, repository_id: int
) -> Sequence[Application]:
    """Active applications bound to a GitHub repository id, in every workspace (at most one per
    workspace, by index). Two or more means the token is ambiguous.
    """
    return db.scalars(
        select(Application)
        .where(
            Application.repository_id == repository_id,
            Application.status == ApplicationStatus.ACTIVE.value,
        )
        .limit(2)
    ).all()
