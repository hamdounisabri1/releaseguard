"""Job kinds and their payloads, shared by the API (which enqueues) and the worker (which runs).

Kinds aren't a CHECK constraint on purpose: a new kind needs a handler, not a migration. A
worker claims only the kinds it has handlers for, so a job waits until a worker that knows it
runs.
"""

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class JobKind(StrEnum):
    VERIFY_GITHUB_INSTALLATION = "github.verify_installation"


class JobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VerifyInstallationPayload(JobPayload):
    integration_id: uuid.UUID
