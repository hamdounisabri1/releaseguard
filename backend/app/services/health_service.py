"""Readiness of ReleaseGuard itself (not of the monitored applications)."""

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

logger = get_logger(__name__)


def database_is_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # The exception text can contain the connection URL; log only its type.
        logger.warning(
            "readiness check failed", reason="database_unreachable", error=type(exc).__name__
        )
        return False
    return True
