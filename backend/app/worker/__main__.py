"""Worker entrypoint: ``python -m app.worker``. Stops cleanly on SIGINT/SIGTERM (Ctrl+C on
Windows), finishing the job in hand; a job cut off by a hard kill is re-run after its lease.
"""

import asyncio
import signal
from contextlib import suppress

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_engine, create_session_factory
from app.worker.registry import build_registry
from app.worker.runner import Worker, WorkerConfig
from app.worker.sweeps import default_sweeps


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_url)
    worker = Worker(
        session=create_session_factory(engine),
        jobs=build_registry(settings),
        sweeps=default_sweeps(),
        config=WorkerConfig.from_settings(settings),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        # Not available on Windows' event loop; Ctrl+C then raises KeyboardInterrupt instead.
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop.set)
    try:
        await worker.run_forever(stop)
    finally:
        engine.dispose()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
