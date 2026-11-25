"""Environment request and response bodies, and the environment policy (guide §4.4)."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EnvironmentType, HealthStatus


class EnvironmentPolicy(BaseModel):
    """Stored as JSONB in ``environments.policy``; frozen onto each deployment later (S3)."""

    model_config = ConfigDict(extra="forbid")

    auto_deploy_on_release: bool = Field(
        default=False, description="Create and dispatch a deployment when a release registers."
    )
    requires_approval: bool = Field(default=False, description="Reviewer gate.")
    min_approvals: int = Field(default=1, ge=1, le=5)
    approval_ttl_hours: int = Field(default=24, ge=1, le=168)
    require_comment: bool = False
    promote_from_environment_id: uuid.UUID | None = Field(
        default=None,
        description="Another environment of the same application where the release must "
        "already have a Succeeded deployment.",
    )
    rollback_requires_approval: bool = False


def _reject_nulls(model: BaseModel, nullable: frozenset[str] = frozenset()) -> None:
    """PATCH semantics: an omitted field is unchanged; an explicit null is an error unless the
    field is really nullable (otherwise it would 500 later or be silently ignored).
    """
    nulls = [
        name
        for name in model.model_fields_set
        if name not in nullable and getattr(model, name) is None
    ]
    if nulls:
        raise ValueError("fields can't be set to null: " + ", ".join(sorted(nulls)))


class EnvironmentPolicyUpdate(BaseModel):
    """Only the fields sent are changed. Only ``promote_from_environment_id`` may be null."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        _reject_nulls(self, frozenset({"promote_from_environment_id"}))
        return self

    auto_deploy_on_release: bool | None = None
    requires_approval: bool | None = None
    min_approvals: Annotated[int, Field(ge=1, le=5)] | None = None
    approval_ttl_hours: Annotated[int, Field(ge=1, le=168)] | None = None
    require_comment: bool | None = None
    promote_from_environment_id: uuid.UUID | None = None
    rollback_requires_approval: bool | None = None


class EnvironmentUpdate(BaseModel):
    """Health-check timing and policy. The health URL is set in Sprint 4, behind the SSRF guard,
    so ``health_url`` is not accepted here yet.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        _reject_nulls(self)
        return self

    expected_status: Annotated[int, Field(ge=100, le=599)] | None = None
    check_interval_seconds: Annotated[int, Field(ge=10, le=86_400)] | None = None
    timeout_ms: Annotated[int, Field(ge=100, le=60_000)] | None = None
    failure_threshold: Annotated[int, Field(ge=1, le=20)] | None = None
    verify_successes: Annotated[int, Field(ge=1, le=20)] | None = None
    verify_timeout_seconds: Annotated[int, Field(ge=10, le=3_600)] | None = None
    policy: EnvironmentPolicyUpdate | None = None


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    environment_type: EnvironmentType
    health_url: str | None
    expected_status: int
    check_interval_seconds: int
    timeout_ms: int
    failure_threshold: int
    verify_successes: int
    verify_timeout_seconds: int
    policy: EnvironmentPolicy
    current_deployment_id: uuid.UUID | None
    health_status: HealthStatus
    consecutive_failures: int
    last_checked_at: datetime | None
    next_check_at: datetime | None
    created_at: datetime
