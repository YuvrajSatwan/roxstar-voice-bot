"""End-to-end tests for the token server in RoxStar mode.

The real HTTP handler runs on localhost. Only LiveKit is replaced by a fake, so we can check
exactly which rooms get created and how many Simrans get sent.

In simple words, these tests prove:
  - no login / refresh token / forged token  -> no room
  - a user can only ever get THEIR OWN room, whatever the browser asks for
  - a refresh or double tap never sends a second Simran
  - when Simran is too busy, or a user starts too many sessions, they get a clear answer
"""

from __future__ import annotations

import asyncio
import http.client
import json
import sys
import threading
import time
import types
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import jwt
import pytest

# LiveKit is not needed to test our logic. If it is not installed (as on a plain dev machine),
# provide a minimal stand-in so token_server can be imported.
try:
    import livekit.api  # noqa: F401
except ImportError:  # pragma: no cover - depends on the machine
    _api = types.SimpleNamespace(
        JobStatus=types.SimpleNamespace(JS_PENDING=1, JS_RUNNING=2, JS_SUCCESS=3, JS_FAILED=4),
        AccessToken=None, VideoGrants=None, LiveKitAPI=None,
        CreateRoomRequest=lambda **kw: types.SimpleNamespace(**kw),
        ListRoomsRequest=lambda **kw: types.SimpleNamespace(**kw),
        CreateAgentDispatchRequest=lambda **kw: types.SimpleNamespace(**kw),
    )
    _lk = types.ModuleType("livekit")
    _lk.api = _api
    sys.modules["livekit"] = _lk
    sys.modules["livekit.api"] = _api

from sts_lab import token_server  # noqa: E402
from sts_lab.config import StsSettings  # noqa: E402
from sts_lab.session_limits import SessionRateLimiter  # noqa: E402

SECRET = "unit-test-secret-not-a-real-key-0123456789-abcdefghijklmnopqrstuvwxyz-0123456789"
AGENT = "sts-simran"


def _login(user_id=42, *, type_="access", exp_in=3600, secret=SECRET, alg="HS256") -> str:
    return jwt.encode({"userID": user_id, "type": type_, "exp": int(time.time()) + exp_in}, secret, algorithm=alg)


def _dispatch(status, room="sts-simran-42"):
    job = SimpleNamespace(state=SimpleNamespace(status=status))
    return SimpleNamespace(agent_name=AGENT, room=room, state=SimpleNamespace(deleted_at=0, jobs=[job]))


class FakeLiveKit:
    """Pretends to be LiveKit and records what we asked it to do."""

    def __init__(self, rooms: list[str] | None = None, dispatches: list | None = None):
        self.rooms = list(rooms or [])
        self.dispatches = list(dispatches or [])
        self.created_rooms: list = []
        self.created_dispatches: list = []

        async def list_dispatch(room_name):
            return list(self.dispatches)

        async def create_dispatch(req):
            self.created_dispatches.append(req)

        async def list_rooms(req):
            return SimpleNamespace(rooms=[SimpleNamespace(name=n) for n in self.rooms])

        async def create_room(req):
            self.created_rooms.append(req)

        self.agent_dispatch = SimpleNamespace(list_dispatch=list_dispatch, create_dispatch=create_dispatch)
        self.room = SimpleNamespace(list_rooms=list_rooms, create_room=create_room)


def _settings(**over) -> StsSettings:
    base = dict(
        livekit_url="wss://example.invalid", livekit_api_key="k", livekit_api_secret="s", gemini_api_key="g",
        auth_mode="roxstar", jwt_api_key=SECRET, max_concurrent_sessions=50, user_sessions_per_hour=3,
        chat_base_url="http://chat.invalid", simran_internal_secret="shh",
    )
    base.update(over)
    return StsSettings(**base)


@pytest.fixture
def server(monkeypatch):
    """Start the real handler; yields a helper to call it. LiveKit, the token signer and the chat call are faked."""
    state = SimpleNamespace(lk=FakeLiveKit(), notified=[], tokens=[])

    def fake_with_livekit(settings, work):
        return asyncio.run(work(state.lk))

    def fake_participant_token(settings, *, identity, room, display_name=None):
        state.tokens.append({"identity": identity, "room": room, "display_name": display_name})
        return "lk-token"

    monkeypatch.setattr(token_server, "_with_livekit", fake_with_livekit)
    monkeypatch.setattr(token_server, "create_participant_token", fake_participant_token)
    monkeypatch.setattr(token_server, "notify_session_started_async",
                        lambda base, secret, uid: state.notified.append((base, secret, uid)))
    monkeypatch.setattr(token_server, "_session_limiter", SessionRateLimiter(3, 3600))

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), token_server.StsTokenHandler)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True).start()
    state.httpd = httpd

    def use(settings: StsSettings | None = None):
        token_server.StsTokenHandler.settings = settings or _settings()

    def call(path="/token", body=None, token=None, method="POST"):
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        # A GET carries no body, like every real client. (Sending one the server never reads makes Windows
        # reset the connection, which made this test fail about 1 run in 40.)
        payload = json.dumps(body or {}) if method == "POST" else None
        conn.request(method, path, payload, headers)
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"{}")
        conn.close()
        return resp.status, data

    state.use, state.call = use, call
    use()
    yield state
    httpd.shutdown()
    httpd.server_close()


# --------------------------------- who may come in ---------------------------------

def test_no_login_means_no_room(server):
    status, body = server.call(token=None)
    assert status == 401 and body == {"error": "unauthorized"}
    assert server.lk.created_dispatches == [] and server.lk.created_rooms == []


@pytest.mark.parametrize(
    "token",
    [
        _login(type_="refresh"),
        _login(exp_in=-600),
        _login(secret="a-completely-different-secret-that-is-long-enough-0123456789-abcdef"),
        "garbage",
    ],
    ids=["refresh-token", "expired", "wrong-secret", "garbage"],
)
def test_bad_logins_never_reach_livekit(server, token):
    status, body = server.call(token=token)
    assert status == 401 and body == {"error": "unauthorized"}
    assert server.lk.created_dispatches == []


def test_401_never_reveals_why(server):
    a = server.call(token=_login(type_="refresh"))
    b = server.call(token=_login(exp_in=-600))
    c = server.call(token=None)
    assert a == b == c


def test_server_with_no_secret_configured_lets_nobody_in(server):
    server.use(_settings(jwt_api_key=""))
    assert server.call(token=_login())[0] == 401


# --------------------------------- the private room ---------------------------------

def test_user_gets_their_own_room_and_one_simran(server):
    status, body = server.call(body={"name": "Rahul"}, token=_login(42))
    assert status == 200
    assert body["room"] == "sts-simran-42" and body["token"] == "lk-token"
    assert server.tokens[0] == {"identity": "rx-42", "room": "sts-simran-42", "display_name": "Rahul"}
    assert len(server.lk.created_dispatches) == 1
    assert server.lk.created_dispatches[0].room == "sts-simran-42"
    assert server.lk.created_dispatches[0].agent_name == AGENT


def test_a_room_name_sent_by_the_browser_is_ignored(server):
    # User 42 tries to walk into user 99's room.
    status, body = server.call(body={"room": "sts-simran-99", "visitor_id": "x"}, token=_login(42))
    assert status == 200 and body["room"] == "sts-simran-42"
    assert server.tokens[0]["room"] == "sts-simran-42"
    assert server.lk.created_dispatches[0].room == "sts-simran-42"


def test_display_name_cannot_change_identity(server):
    server.call(body={"name": "rx-99\n\x00<script>"}, token=_login(42))
    assert server.tokens[0]["identity"] == "rx-42"
    assert "\n" not in server.tokens[0]["display_name"] and "\x00" not in server.tokens[0]["display_name"]


def test_missing_name_falls_back_to_friend(server):
    server.call(body={}, token=_login(42))
    assert server.tokens[0]["display_name"] == "Friend"


def test_anonymous_room_creation_is_switched_off(server):
    status, _ = server.call(path="/rooms", token=_login(42))
    assert status == 404
    assert server.lk.created_rooms == [] and server.lk.created_dispatches == []


def test_duets_endpoint_shows_no_demo_rooms_in_production(server):
    status, body = server.call(path="/duets", method="GET")
    assert status == 200 and body == {"duets": []}


# ------------------------------ one Simran per room ------------------------------

def test_refresh_or_double_tap_does_not_send_a_second_simran(server):
    server.call(token=_login(42))
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]  # first Simran is now working
    status, _ = server.call(token=_login(42))
    assert status == 200
    assert len(server.lk.created_dispatches) == 1  # still just ONE


def test_a_ticket_not_yet_picked_up_also_counts_as_live(server):
    server.lk.dispatches = [SimpleNamespace(agent_name=AGENT, room="r", state=SimpleNamespace(deleted_at=0, jobs=[]))]
    server.call(token=_login(42))
    assert server.lk.created_dispatches == []


def test_after_simran_has_left_a_new_session_gets_a_new_simran(server):
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_SUCCESS)]
    status, _ = server.call(token=_login(42))
    assert status == 200 and len(server.lk.created_dispatches) == 1


def test_a_deleted_ticket_does_not_count(server):
    d = _dispatch(token_server.api.JobStatus.JS_RUNNING)
    d.state.deleted_at = 123456
    server.lk.dispatches = [d]
    server.call(token=_login(42))
    assert len(server.lk.created_dispatches) == 1


def test_refreshes_do_not_use_up_the_hourly_allowance(server):
    server.use(_settings(user_sessions_per_hour=1))
    token_server._session_limiter = SessionRateLimiter(1, 3600)
    assert server.call(token=_login(42))[0] == 200  # uses the one allowed new session
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]
    for _ in range(5):
        assert server.call(token=_login(42))[0] == 200  # refreshes: never blocked


# ------------------------------- capacity and limits -------------------------------

def test_when_simran_is_full_the_user_gets_busy_and_nothing_is_created(server):
    server.use(_settings(max_concurrent_sessions=2))
    server.lk.rooms = ["sts-simran-1", "sts-simran-2", "some-other-app-room"]
    status, body = server.call(token=_login(42))
    assert status == 503 and body == {"error": "busy"}
    assert server.lk.created_dispatches == [] and server.lk.created_rooms == []


def test_only_simran_rooms_count_towards_capacity(server):
    server.use(_settings(max_concurrent_sessions=2))
    server.lk.rooms = ["sts-simran-1", "party-room-9", "party-room-10", "chat-3"]
    assert server.call(token=_login(42))[0] == 200


def test_busy_does_not_use_up_the_users_hourly_allowance(server):
    server.use(_settings(max_concurrent_sessions=1))
    token_server._session_limiter = SessionRateLimiter(1, 3600)
    server.lk.rooms = ["sts-simran-1"]
    for _ in range(4):
        assert server.call(token=_login(42))[0] == 503
    server.lk.rooms = []  # capacity frees up
    assert server.call(token=_login(42))[0] == 200  # the allowance is still intact


def test_zero_max_sessions_means_no_cap(server):
    server.use(_settings(max_concurrent_sessions=0))
    server.lk.rooms = [f"sts-simran-{i}" for i in range(500)]
    assert server.call(token=_login(42))[0] == 200


def test_a_user_who_keeps_starting_new_sessions_gets_429(server):
    token_server._session_limiter = SessionRateLimiter(3, 3600)
    codes = []
    for _ in range(5):
        server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_SUCCESS)]  # each time the old Simran is gone
        codes.append(server.call(token=_login(42))[0])
    assert codes == [200, 200, 200, 429, 429]
    assert len(server.lk.created_dispatches) == 3


def test_one_users_limit_does_not_affect_another(server):
    token_server._session_limiter = SessionRateLimiter(1, 3600)
    assert server.call(token=_login(1))[0] == 200
    assert server.call(token=_login(2))[0] == 200


# --------------------------------- popup cancellation ---------------------------------

def test_chat_is_told_the_session_started(server):
    server.call(token=_login(42))
    assert server.notified == [("http://chat.invalid", "shh", 42)]


def test_chat_is_not_told_when_the_user_was_refused(server):
    server.use(_settings(max_concurrent_sessions=1))
    server.lk.rooms = ["sts-simran-1"]
    server.call(token=_login(42))
    server.call(token=None)
    assert server.notified == []


# ------------------------------------ resilience ------------------------------------

def test_livekit_failure_gives_a_generic_error_and_no_details(server, monkeypatch):
    def boom(settings, work):
        raise RuntimeError("secret internal detail wss://lk.example key=abc")

    monkeypatch.setattr(token_server, "_with_livekit", boom)
    status, body = server.call(token=_login(42))
    assert status == 400 and "secret" not in json.dumps(body) and "lk.example" not in json.dumps(body)


def test_standalone_mode_is_untouched_by_all_of_this(server, monkeypatch):
    """With STS_AUTH_MODE unset the lab behaves exactly as before: no login needed."""
    server.use(_settings(auth_mode="standalone", jwt_api_key=""))
    monkeypatch.setattr(token_server, "ensure_room_and_dispatch", lambda *a, **k: asyncio.sleep(0))
    status, body = server.call(body={"name": "Rahul"}, token=None)
    assert status == 200 and body["room"].startswith("sts-simran-")
