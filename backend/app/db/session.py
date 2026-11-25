"""Engine and session factory. ``create_app`` stores both on ``app.state``.

The API uses synchronous SQLAlchemy with psycopg 3: routes that touch the database are plain
``def`` functions, which FastAPI runs in its threadpool.
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

# Fail fast when the database is unreachable instead of hanging a request (or /readyz).
CONNECT_TIMEOUT_SECONDS = 3


def create_db_engine(database_url: str) -> Engine:
    """Create the engine. Nothing connects until the first query."""
    return create_engine(
        database_url,
        # Keep bound values (password hashes, token hashes, user input) out of exception text,
        # which the 500 handler logs.
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: services return ORM objects after committing; routes serialize them.
    return sessionmaker(engine, expire_on_commit=False)
