"""Auth request and response bodies."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import Role
from app.services.auth_service import CurrentUser


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    # Capped so a huge body can't make argon2 hash megabytes.
    password: str = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class MeResponse(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
    role: Role

    @classmethod
    def build(cls, current: CurrentUser) -> "MeResponse":
        return cls(
            user=UserOut.model_validate(current.user),
            workspace=WorkspaceOut.model_validate(current.workspace),
            role=current.role,
        )
