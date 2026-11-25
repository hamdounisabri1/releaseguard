"""OpenAPI models for the standard error shape (see ``app.core.errors``)."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable code, e.g. `csrf_origin_mismatch`.")
    message: str = Field(description="Human-readable summary; safe to show to the user.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Extra context, e.g. `errors` for validation failures."
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Error responses any route may return; set app-wide in ``create_app``.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "Forbidden (role, or foreign `Origin`)."},
    422: {"model": ErrorResponse, "description": "Validation error."},
}
