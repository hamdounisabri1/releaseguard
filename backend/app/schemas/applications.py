"""Application request and response bodies."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ApplicationStatus

# GitHub's own limits: owner 1 to 39 chars (letters, digits, hyphens, not leading); repository up
# to 100 chars of letters, digits, '.', '_' and '-'.
RepositoryOwner = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")]
# (pydantic-core's regex engine has no lookaheads, so the extra rules are validators; their
# messages never echo the input.)


def _not_dot_path(value: str) -> str:
    if value in {".", ".."}:
        raise ValueError("must not be '.' or '..'")
    return value


def _no_double_dot(value: str) -> str:
    if ".." in value:
        raise ValueError("must not contain '..'")
    return value


RepositoryName = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9._-]{1,100}$", examples=["taskflow"]),
    AfterValidator(_not_dot_path),
]
# A git branch name without whitespace or the characters git refuses, not starting with '-'.
BranchName = Annotated[
    str,
    Field(min_length=1, max_length=255, pattern=r"^[^\s~^:?*\[\\-][^\s~^:?*\[\\]*$"),
    AfterValidator(_no_double_dot),
]
WorkflowPath = Annotated[
    str,
    Field(max_length=255, pattern=r"^\.github/workflows/[A-Za-z0-9._-]+\.ya?ml$"),
]
ApplicationName = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=500)]
RepositoryId = Annotated[int, Field(gt=0, description="GitHub's numeric repository id.")]


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: ApplicationName
    description: Description = ""
    repository_owner: RepositoryOwner
    repository_name: RepositoryName
    repository_id: RepositoryId | None = None
    default_branch: BranchName = "main"
    ci_workflow_path: WorkflowPath = ".github/workflows/ci.yml"
    deploy_workflow_path: WorkflowPath = ".github/workflows/deploy.yml"


class ApplicationUpdate(BaseModel):
    """Only the fields sent are changed. ``repository_id`` may be set to null; nothing else."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: ApplicationName | None = None
    description: Description | None = None
    repository_owner: RepositoryOwner | None = None
    repository_name: RepositoryName | None = None
    repository_id: RepositoryId | None = None
    default_branch: BranchName | None = None
    ci_workflow_path: WorkflowPath | None = None
    deploy_workflow_path: WorkflowPath | None = None

    @model_validator(mode="after")
    def _no_null_for_required_fields(self) -> Self:
        nulls = [
            name
            for name in self.model_fields_set
            if name != "repository_id" and getattr(self, name) is None
        ]
        if nulls:
            raise ValueError("only repository_id can be set to null")
        return self


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    repository_owner: str
    repository_name: str
    repository_id: int | None
    default_branch: str
    ci_workflow_path: str
    deploy_workflow_path: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
