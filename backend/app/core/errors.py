"""The API's single error shape, ``{"error": {"code", "message", "details"}}``, and its handlers.

Services raise ``AppError`` subclasses; routes never build error responses by hand.
"""

import logging
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """A domain or request error with a stable machine-readable ``code``."""

    status_code: int = HTTPStatus.BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "unauthorized"
    message = "Authentication is required."


class ForbiddenError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden"
    message = "You don't have permission to do this."


class NotFoundError(AppError):
    """Also used for another workspace's resources, so their existence is never confirmed."""

    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state."


class UnprocessableError(AppError):
    """Well-formed input that breaks a domain rule (e.g. a policy pointing at the wrong place)."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "unprocessable"
    message = "The request breaks a domain rule."


class ServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "not_ready"
    message = "The service is not ready."


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=error_body(code, message, details), headers=headers
    )


def _code_for_status(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "http_error"


# Starlette types every handler as taking ``Exception``; each one narrows it and treats anything
# unexpected as an unhandled error.


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await _unhandled_error_handler(request, exc)
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return await _unhandled_error_handler(request, exc)
    try:
        default_message = HTTPStatus(exc.status_code).phrase
    except ValueError:
        default_message = "HTTP error"
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else default_message
    return error_response(
        exc.status_code,
        _code_for_status(exc.status_code),
        message,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await _unhandled_error_handler(request, exc)
    # Only location, message and type: never echo the submitted input (it may hold a password).
    errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "validation_error",
        "The request is invalid.",
        {"errors": errors},
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled error on %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    # Starlette sends this response from outside the user middleware, so the request-ID
    # middleware can't add its header here; add it from the log context instead.
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "internal_error",
        "An unexpected error occurred.",
        headers={"X-Request-ID": request_id} if isinstance(request_id, str) else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
