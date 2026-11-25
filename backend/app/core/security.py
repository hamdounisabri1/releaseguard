"""Request security: the Origin-check CSRF defense (ADR-0007).

Password hashing and server-side sessions are added here in SCRUM-20.
"""

from collections.abc import Iterable
from http import HTTPStatus
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

# Default-deny: every method except these read-only ones needs an allowed origin, including
# POST/PUT/PATCH/DELETE and anything non-standard.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Endpoints that don't use the session cookie, so CSRF doesn't apply: GitHub webhooks are
# HMAC-verified and CI release registration uses a GitHub OIDC bearer token. Exact method and
# path only; never a prefix.
CSRF_EXEMPT: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/v1/github/webhooks"),
        ("POST", "/api/v1/releases/ci"),
    }
)

_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_origin(value: str, *, allow_path: bool = False) -> str | None:
    """Return ``scheme://host[:port]`` in canonical form, or ``None`` if ``value`` isn't one.

    Lowercases scheme and host and drops the scheme's default port. Rejects ``null`` (opaque
    origins), non-http(s) schemes, credentials, whitespace and malformed ports. With
    ``allow_path`` (for ``Referer``), a path, query or fragment is accepted and discarded.
    """
    if not value or value != value.strip() or any(ch.isspace() or ord(ch) < 0x20 for ch in value):
        return None
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = parts.hostname
    if scheme not in _DEFAULT_PORTS or not host or parts.username or parts.password:
        return None
    if "@" in parts.netloc:
        return None
    if not allow_path and (parts.path not in ("", "/") or parts.query or parts.fragment):
        return None
    if ":" in host:  # IPv6 literal; hostname strips the brackets
        host = f"[{host}]"
    if port is None or port == _DEFAULT_PORTS[scheme]:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def request_origin(headers: Headers) -> str | None:
    """The normalized origin of a request: ``Origin``, or ``Referer`` when ``Origin`` is absent."""
    origin = headers.get("origin")
    if origin is not None:
        return normalize_origin(origin)
    referer = headers.get("referer")
    if referer is not None:
        return normalize_origin(referer, allow_path=True)
    return None


class OriginCheckMiddleware:
    """Reject unsafe requests whose ``Origin`` (or ``Referer``) isn't an allowed origin with 403.

    Pure ASGI, so it runs before routing and never buffers bodies. Safe methods, including
    ``OPTIONS`` preflights, pass through. Only ``http`` scopes are checked: a WebSocket route
    would need its own Origin check.
    """

    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._is_allowed(scope):
            await self.app(scope, receive, send)
            return
        response = error_response(
            HTTPStatus.FORBIDDEN,
            "csrf_origin_mismatch",
            "The request origin is not allowed.",
        )
        await response(scope, receive, send)

    def _is_allowed(self, scope: Scope) -> bool:
        method = scope["method"].upper()
        if method in SAFE_METHODS:
            return True
        if (method, scope["path"]) in CSRF_EXEMPT:
            return True
        origin = request_origin(Headers(scope=scope))
        return origin is not None and origin in self.allowed_origins
