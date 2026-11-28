"""Releases, always scoped to one workspace."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Release


def add(db: Session, workspace_id: uuid.UUID, release: Release) -> Release:
    if release.workspace_id != workspace_id:
        raise ValueError("release belongs to another workspace")
    db.add(release)
    db.flush()
    return release


def get(db: Session, workspace_id: uuid.UUID, release_id: uuid.UUID) -> Release | None:
    return db.scalar(
        select(Release).where(Release.workspace_id == workspace_id, Release.id == release_id)
    )


def get_by_version(
    db: Session, workspace_id: uuid.UUID, application_id: uuid.UUID, version: str
) -> Release | None:
    return db.scalar(
        select(Release).where(
            Release.workspace_id == workspace_id,
            Release.application_id == application_id,
            Release.version == version,
        )
    )
