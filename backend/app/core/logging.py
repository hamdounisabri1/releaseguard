"""structlog JSON logging for the app and every stdlib logger (uvicorn, SQLAlchemy, Alembic).

Each line is one JSON object with ``timestamp`` (UTC), ``level``, ``logger``, ``event``, the
context bound for the current request (``request_id``, and later ``workspace_id``, ``user_id``,
…) and the call's own fields. Values under sensitive keys are redacted before rendering.
"""

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any, TextIO

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

REDACTED = "[REDACTED]"
# Matched against field names anywhere in the event, nested dicts included.
SENSITIVE_KEY = re.compile(
    r"pass(word|wd)?|secret|token|cookie|authorization|api[_-]?key|private[_-]?key|credential",
    re.IGNORECASE,
)


def redact(value: Any) -> Any:
    """Return ``value`` with every sensitive key's value replaced, recursively."""
    if isinstance(value, Mapping):
        return {
            key: REDACTED if SENSITIVE_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


def _redact_processor(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    redacted: EventDict = redact(event_dict)
    return redacted


_SHARED_PROCESSORS: list[Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    _redact_processor,
]


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Route structlog and the stdlib root logger through one JSON formatter on ``stream``.

    Called by ``create_app``; safe to call again (it replaces the handler).
    """
    structlog.configure(
        processors=[*_SHARED_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    # The request-ID middleware writes one access line per request (without the query string,
    # which may carry tokens), so uvicorn's own access log is off.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger
