"""Security primitives: password hashing and session tokens.

Two independent mechanisms live in this module:

Passwords
---------
A password is **never** stored.  Only its Argon2id hash is, produced by
:func:`hash_password` and checked by :func:`verify_password`.  Argon2id is
the winner of the Password Hashing Competition and is memory hard, which
makes a brute force against a stolen table expensive.

The parameters are explicit (:data:`ARGON2_TIME_COST`,
:data:`ARGON2_MEMORY_COST`, :data:`ARGON2_PARALLELISM`,
:data:`ARGON2_HASH_LENGTH` and :data:`ARGON2_SALT_LENGTH`) so that a hash
produced by this module can always be verified, even after the defaults of
the library change.  :func:`needs_rehash` reports whether a stored hash was
produced with weaker parameters, which lets the login upgrade it.

Sessions
--------
A session token is a 256 bit random string (:func:`generate_session_token`).
It is delivered to the client in an **httpOnly cookie**, therefore a script
that runs in the browser cannot read it.

**Only the SHA-256 hash of the token is persisted.**  The raw token exists
exactly once - in the response that creates the session - and the database
only ever sees ``hash_session_token(token)``.  A dump of the ``auth_sessions``
table therefore does not allow a session to be replayed.  The comparison of
two tokens uses :func:`hmac.compare_digest`, which does not leak the
position of the first differing byte.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

__all__ = [
    "ARGON2_HASH_LENGTH",
    "ARGON2_MEMORY_COST",
    "ARGON2_PARALLELISM",
    "ARGON2_SALT_LENGTH",
    "ARGON2_TIME_COST",
    "SESSION_TOKEN_BYTES",
    "generate_session_token",
    "hash_password",
    "hash_session_token",
    "needs_rehash",
    "tokens_equal",
    "verify_password",
]

#: Number of passes over the memory (the Argon2 time cost).
ARGON2_TIME_COST: int = 3

#: Size of the memory block in KiB (64 MiB).
ARGON2_MEMORY_COST: int = 65536

#: Number of lanes that are used in parallel.
ARGON2_PARALLELISM: int = 4

#: Length of the derived key in bytes.
ARGON2_HASH_LENGTH: int = 32

#: Length of the random salt in bytes.
ARGON2_SALT_LENGTH: int = 16

#: Number of random bytes of a session token (32 bytes -> 43 url safe chars).
SESSION_TOKEN_BYTES: int = 32

#: The hasher every hash of this module is produced with.
_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LENGTH,
    salt_len=ARGON2_SALT_LENGTH,
    type=Type.ID,
)


def hash_password(plain: str) -> str:
    """Return the Argon2id hash of *plain*.

    Every call produces a **different** hash: the salt is random, therefore
    two identical passwords never share a hash.

    Raises
    ------
    ValueError
        If *plain* is not a non-empty string.
    """
    if not isinstance(plain, str) or not plain:
        raise ValueError("the password must be a non-empty string")
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """Return whether *plain* is the password of *password_hash*.

    The function **never raises**: a malformed hash, a hash of another
    scheme or an empty password are all reported as ``False``.  A caller
    therefore never has to distinguish between "the password is wrong" and
    "the stored hash is broken".
    """
    if not isinstance(plain, str) or not plain:
        return False
    if not isinstance(password_hash, str) or not password_hash:
        return False
    try:
        return bool(_hasher.verify(password_hash, plain))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False
    except Exception:  # pragma: no cover - a broken hash must never raise
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return whether *password_hash* was produced with weaker parameters.

    A hash that is malformed is reported as *needs rehash* as well: the
    next successful login replaces it with a current one.
    """
    if not isinstance(password_hash, str) or not password_hash:
        return True
    try:
        return bool(_hasher.check_needs_rehash(password_hash))
    except (InvalidHashError, VerificationError):
        return True
    except Exception:  # pragma: no cover - a broken hash must never raise
        return True


def generate_session_token() -> str:
    """Return a fresh, opaque session token.

    The token is 32 random bytes rendered with :func:`secrets.token_urlsafe`
    and is therefore at least 43 characters long and safe to use in a URL
    and in a cookie without any escaping.
    """
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest of *token*.

    The digest is what the database stores.  The raw token is never
    persisted, therefore a stolen database cannot be replayed against the
    API.
    """
    if not isinstance(token, str):
        raise ValueError("the session token must be a string")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    """Return whether *left* and *right* are the same token.

    The comparison is constant time, therefore it does not leak how many
    leading characters of two tokens are equal.
    """
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left, right)