"""Applications and their environments."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in
from app.models._columns import CreatedAt, Timestamp, UuidPk
from app.models.enums import ApplicationStatus, EnvironmentType, HealthStatus


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        # Target of the composite FKs that stop child rows pointing across workspaces.
        UniqueConstraint("id", "workspace_id"),
        # NULLs never collide, so apps without a known repository id are allowed.
        UniqueConstraint("workspace_id", "repository_id"),
        check_in("status", ApplicationStatus),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), server_default="")
    repository_owner: Mapped[str] = mapped_column(String(39))
    repository_name: Mapped[str] = mapped_column(String(100))
    # GitHub's numeric repository id; binds CI OIDC tokens to this app (ADR-0006).
    repository_id: Mapped[int | None] = mapped_column(BigInteger)
    default_branch: Mapped[str] = mapped_column(String(255), server_default="main")
    ci_workflow_path: Mapped[str] = mapped_column(
        String(255), server_default=".github/workflows/ci.yml"
    )
    deploy_workflow_path: Mapped[str] = mapped_column(
        String(255), server_default=".github/workflows/deploy.yml"
    )
    status: Mapped[str] = mapped_column(String(20), server_default=ApplicationStatus.ACTIVE.value)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[Timestamp | None]


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "workspace_id"],
            ["applications.id", "applications.workspace_id"],
        ),
        UniqueConstraint("id", "workspace_id"),
        UniqueConstraint("application_id", "environment_type"),
        check_in("environment_type", EnvironmentType),
        check_in("health_status", HealthStatus),
        CheckConstraint("expected_status BETWEEN 100 AND 599", name="expected_status"),
        CheckConstraint("check_interval_seconds >= 10", name="check_interval_seconds"),
        CheckConstraint("timeout_ms BETWEEN 100 AND 60000", name="timeout_ms"),
        CheckConstraint("failure_threshold >= 1", name="failure_threshold"),
        CheckConstraint("verify_successes >= 1", name="verify_successes"),
        CheckConstraint("verify_timeout_seconds >= 10", name="verify_timeout_seconds"),
        CheckConstraint("consecutive_failures >= 0", name="consecutive_failures"),
        Index("ix_environments_next_check_at", "next_check_at"),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    application_id: Mapped[uuid.UUID]
    environment_type: Mapped[str] = mapped_column(String(20))
    # Health check configuration (S4 adds editing the URL, behind the SSRF guard).
    health_url: Mapped[str | None] = mapped_column(String(2048))
    expected_status: Mapped[int] = mapped_column(server_default=text("200"))
    check_interval_seconds: Mapped[int] = mapped_column(server_default=text("60"))
    timeout_ms: Mapped[int] = mapped_column(server_default=text("5000"))
    failure_threshold: Mapped[int] = mapped_column(server_default=text("3"))
    verify_successes: Mapped[int] = mapped_column(server_default=text("3"))
    verify_timeout_seconds: Mapped[int] = mapped_column(server_default=text("300"))
    # Environment policy (guide §4.4); its shape is ``app.schemas.environments.EnvironmentPolicy``.
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # The FK to deployments arrives with that table's migration (the two reference each other).
    current_deployment_id: Mapped[uuid.UUID | None]
    health_status: Mapped[str] = mapped_column(
        String(20), server_default=HealthStatus.UNKNOWN.value
    )
    consecutive_failures: Mapped[int] = mapped_column(server_default=text("0"))
    last_checked_at: Mapped[Timestamp | None]
    next_check_at: Mapped[Timestamp | None]
    created_at: Mapped[CreatedAt]
