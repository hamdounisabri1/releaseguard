"""Request and response bodies for ``/releases``.

Every field that ends up in a deploy (the digest above all) is checked against a strict pattern;
validators never echo the submitted value (backend.md).
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.enums import ReleaseSource
from app.models.releases import DIGEST_PATTERN

Version = Annotated[
    str,
    Field(
        pattern=r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,99}$",
        description="Release version, e.g. `1.4.0` or `2026.11.28-3`.",
    ),
]
CommitSha = Annotated[
    str,
    Field(pattern=r"^[0-9a-fA-F]{40}$", description="Full 40-character commit SHA."),
    AfterValidator(str.lower),
]
Branch = Annotated[str, Field(pattern=r"^[^\x00-\x1f\x7f]{1,255}$")]
# A registry path without tag or digest, e.g. `ghcr.io/octo-org/taskflow`.
ImageRepository = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9]+([._-][a-z0-9]+)*(:[0-9]{1,5})?(/[a-z0-9]+([._-][a-z0-9]+)*)+$",
        max_length=255,
    ),
]
ImageTag = Annotated[str, Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")]
ImageDigest = Annotated[
    str,
    Field(
        pattern=DIGEST_PATTERN,
        description="The immutable image digest, `sha256:` plus 64 lowercase hex characters. "
        "Deployments always pull by this digest, never by tag.",
    ),
]


class _ReleaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Version
    commit_sha: CommitSha
    branch: Branch | None = None
    image_repository: ImageRepository
    image_tag: ImageTag | None = None
    image_digest: ImageDigest


class ReleaseCiCreate(_ReleaseBody):
    """Sent by the application's CI workflow with its OIDC token (ADR-0006)."""

    workflow_run_id: int = Field(gt=0, description="Must equal the token's `run_id` claim.")


class ReleaseCreate(_ReleaseBody):
    """Manual registration (Admin/Developer), the fallback when CI can't register."""

    application_id: uuid.UUID
    release_notes: str | None = Field(default=None, max_length=10_000)


class ReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    version: str
    commit_sha: str
    branch: str | None
    image_repository: str
    image_tag: str | None
    image_digest: str
    source: ReleaseSource
    workflow_run_id: int | None
    workflow_url: str | None = Field(description="The CI run that built it (CI releases only).")
    created_by: uuid.UUID | None = Field(description="The user, for manual releases.")
    release_notes: str | None
    created_at: datetime
