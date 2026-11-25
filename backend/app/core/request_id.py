"""Request-ID middleware: every request gets an id, bound to its log lines and echoed back."""

import re
import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
# A caller-supplied id is reused only if it is short and plain, so it can't inject into logs.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

logger = get_logger("app.request")


def current_request_id() -> str | None:
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None


class RequestIdMiddleware:
    """Pure ASGI. Binds ``request_id`` for the request's log lines (contextvars also reach sync
    routes in the threadpool), adds ``X-Request-ID`` to the response and logs one access line.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
        valid = incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming)
        request_id = incoming if valid and incoming else uuid.uuid4().hex
        # Each request runs in its own task with its own context copy, so binding here never
        # leaks into another request. Not cleared on the way out: the app's 500 handler logs
        # after this middleware has returned and still needs the id.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request",
                method=scope["method"],
                path=scope["path"],  # never the query string
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
