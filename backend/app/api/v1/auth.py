"""``/auth``: login, logout and the current user (server-side sessions, ADR-0007)."""

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentPrincipal, DbSession
from app.schemas.auth import LoginRequest, MeResponse
from app.schemas.errors import UNAUTHORIZED_RESPONSE, ErrorResponse
from app.services import auth_service
from app.services.auth_service import ABSOLUTE_LIFETIME, SESSION_COOKIE

router = APIRouter(prefix="/auth", tags=["auth"], responses=UNAUTHORIZED_RESPONSE)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(ABSOLUTE_LIFETIME.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


@router.post(
    "/login",
    summary="Sign in with email and password",
    description="Sets the `rg_session` cookie (HttpOnly, Secure, SameSite=Lax). Wrong password, "
    "unknown email and disabled account all return the same 401 `invalid_credentials`. After too "
    "many failures for one (email, client IP), or from one client IP, within the throttle window "
    "it returns 429 `too_many_attempts` with `Retry-After`, the same for known and unknown emails.",
    responses={
        429: {
            "model": ErrorResponse,
            "description": "Too many failed attempts; retry after `Retry-After` seconds.",
            "headers": {
                "Retry-After": {
                    "description": "Seconds until a new attempt is allowed.",
                    "schema": {"type": "integer"},
                }
            },
        }
    },
)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> MeResponse:
    result = auth_service.login(
        db,
        body.email,
        body.password,
        # The socket peer, or the X-Forwarded-For client when the peer is a trusted proxy.
        client_ip=auth_service.client_key(request.client.host if request.client else None),
        throttle=auth_service.LoginThrottle.from_settings(request.app.state.settings),
        previous_token=request.cookies.get(SESSION_COOKIE),
    )
    _set_session_cookie(response, result.token)
    return MeResponse.build(result.current)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out: deletes the server-side session and clears the cookie",
)
def logout(request: Request, response: Response, db: DbSession) -> None:
    auth_service.logout(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


@router.get("/me", summary="The signed-in user, their workspace and role")
def me(principal: CurrentPrincipal, db: DbSession) -> MeResponse:
    return MeResponse.build(auth_service.current_user(db, principal))
