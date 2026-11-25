"""/healthz, /readyz, the request-ID middleware and structlog JSON logging."""

import io
import json
import logging
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.logging import REDACTED, configure_logging, get_logger, redact
from tests.conftest import build_app, client_for


def _log_lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


@pytest.fixture
def log_stream(app: FastAPI) -> io.StringIO:
    """Capture the JSON log output (after ``app`` has configured logging)."""
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)
    return stream


async def test_healthz_is_public_and_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_is_ok_when_the_database_is_reachable(client: AsyncClient) -> None:
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_returns_503_when_the_database_is_unreachable() -> None:
    app = build_app(database_url="postgresql+psycopg://nobody:secretpw@127.0.0.1:1/none")
    stream = io.StringIO()
    configure_logging("INFO", stream=stream)

    async with client_for(app) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    assert "secretpw" not in stream.getvalue()


async def test_every_response_gets_a_request_id_header(client: AsyncClient) -> None:
    ok = await client.get("/healthz")
    csrf_refused = await client.post("/api/v1/_test/echo")  # no Origin: 403 from the middleware
    crashed = await client.get("/api/v1/_test/boom")  # 500 from the app's error handler

    assert csrf_refused.status_code == 403
    assert crashed.status_code == 500
    ids = {r.headers.get("x-request-id") for r in (ok, csrf_refused, crashed)}
    assert None not in ids
    assert len(ids) == 3


async def test_a_plain_incoming_request_id_is_reused(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "abc-123.def_4"})

    assert response.headers["x-request-id"] == "abc-123.def_4"


@pytest.mark.parametrize("bad", ["has space", "x" * 65, "line\\nbreak", "<script>"])
async def test_an_unsafe_incoming_request_id_is_replaced(client: AsyncClient, bad: str) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": bad})

    assert response.headers["x-request-id"] != bad
    assert len(response.headers["x-request-id"]) == 32


async def test_log_lines_carry_the_request_id(client: AsyncClient, log_stream: io.StringIO) -> None:
    response = await client.get("/api/v1/_test/boom", headers={"X-Request-ID": "req-42"})

    assert response.headers["x-request-id"] == "req-42"
    lines = _log_lines(log_stream)
    error_lines = [line for line in lines if line["level"] == "error"]
    access_lines = [line for line in lines if line["event"] == "request"]
    assert error_lines and all(line["request_id"] == "req-42" for line in error_lines)
    assert access_lines == [
        {
            **access_lines[0],
            "request_id": "req-42",
            "method": "GET",
            "path": "/api/v1/_test/boom",
            "status": 500,
        }
    ]


async def test_access_log_never_contains_the_query_string(
    client: AsyncClient, log_stream: io.StringIO
) -> None:
    await client.get("/healthz?token=abc123secret")

    # The test client's own "HTTP Request: …" line is client-side; only check the server's.
    server_lines = [line for line in _log_lines(log_stream) if line["logger"] != "httpx"]
    assert server_lines
    assert "abc123secret" not in json.dumps(server_lines)


def test_sensitive_fields_are_redacted_from_log_lines(log_stream: io.StringIO) -> None:
    get_logger("test").info(
        "login attempt",
        email="admin@example.com",
        password="hunter2",  # noqa: S106 (checks that it's redacted)
        details={"session_token": "tok-1", "nested": [{"Authorization": "Bearer abc"}]},
    )
    logging.getLogger("stdlib").warning("plain stdlib line")

    output = log_stream.getvalue()
    for secret in ("hunter2", "tok-1", "Bearer abc"):
        assert secret not in output
    first, second = _log_lines(log_stream)
    assert first["password"] == REDACTED
    assert first["email"] == "admin@example.com"
    assert first["timestamp"].endswith("Z")
    assert second["event"] == "plain stdlib line"


def test_redact_handles_nested_structures() -> None:
    assert redact({"a": {"cookie": "c", "keep": 1}, "b": [{"api_key": "k"}]}) == {
        "a": {"cookie": REDACTED, "keep": 1},
        "b": [{"api_key": REDACTED}],
    }
