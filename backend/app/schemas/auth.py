"""Auth request and response bodies."""

import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.core.permissions import Role
from app.services.auth_service import CurrentUser

EMAIL_MAX_LENGTH = 254  # users.email and login_attempts.email


def _normalize_email(value: str) -> str:
    # Lowercasing can lengthen a string ("İ" → "i̇"), so the length is checked after it: a
    # longer key couldn't be stored in login_attempts (500 after argon2, never throttled).
    normalized = value.strip().lower()
    if not 3 <= len(normalized) <= EMAIL_MAX_LENGTH:
        raise ValueError(f"must be 3 to {EMAIL_MAX_LENGTH} characters")
    return normalized


class LoginRequest(BaseModel):
    """``email`` arrives trimmed and lowercased, the form it's stored and throttled in."""

    email: Annotated[str, Field(max_length=4 * EMAIL_MAX_LENGTH), AfterValidator(_normalize_email)]
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
