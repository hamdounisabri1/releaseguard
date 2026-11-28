"""Releases: immutable builds, identified by their image digest (ADR-0002)."""

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in
from app.models._columns import CreatedAt, UuidPk
from app.models.enums import ReleaseSource

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
CI_RUN_REGISTERED = "uq_releases_ci_workflow_run_id"


class Release(Base):
    """One build of an application. Never changed after registration (release notes aside)."""

    __tablename__ = "releases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "workspace_id"],
            ["applications.id", "applications.workspace_id"],
        ),
        UniqueConstraint("id", "workspace_id"),
        # Also the CI idempotency key: the same version with the same digest is a replay.
        UniqueConstraint("application_id", "version"),
        check_in("source", ReleaseSource),
        CheckConstraint(f"image_digest ~ '{DIGEST_PATTERN}'", name="image_digest"),
        CheckConstraint("commit_sha ~ '^[0-9a-f]{40}$'", name="commit_sha"),
        # One release per CI run: a leaked OIDC token (valid for its run) can't register more.
        Index(
            CI_RUN_REGISTERED,
            "application_id",
            "workflow_run_id",
            unique=True,
            postgresql_where=text("source = 'ci'"),
        ),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    application_id: Mapped[uuid.UUID]
    version: Mapped[str] = mapped_column(String(100))
    commit_sha: Mapped[str] = mapped_column(String(40))
    branch: Mapped[str | None] = mapped_column(String(255))
    image_repository: Mapped[str] = mapped_column(String(255))
    image_tag: Mapped[str | None] = mapped_column(String(128))
    image_digest: Mapped[str] = mapped_column(String(71))
    source: Mapped[str] = mapped_column(String(20))
    workflow_run_id: Mapped[int | None] = mapped_column(BigInteger)
    # Link to the CI run, built from the OIDC claims (never from request text).
    workflow_url: Mapped[str | None] = mapped_column(String(500))
    # NULL for CI registrations (the system actor); the user for manual ones.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    release_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
