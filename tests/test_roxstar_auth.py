"""Tests for the RoxStar login check (roxstar_auth.py).

In simple words: these prove that only a real, current RoxStar ACCESS token opens a Simran session,
and that forged, expired, refresh, or oddly-shaped tokens are all refused.
"""

from __future__ import annotations

import time

import jwt
import pytest

from sts_lab.roxstar_auth import (
    AuthError,
    identity_for_user,
    parse_bearer,
    room_for_user,
    verify_access_token,
)

SECRET = "unit-test-secret-not-a-real-key-0123456789-abcdefghijklmnopqrstuvwxyz-0123456789"


def _token(payload: dict | None = None, *, secret: str = SECRET, alg: str = "HS256") -> str:
    base = {"userID": 42, "type": "access", "exp": int(time.time()) + 3600}
    if payload is not None:
        base.update(payload)
    return jwt.encode(base, secret, algorithm=alg)


def _reason(token: str, secret: str = SECRET) -> str:
    with pytest.raises(AuthError) as err:
        verify_access_token(token, secret)
    return str(err.value)


def test_valid_access_token_returns_user_id():
    assert verify_access_token(_token(), SECRET) == 42


def test_user_id_may_arrive_as_a_string_like_php_sometimes_sends():
    assert verify_access_token(_token({"userID": "49102"}), SECRET) == 49102


def test_expired_token_is_rejected():
    assert _reason(_token({"exp": int(time.time()) - 600})) == "token_expired"


def test_token_without_expiry_is_rejected():
    raw = jwt.encode({"userID": 42, "type": "access"}, SECRET, algorithm="HS256")
    assert _reason(raw) == "token_invalid"


def test_refresh_token_is_rejected_because_it_lives_a_year():
    assert _reason(_token({"type": "refresh"})) == "not_an_access_token"


def test_token_without_type_is_rejected():
    raw = jwt.encode({"userID": 42, "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
    assert _reason(raw) == "not_an_access_token"


def test_token_signed_with_another_secret_is_rejected():
    assert _reason(_token(secret="some-other-secret-of-sufficient-length-0123456789")) == "token_invalid"


def test_other_algorithms_are_rejected_even_with_the_right_secret():
    assert _reason(_token(alg="HS512")) == "token_invalid"


def test_alg_none_forgery_is_rejected():
    forged = jwt.encode({"userID": 42, "type": "access", "exp": int(time.time()) + 60}, None, algorithm="none")
    assert _reason(forged) == "token_invalid"


def test_garbage_token_is_rejected():
    assert _reason("not.a.jwt") == "token_invalid"


@pytest.mark.parametrize("bad", [None, True, False, 0, -5, "abc", "", "0", [], {}])
def test_bad_user_ids_are_rejected(bad):
    payload = {"userID": bad}
    raw = jwt.encode(
        {"type": "access", "exp": int(time.time()) + 60, **payload}, SECRET, algorithm="HS256"
    )
    with pytest.raises(AuthError):
        verify_access_token(raw, SECRET)


def test_missing_user_id_claim_is_rejected():
    raw = jwt.encode({"type": "access", "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
    assert _reason(raw) == "missing_user_id"


def test_user_id_must_use_the_exact_claim_name_userID():
    raw = jwt.encode({"user_id": 42, "type": "access", "exp": int(time.time()) + 60}, SECRET, algorithm="HS256")
    assert _reason(raw) == "missing_user_id"


def test_server_without_a_secret_refuses_everyone():
    assert _reason(_token(), secret="") == "server_secret_not_configured"


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer   abc", "abc"),
        ("  Bearer abc  ", "abc"),
    ],
)
def test_parse_bearer_accepts_normal_headers(header, expected):
    assert parse_bearer(header) == expected


@pytest.mark.parametrize("header", [None, "", "abc", "Basic abc", "Bearer", "Bearer   "])
def test_parse_bearer_rejects_everything_else(header):
    with pytest.raises(AuthError):
        parse_bearer(header)


def test_room_and_identity_are_derived_from_the_user_id_only():
    assert room_for_user(49102) == "sts-simran-49102"
    assert identity_for_user(49102) == "rx-49102"
