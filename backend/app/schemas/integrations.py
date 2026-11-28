"""Request and response bodies for ``/integrations``."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IntegrationProvider, IntegrationStatus

# GitHub ids are positive 64-bit integers.
_MAX_BIGINT = 2**63 - 1


class GitHubInstallCallback(BaseModel):
    """What GitHub's Setup URL redirect carries (``?installation_id=…&setup_action=…``); the
    frontend posts it here with the Admin's session.
    """

    model_config = ConfigDict(extra="forbid")

    installation_id: int = Field(gt=0, le=_MAX_BIGINT)
    setup_action: Literal["install", "update"] = "install"


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: IntegrationProvider
    installation_id: int
    status: IntegrationStatus = Field(
        description="`pending` until the worker confirms the installation with GitHub; "
        "`active` once it does (only then are dispatches allowed); `invalid` when GitHub "
        "doesn't know it; `disconnected` after an Admin removes it."
    )
    account_login: str | None = Field(description="The GitHub account the App is installed on.")
    permissions_summary: dict[str, Any]
    created_at: datetime
    connected_at: datetime | None
    disconnected_at: datetime | None
