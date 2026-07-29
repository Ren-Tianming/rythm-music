import hashlib
import secrets
from datetime import UTC, datetime

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
LEGACY_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(LEGACY_BCRYPT_PREFIXES):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False
    try:
        return password_hasher.verify(hashed_password, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    if hashed_password.startswith(LEGACY_BCRYPT_PREFIXES):
        return True
    try:
        return password_hasher.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    plain_key = f"aas_{secrets.token_urlsafe(32)}"
    prefix = plain_key[:12]
    return plain_key, prefix, hash_api_key(plain_key)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
