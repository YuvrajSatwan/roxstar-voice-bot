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

        self.list_dispatch_calls: list[str] = []

        async def list_dispatch(room_name):
            # Real LiveKit takes ~3 s and then errors for a room that was never created, so the
            # server must not ask. The fake fails loudly if it does.
            self.list_dispatch_calls.append(room_name)
            if room_name not in self.rooms:
                raise AssertionError(f"list_dispatch called for a room that does not exist: {room_name}")
            return list(self.dispatches)

        async def create_dispatch(req):
            self.created_dispatches.append(req)

        async def list_rooms(req):
            return SimpleNamespace(rooms=[SimpleNamespace(name=n) for n in self.rooms])

        async def create_room(req):
            self.created_rooms.append(req)
            if req.name not in self.rooms:
                self.rooms.append(req.name)

        self.agent_dispatch = SimpleNamespace(list_dispatch=list_dispatch, create_dispatch=create_dispatch)
        self.room_metadata_updates: list = []
        self.fail_metadata = False

        async def update_room_metadata(req):
            if self.fail_metadata:
                raise RuntimeError("livekit hiccup")
            self.room_metadata_updates.append(req)

        self.room = SimpleNamespace(
            list_rooms=list_rooms, create_room=create_room, update_room_metadata=update_room_metadata
        )


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


def test_a_brand_new_user_never_triggers_the_slow_dispatch_lookup(server):
    """LiveKit needs ~3 s to answer for a room that does not exist. New users must skip that call."""
    assert server.call(token=_login(77))[0] == 200
    assert server.lk.list_dispatch_calls == []
    assert len(server.lk.created_dispatches) == 1


def test_a_ticket_not_yet_picked_up_also_counts_as_live(server):
    server.lk.rooms = ["sts-simran-42"]  # the user's room already exists
    server.lk.dispatches =[SimpleNamespace(agent_name=AGENT, room="r", state=SimpleNamespace(deleted_at=0, jobs=[]))]
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


# --------------------------------- early start (/prewarm) ---------------------------------

def test_prewarm_is_off_by_default(server):
    status, _ = server.call("/prewarm", token=_login(42))
    assert status == 404
    assert server.lk.created_dispatches == [] and server.lk.created_rooms == []


def test_prewarm_needs_a_real_login(server):
    server.use(_settings(prewarm_enabled=True))
    status, body = server.call("/prewarm", token=None)
    assert status == 401 and body == {"error": "unauthorized"}
    assert server.lk.created_dispatches == []


def test_prewarm_gets_simran_ready_in_the_users_own_room_without_a_token(server):
    server.use(_settings(prewarm_enabled=True))
    status, body = server.call("/prewarm", token=_login(42))
    assert status == 202 and body == {"status": "started"}
    assert "token" not in body
    assert [d.room for d in server.lk.created_dispatches] == ["sts-simran-42"]
    assert server.tokens == []  # no LiveKit token is minted here
    assert server.notified == []  # the popup is cancelled by the real /token call, not by this


def test_the_real_join_after_prewarm_reuses_the_same_simran_and_one_allowance(server):
    server.use(_settings(prewarm_enabled=True, user_sessions_per_hour=1))
    token_server._session_limiter = SessionRateLimiter(1, 3600)
    assert server.call("/prewarm", token=_login(42))[1] == {"status": "started"}
    # Simran is now live in the room. The user's real /token call must not send a second one.
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]
    status, body = server.call("/token", token=_login(42))
    assert status == 200 and body["room"] == "sts-simran-42"
    assert len(server.lk.created_dispatches) == 1


def test_tapping_twice_does_not_send_two_simrans(server):
    server.use(_settings(prewarm_enabled=True))
    server.call("/prewarm", token=_login(42))
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]
    status, body = server.call("/prewarm", token=_login(42))
    assert status == 202 and body == {"status": "reused"}
    assert len(server.lk.created_dispatches) == 1


def test_prewarm_respects_the_capacity_cap(server):
    server.use(_settings(prewarm_enabled=True, max_concurrent_sessions=1))
    server.lk.rooms = ["sts-simran-7"]
    status, body = server.call("/prewarm", token=_login(42))
    assert status == 202 and body == {"status": "busy"}
    assert server.lk.created_dispatches == []


def test_standalone_prewarm_without_a_room_name_does_nothing(server):
    server.use(_settings(prewarm_enabled=True, auth_mode="standalone"))
    status, _ = server.call("/prewarm", token=_login(42))
    assert status == 400
    assert server.lk.created_dispatches == []


def test_standalone_prewarm_is_off_unless_switched_on(server):
    server.use(_settings(prewarm_enabled=False, auth_mode="standalone"))
    status, _ = server.call("/prewarm", body={"room": "sts-simran-42"})
    assert status == 404
    assert server.lk.created_dispatches == []


def test_token_call_tells_a_waiting_simran_the_user_is_arriving(server):
    server.use(_settings(prewarm_enabled=True))
    server.call("/prewarm", token=_login(42))
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]
    status, _ = server.call("/token", token=_login(42))
    assert status == 200
    assert len(server.lk.room_metadata_updates) == 1
    update = server.lk.room_metadata_updates[0]
    assert update.room == "sts-simran-42"
    stamp = json.loads(update.metadata)["user_arriving"]
    assert abs(time.time() - stamp) < 30  # a fresh timestamp, so an old note from a past visit never counts


def test_no_arriving_note_when_early_start_is_off(server):
    assert server.call("/token", token=_login(42))[0] == 200
    assert server.lk.room_metadata_updates == []


def test_a_failed_arriving_note_never_blocks_the_user(server):
    server.use(_settings(prewarm_enabled=True))
    server.lk.fail_metadata = True
    status, body = server.call("/token", token=_login(42))
    assert status == 200 and body["token"] == "lk-token"


# --------------------------------- early start in standalone (lab) mode ---------------------------------

def test_standalone_prewarm_sends_simran_to_the_named_room(server):
    server.use(_settings(prewarm_enabled=True, auth_mode="standalone"))
    status, body = server.call("/prewarm", body={"room": "sts-simran-42"})
    assert status == 202 and body == {"status": "started"}
    assert [d.room for d in server.lk.created_dispatches] == ["sts-simran-42"]


def test_standalone_prewarm_rejects_a_bad_room_name(server):
    server.use(_settings(prewarm_enabled=True, auth_mode="standalone"))
    for bad in ("", "A B", "../x", "x" * 80):
        assert server.call("/prewarm", body={"room": bad})[0] == 400
    assert server.lk.created_dispatches == []


def test_standalone_join_after_prewarm_does_not_send_a_second_simran(server):
    server.use(_settings(prewarm_enabled=True, auth_mode="standalone"))
    server.call("/prewarm", body={"room": "sts-simran-42"})
    server.lk.dispatches = [_dispatch(token_server.api.JobStatus.JS_RUNNING)]
    status, body = server.call("/token", body={"name": "Rahul", "room": "sts-simran-42"})
    assert status == 200
    assert len(server.lk.created_dispatches) == 1
    assert len(server.lk.room_metadata_updates) == 1  # "user is arriving" note


def test_standalone_new_room_never_asks_about_agents_before_it_exists(server):
    """Same ~3 s trap as the login path: the room must be created before we ask what is in it."""
    server.use(_settings(auth_mode="standalone"))
    assert server.call("/token", body={"name": "Rahul", "room": "sts-simran-77"})[0] == 200
    assert len(server.lk.created_dispatches) == 1  # the fake raises if asked about a room that does not exist yet


# --------------------------------- one conversation per user ("session expired") ---------------------------------

@pytest.fixture
def used_file(tmp_path, monkeypatch):
    from sts_lab import session_gate
    path = tmp_path / "used.json"
    monkeypatch.setattr(session_gate, "DEFAULT_FILE", path)
    monkeypatch.setattr(token_server, "SessionGate", lambda enabled: session_gate.SessionGate(enabled, path))
    return path


def test_a_used_conversation_gets_session_expired_and_no_simran(server, used_file):
    from sts_lab.session_gate import SessionGate
    server.use(_settings(single_session_per_user=True))
    SessionGate(True, used_file).mark_used("sts-simran-42")
    status, body = server.call("/token", token=_login(42))
    assert status == 410 and body == {"error": "session_expired"}
    assert server.lk.created_dispatches == [] and server.lk.created_rooms == []
    assert server.tokens == []  # no way into the room


def test_other_users_are_not_affected(server, used_file):
    from sts_lab.session_gate import SessionGate
    server.use(_settings(single_session_per_user=True))
    SessionGate(True, used_file).mark_used("sts-simran-42")
    assert server.call("/token", token=_login(43))[0] == 200


def test_switch_off_means_everybody_can_come_back(server, used_file):
    from sts_lab.session_gate import SessionGate
    SessionGate(True, used_file).mark_used("sts-simran-42")
    server.use(_settings(single_session_per_user=False))
    assert server.call("/token", token=_login(42))[0] == 200


def test_prewarm_does_not_start_simran_for_an_expired_user(server, used_file):
    from sts_lab.session_gate import SessionGate
    server.use(_settings(prewarm_enabled=True, single_session_per_user=True))
    SessionGate(True, used_file).mark_used("sts-simran-42")
    status, body = server.call("/prewarm", token=_login(42))
    assert status == 202 and body == {"status": "expired"}
    assert server.lk.created_dispatches == []


def test_standalone_mode_also_expires_user_rooms(server, used_file):
    from sts_lab.session_gate import SessionGate
    server.use(_settings(auth_mode="standalone", single_session_per_user=True, prewarm_enabled=True))
    SessionGate(True, used_file).mark_used("sts-simran-42")
    assert server.call("/token", body={"name": "R", "room": "sts-simran-42"})[0] == 410
    assert server.call("/prewarm", body={"room": "sts-simran-42"})[1] == {"status": "expired"}
    assert server.lk.created_dispatches == []
    # a lab room is never limited
    assert server.call("/token", body={"name": "R", "room": "sts-simran-ab3k"})[0] == 200


def test_preflight_allows_the_dev_tunnel_header(server):
    """A page on another origin (dev tunnel) sends ngrok-skip-browser-warning; the preflight must allow it."""
    conn = http.client.HTTPConnection("127.0.0.1", server.httpd.server_port, timeout=5)
    conn.request("OPTIONS", "/token", headers={
        "Origin": "http://localhost:5175",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization,ngrok-skip-browser-warning",
    })
    resp = conn.getresponse()
    resp.read()
    allowed = (resp.getheader("Access-Control-Allow-Headers") or "").lower()
    conn.close()
    assert resp.status == 204
    for name in ("content-type", "authorization", "ngrok-skip-browser-warning"):
        assert name in allowed
