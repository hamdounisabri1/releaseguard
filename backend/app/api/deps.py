"""Shared FastAPI dependencies."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    """One session per request. Services own the transaction (they commit); anything left
    uncommitted is rolled back when the session closes.
    """
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
