"""Origin-check CSRF middleware (ADR-0007): unsafe methods need an allowed Origin or Referer."""

import pytest
from httpx import AsyncClient

from app.core.security import normalize_origin
from tests.conftest import build_app, client_for

UNSAFE = ["POST", "PUT", "PATCH", "DELETE"]
ECHO = "/api/v1/_test/echo"


def _assert_csrf_rejected(response_status: int, body: dict[str, object]) -> None:
    assert response_status == 403
    assert body == {
        "error": {
            "code": "csrf_origin_mismatch",
            "message": "The request origin is not allowed.",
            "details": {},
        }
    }


# --- Failure paths -------------------------------------------------------------------------


@pytest.mark.parametrize("method", UNSAFE)
@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({"Origin": "https://evil.example"}, id="foreign-origin"),
        pytest.param({}, id="no-origin-no-referer"),
        pytest.param({"Origin": "null"}, id="opaque-origin"),
        pytest.param({"Origin": ""}, id="empty-origin"),
        pytest.param({"Referer": "https://evil.example/page"}, id="foreign-referer"),
        pytest.param({"Origin": "http://testserver.evil.example"}, id="suffix-lookalike"),
        pytest.param({"Origin": "http://evil.example#testserver"}, id="fragment-trick"),
        pytest.param({"Origin": "http://testserver@evil.example"}, id="userinfo-trick"),
        pytest.param({"Origin": "http://testserver:8080"}, id="other-port"),
        pytest.param({"Origin": "https://testserver"}, id="other-scheme"),
        pytest.param({"Origin": "http://testserver/path"}, id="origin-with-path"),
        # A foreign Origin wins over a matching Referer.
        pytest.param(
            {"Origin": "https://evil.example", "Referer": "http://testserver/"},
            id="foreign-origin-good-referer",
        ),
    ],
)
async def test_unsafe_request_without_allowed_origin_is_rejected(
    client: AsyncClient, method: str, headers: dict[str, str]
) -> None:
    response = await client.request(method, ECHO, headers=headers)

    _assert_csrf_rejected(response.status_code, response.json())


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("PUT", "/api/v1/github/webhooks", id="exempt-path-other-method"),
        pytest.param("POST", "/api/v1/github/webhooks/extra", id="exempt-prefix"),
        pytest.param("POST", "/api/v1/github/webhooks/", id="exempt-trailing-slash"),
        pytest.param("POST", "/api/v1/releases/ci/", id="ci-trailing-slash"),
        pytest.param("POST", "/api/v1/does-not-exist", id="unknown-route"),
    ],
)
async def test_exemption_is_exact_method_and_path(
    client: AsyncClient, method: str, path: str
) -> None:
    response = await client.request(method, path, headers={"Origin": "https://evil.example"})

    _assert_csrf_rejected(response.status_code, response.json())


async def test_cors_origin_is_refused_outside_local() -> None:
    app = build_app(
        env="production",
        site_origin="https://rg.example.com",
        cors_origins=["http://localhost:3000"],
    )
    async with client_for(app) as client:
        response = await client.post(ECHO, headers={"Origin": "http://localhost:3000"})

    _assert_csrf_rejected(response.status_code, response.json())


# --- Allowed requests ----------------------------------------------------------------------


@pytest.mark.parametrize("method", UNSAFE)
@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({"Origin": "http://testserver"}, id="origin"),
        pytest.param({"Origin": "HTTP://TestServer:80"}, id="origin-normalized"),
        pytest.param({"Referer": "http://testserver/applications?x=1"}, id="referer-fallback"),
    ],
)
async def test_unsafe_request_from_site_origin_is_allowed(
    client: AsyncClient, method: str, headers: dict[str, str]
) -> None:
    response = await client.request(method, ECHO, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_safe_methods_need_no_origin(client: AsyncClient, method: str) -> None:
    response = await client.request(method, ECHO)

    assert response.status_code == 200


async def test_options_is_not_checked(client: AsyncClient) -> None:
    response = await client.options(ECHO, headers={"Origin": "https://evil.example"})

    assert response.status_code == 405  # no route for OPTIONS, but not a CSRF rejection
    assert response.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.parametrize("path", ["/api/v1/github/webhooks", "/api/v1/releases/ci"])
async def test_cookieless_endpoints_are_exempt(client: AsyncClient, path: str) -> None:
    response = await client.post(path, headers={"Origin": "https://evil.example"})
    no_origin = await client.post(path)

    assert response.status_code == 200
    assert no_origin.status_code == 200


async def test_cors_origin_is_allowed_in_local() -> None:
    app = build_app(
        env="local", site_origin="http://localhost:8000", cors_origins=["http://localhost:3000"]
    )
    async with client_for(app) as client:
        response = await client.post(ECHO, headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


# --- normalize_origin ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://example.com", "http://example.com"),
        ("HTTPS://Example.COM:443", "https://example.com"),
        ("http://example.com:8080/", "http://example.com:8080"),
        ("http://[::1]:3000", "http://[::1]:3000"),
        ("http://127.0.0.1", "http://127.0.0.1"),
        ("null", None),
        ("", None),
        (" http://example.com", None),
        ("http://exa mple.com", None),
        ("javascript://example.com", None),
        ("file:///etc/passwd", None),
        ("http://", None),
        ("http://example.com:notaport", None),
        ("http://user@example.com", None),
        ("http://example.com/path", None),
    ],
)
def test_normalize_origin(value: str, expected: str | None) -> None:
    assert normalize_origin(value) == expected


def test_normalize_origin_with_path_for_referer() -> None:
    assert normalize_origin("https://Example.com/a/b?c=d#e", allow_path=True) == (
        "https://example.com"
    )
