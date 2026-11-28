"""Declarative base and the constraint naming convention shared by models and migrations."""

from collections.abc import Iterable
from enum import StrEnum

from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy.orm import DeclarativeBase

# Stable, predictable constraint names, so later migrations can find (and drop) them.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def sql_values(values: Iterable[StrEnum]) -> str:
    """``'a', 'b'`` (sorted) for an ``IN (...)`` list, e.g. a partial index's ``WHERE``."""
    return ", ".join(f"'{value}'" for value in sorted(member.value for member in values))


def check_in(column: str, values: type[StrEnum]) -> CheckConstraint:
    """``CHECK (column IN (...))`` built from a Python enum, so the two never drift apart."""
    allowed = ", ".join(f"'{member.value}'" for member in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=column)
