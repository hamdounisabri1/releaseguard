"""A local JWKS and token signer standing in for GitHub's OIDC provider (no network in tests)."""

import json
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK, PyJWKSet
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import PyJWKClientError

KID = "test-key"


@lru_cache(maxsize=2)
def _private_key(name: str) -> rsa.RSAPrivateKey:
    del name  # one key per name, generated once per run (RSA generation is slow)
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class LocalKeys:
    """Implements ``app.core.oidc.SigningKeys`` over one in-memory RSA key."""

    def __init__(self) -> None:
        self.private = _private_key("github")
        jwk = json.loads(RSAAlgorithm.to_jwk(self.private.public_key()))
        jwk.update(kid=KID, alg="RS256", use="sig")
        self.jwks = PyJWKSet.from_dict({"keys": [jwk]})

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        kid = jwt.get_unverified_header(token).get("kid")
        for key in self.jwks.keys:
            if key.key_id == kid:
                return key
        raise PyJWKClientError("Unable to find a signing key that matches the token")

    def sign(self, claims: dict[str, Any], *, kid: str = KID, other_key: bool = False) -> str:
        key = _private_key("attacker") if other_key else self.private
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})
