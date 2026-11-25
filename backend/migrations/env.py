"""Alembic environment: online migrations against DATABASE_URL, compared with app.models."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base

config = context.config

# Tests run migrations in-process and pass configure_logger=False, so Alembic's logging setup
# doesn't replace the app's.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (--sql) migrations are not supported; run against a database.")
run_migrations_online()
