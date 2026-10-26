"""Unit tests of the security primitives.

The tests never touch a database: they check the pure functions of
:mod:`app.core.security`.
"""

from __future__ import annotations

import re

import pytest

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    tokens_equal,
    verify_password,
)

#: A password that satisfies the rules of the service.
PASSWORD = "a-correct-horse-battery-staple"


# ----------------------------------------------------------------------
# passwords
# ----------------------------------------------------------------------
def test_a_password_verifies_against_its_hash() -> None:
    """The hash of a password verifies the password."""
    password_hash = hash_password(PASSWORD)

    assert verify_password(PASSWORD, password_hash) is True


def test_every_hash_is_salted_and_different() -> None:
    """Two hashes of the same password are never equal."""
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)

    assert first != second
    assert verify_password(PASSWORD, first) is True
    assert verify_password(PASSWORD, second) is True


def test_the_hash_never_contains_the_password() -> None:
    """The hash is a digest, the password is not part of it."""
    password_hash = hash_password(PASSWORD)

    assert PASSWORD not in password_hash
    assert password_hash.startswith("$argon2id$")


def test_a_wrong_password_is_rejected() -> None:
    """A password that was not hashed does not verify."""
    password_hash = hash_password(PASSWORD)

    assert verify_password("another password", password_hash) is False


def test_an_empty_password_is_rejected() -> None:
    """An empty password never verifies."""
    password_hash = hash_password(PASSWORD)

    assert verify_password("", password_hash) is False


def test_a_malformed_hash_is_rejected_without_raising() -> None:
    """A broken hash is reported as *wrong*, it never raises."""
    assert verify_password(PASSWORD, "not-a-hash") is False
    assert verify_password(PASSWORD, "") is False
    assert verify_password(PASSWORD, "$argon2id$broken") is False


def test_hashing_an_empty_password_raises() -> None:
    """An empty password cannot be hashed at all."""
    with pytest.raises(ValueError):
        hash_password("")


def test_a_current_hash_does_not_need_a_rehash() -> None:
    """A hash of the current parameters is up to date."""
    assert needs_rehash(hash_password(PASSWORD)) is False


def test_a_malformed_hash_needs_a_rehash() -> None:
    """A broken hash is replaced by the next successful login."""
    assert needs_rehash("not-a-hash") is True
    assert needs_rehash("") is True


# ----------------------------------------------------------------------
# session tokens
# ----------------------------------------------------------------------
def test_the_session_token_is_url_safe() -> None:
    """The token can be used in a URL and in a cookie as it is."""
    token = generate_session_token()

    assert len(token) >= 43
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token) is not None


def test_the_session_tokens_are_unique() -> None:
    """Every token is a fresh random value."""
    tokens = {generate_session_token() for _ in range(100)}

    assert len(tokens) == 100


def test_the_hash_of_a_token_is_a_deterministic_digest() -> None:
    """The digest is 64 hex characters and always the same."""
    token = generate_session_token()

    digest = hash_session_token(token)

    assert len(digest) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", digest) is not None
    assert hash_session_token(token) == digest
    assert hash_session_token(generate_session_token()) != digest


def test_the_raw_token_is_not_part_of_its_hash() -> None:
    """The digest does not contain the token."""
    token = generate_session_token()

    assert token not in hash_session_token(token)


def test_two_tokens_are_compared_correctly() -> None:
    """Only identical tokens are equal."""
    token = generate_session_token()

    assert tokens_equal(token, token) is True
    assert tokens_equal(token, generate_session_token()) is False
    assert tokens_equal(token, "") is False