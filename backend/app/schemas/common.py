"""Shared response shapes."""

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    """One page of a list. ``page`` starts at 1."""

    items: list[T]
    total: int = Field(description="Matching items across all pages.")
    page: int
    page_size: int
