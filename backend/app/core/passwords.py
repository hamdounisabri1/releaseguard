"""Password hashing with argon2id (argon2-cffi defaults: RFC 9106 low-memory profile)."""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash("releaseguard-timing-equalizer")


def burn_verification_time(password: str) -> None:
    """Spend the same time as a real check, so an unknown email can't be told apart by timing."""
    verify_password(_dummy_hash(), password)
