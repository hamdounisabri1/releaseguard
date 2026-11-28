"""Deployments (the aggregate, ADR-0003) and their append-only event timeline."""

import uuid
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in, sql_values
from app.models._columns import CreatedAt, Timestamp, UuidPk
from app.models.enums import (
    ACTIVE_STATUSES,
    DeploymentErrorCode,
    DeploymentStatus,
    EventSource,
    OperationType,
)

# The database's guarantee of one active deployment per environment (guide §7.3). A violation
# maps to 409 ``environment_busy``.
ONE_ACTIVE_PER_ENVIRONMENT = "deployments_one_active_per_env"


class Deployment(Base):
    """One attempt to put one release into one environment. Its approval state, frozen policy
    and rollback link live here. ``status`` changes only through ``deployment_service``.
    """

    __tablename__ = "deployments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["release_id", "workspace_id"], ["releases.id", "releases.workspace_id"]
        ),
        ForeignKeyConstraint(
            ["environment_id", "workspace_id"],
            ["environments.id", "environments.workspace_id"],
        ),
        ForeignKeyConstraint(
            ["base_deployment_id", "workspace_id"],
            ["deployments.id", "deployments.workspace_id"],
            name="fk_deployments_base_deployment_id_deployments",
        ),
        ForeignKeyConstraint(
            ["rollback_of_deployment_id", "workspace_id"],
            ["deployments.id", "deployments.workspace_id"],
            name="fk_deployments_rollback_of_deployment_id_deployments",
        ),
        UniqueConstraint("id", "workspace_id"),
        check_in("status", DeploymentStatus),
        check_in("operation_type", OperationType),
        CheckConstraint(
            f"error_code IS NULL OR error_code IN ({sql_values(DeploymentErrorCode)})",
            name="error_code",
        ),
        # A rollback always names the deployment it replaces; a deploy never does.
        CheckConstraint(
            "(operation_type = 'rollback') = (rollback_of_deployment_id IS NOT NULL)",
            name="rollback_of_deployment_id",
        ),
        Index(
            ONE_ACTIVE_PER_ENVIRONMENT,
            "environment_id",
            unique=True,
            postgresql_where=text(f"status IN ({sql_values(ACTIVE_STATUSES)})"),
        ),
        Index(
            "uq_deployments_workspace_id_idempotency_key",
            "workspace_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_deployments_environment_created", "environment_id", text("created_at DESC")),
        Index(
            "ix_deployments_workspace_status_created",
            "workspace_id",
            "status",
            text("created_at DESC"),
        ),
        Index("ix_deployments_release_id", "release_id"),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    release_id: Mapped[uuid.UUID]
    environment_id: Mapped[uuid.UUID]
    operation_type: Mapped[str] = mapped_column(
        String(20), server_default=OperationType.DEPLOY.value
    )
    status: Mapped[str] = mapped_column(String(30))
    # NULL when the policy started it (auto-deploy on release).
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    approval_expires_at: Mapped[Timestamp | None]
    # The environment's current deployment when the request was made (stale-approval check).
    base_deployment_id: Mapped[uuid.UUID | None]
    rollback_of_deployment_id: Mapped[uuid.UUID | None]
    reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    workflow_run_id: Mapped[int | None] = mapped_column(BigInteger)
    workflow_url: Mapped[str | None] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(30))
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
    dispatched_at: Mapped[Timestamp | None]
    finished_at: Mapped[Timestamp | None]


class DeploymentEvent(Base):
    """One status change of a deployment. Append-only: a trigger refuses UPDATE, DELETE and
    TRUNCATE (as on ``audit_logs``).
    """

    __tablename__ = "deployment_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["deployment_id", "workspace_id"],
            ["deployments.id", "deployments.workspace_id"],
        ),
        check_in("source", EventSource),
        # NULL from_status: the creation event.
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({sql_values(DeploymentStatus)})",
            name="from_status",
        ),
        check_in("to_status", DeploymentStatus),
        Index("ix_deployment_events_deployment_created", "deployment_id", "created_at"),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    deployment_id: Mapped[uuid.UUID]
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[CreatedAt]
