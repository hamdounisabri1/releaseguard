"""GitHub Actions OIDC token verification for ``POST /releases/ci`` (ADR-0006).

``OidcVerifier`` checks the signature against GitHub's JWKS (RS256 only), ``iss``, ``aud``
(``GITHUB_OIDC_AUDIENCE``), ``exp``/``iat``, and that the claims the binding needs are present.
Binding the claims to an application (repository id, workflow, SHA, run) is the release
service's job.

This is the one outbound call the API process makes: PyJWKClient fetches the key set over HTTPS
(5 s timeout), caches it for 10 minutes, and refetches at most every 30 s for an unknown key id.
"""

from typing import Any, Protocol

import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import ServiceUnavailableError, UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)

GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
GITHUB_OIDC_JWKS_URL = f"{GITHUB_OIDC_ISSUER}/.well-known/jwks"
ALGORITHMS = ["RS256"]
LEEWAY_SECONDS = 10


class InvalidOidcTokenError(UnauthorizedError):
    code = "invalid_oidc_token"
    message = "A valid GitHub Actions OIDC bearer token is required."

    def __init__(self) -> None:
        super().__init__(headers={"WWW-Authenticate": "Bearer"})


class OidcUnavailableError(ServiceUnavailableError):
    code = "oidc_unavailable"
    message = "GitHub's OIDC keys can't be fetched right now. Retry later."


class SigningKeys(Protocol):
    """Where verification keys come from: ``PyJWKClient`` in production, a local key set in
    tests (no network).
    """

    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


class GitHubOidcClaims(BaseModel):
    """The claims ReleaseGuard relies on. GitHub sends ids as strings; they are parsed here."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
    repository_id: int = Field(gt=0)
    workflow_ref: str = Field(min_length=1, max_length=500)
    sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    run_id: int = Field(gt=0)
    actor: str = Field(min_length=1, max_length=100)
    event_name: str | None = None


class OidcVerifier:
    def __init__(
        self, audience: str | None, keys: SigningKeys, *, issuer: str = GITHUB_OIDC_ISSUER
    ) -> None:
        self.audience = audience
        self.keys = keys
        self.issuer = issuer

    @classmethod
    def for_github(cls, audience: str | None) -> "OidcVerifier":
        keys = PyJWKClient(
            GITHUB_OIDC_JWKS_URL, cache_jwk_set=True, lifespan=600, timeout=5, cooldown_duration=30
        )
        return cls(audience, keys)

    def verify(self, token: str) -> GitHubOidcClaims:
        """The token's claims, or 401 ``invalid_oidc_token`` (503 when the JWKS is unreachable).
        Only the failure's class is logged, never the token.
        """
        if not self.audience:
            # Fail closed: without an expected audience any GitHub token would pass.
            logger.warning("oidc token refused", reason="GITHUB_OIDC_AUDIENCE is not set")
            raise InvalidOidcTokenError()
        try:
            key = self.keys.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError:
            logger.error("oidc jwks unreachable")
            raise OidcUnavailableError() from None
        except (PyJWKClientError, InvalidTokenError) as exc:
            logger.warning("oidc token refused", reason=type(exc).__name__)
            raise InvalidOidcTokenError() from None
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=ALGORITHMS,
                audience=self.audience,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except InvalidTokenError as exc:
            logger.warning("oidc token refused", reason=type(exc).__name__)
            raise InvalidOidcTokenError() from None
        try:
            return GitHubOidcClaims.model_validate(claims)
        except ValidationError:
            logger.warning("oidc token refused", reason="missing or malformed claims")
            raise InvalidOidcTokenError() from None
