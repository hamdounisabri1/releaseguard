"""The GitHub App installation linked to a workspace, and idempotent webhook intake."""

import uuid
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, check_in, sql_values
from app.models._columns import CreatedAt, Timestamp, UuidPk
from app.models.enums import (
    LINKED_INTEGRATION_STATUSES,
    IntegrationProvider,
    IntegrationStatus,
)

# A linked (pending or active) installation belongs to exactly one workspace, and a workspace
# links at most one per provider. Disconnected or invalid rows stay as history.
INSTALLATION_LINKED = "uq_integrations_linked_installation_id"
WORKSPACE_PROVIDER_LINKED = "uq_integrations_linked_workspace_provider"
_LINKED = text(f"status IN ({sql_values(LINKED_INTEGRATION_STATUSES)})")


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (
        check_in("provider", IntegrationProvider),
        check_in("status", IntegrationStatus),
        CheckConstraint("installation_id > 0", name="installation_id"),
        Index(INSTALLATION_LINKED, "installation_id", unique=True, postgresql_where=_LINKED),
        Index(
            WORKSPACE_PROVIDER_LINKED,
            "workspace_id",
            "provider",
            unique=True,
            postgresql_where=_LINKED,
        ),
    )

    id: Mapped[UuidPk]
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    provider: Mapped[str] = mapped_column(
        String(20), server_default=IntegrationProvider.GITHUB.value
    )
    installation_id: Mapped[int] = mapped_column(BigInteger)
    # Filled by the worker once GitHub confirms the installation.
    account_login: Mapped[str | None] = mapped_column(String(100))
    permissions_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(20), server_default=IntegrationStatus.PENDING.value)
    created_at: Mapped[CreatedAt]
    connected_at: Mapped[Timestamp | None]
    disconnected_at: Mapped[Timestamp | None]


class WebhookDelivery(Base):
    """One received GitHub delivery. The primary key de-duplicates ``X-GitHub-Delivery``.

    Not a tenant table: deliveries are recorded before they are matched to a workspace.
    """

    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event: Mapped[str] = mapped_column(String(50))
    received_at: Mapped[CreatedAt]
    processed_at: Mapped[Timestamp | None]
    outcome: Mapped[str | None] = mapped_column(String(50))
