"""Dedicated Token Server for STS Lab (Port 8001).

Issues tokens for the Gemini 3.8 Live Speech-to-Speech test room and dispatches 'sts-simran'.
"""

from __future__ import annotations

import asyncio
import json
import time
import logging
import mimetypes
import os
import re
import secrets
import sys
import threading
from pathlib import Path

# Ensure sts_lab and parent directory are on sys.path
_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent
for _p in (str(_parent_dir), str(_current_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_dist_dir = _current_dir / "web" / "dist"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from collections.abc import Awaitable, Callable
from datetime import timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

from livekit import api
from sts_lab.config import StsSettings
from sts_lab.db.admin_api import AdminDbRunner, handle_admin_request
from sts_lab.rox_services import notify_session_started_async
from sts_lab.roxstar_auth import (
    AuthError,
    identity_for_user,
    parse_bearer,
    room_for_user,
    verify_access_token,
)
from sts_lab.session_gate import SessionGate
from sts_lab.session_limits import SessionRateLimiter
from sts_lab.text_chat import SimranTextChatEngine
import hmac

_admin_runner = AdminDbRunner()
_chat_engine: SimranTextChatEngine | None = None


_chat_engine_lock = threading.Lock()


def get_chat_engine() -> SimranTextChatEngine:
    global _chat_engine
    if _chat_engine is None:
        with _chat_engine_lock:  # two first requests at once must not build two engines
            if _chat_engine is None:
                _chat_engine = SimranTextChatEngine()
    return _chat_engine


def _warm_chat_engine() -> None:
    """Build the text engine and open its Gemini connection before the first user message. Never raises."""
    try:
        get_chat_engine().warm_up()
    except Exception as exc:  # noqa: BLE001 - e.g. no Gemini key yet; the request path reports it properly
        logging.getLogger("sts_token_server").warning("Chat engine warm-up skipped: %s", exc)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sts_token_server")

_dispatch_lock = Lock()
_ROOM_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$")
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"

# Every Simran room starts with this (lab rooms: sts-simran-ab3k, RoxStar rooms: sts-simran-49102).
# We count rooms with this prefix to know how many conversations are live right now.
SIMRAN_ROOM_PREFIX = "sts-simran-"

# Filled in by main() once settings are known. One limiter shared by all request threads.
_session_limiter: SessionRateLimiter | None = None

# Protection for POST /api/simran/chat-reply (each call costs a paid Gemini request).
# Built once from the settings; rebuilt only if the limits change.
_chat_guard_lock = Lock()
_chat_guard_key: tuple[int, int] | None = None
_chat_slots: threading.BoundedSemaphore | None = None
_chat_limiter: SessionRateLimiter | None = None


def _get_chat_guards(settings: Any) -> tuple[threading.BoundedSemaphore | None, SessionRateLimiter | None]:
    """The concurrency cap and the per-user rate limiter for text replies (None = switched off)."""
    global _chat_guard_key, _chat_slots, _chat_limiter
    max_concurrent = int(getattr(settings, "chat_max_concurrent", 0) or 0)
    per_minute = int(getattr(settings, "chat_replies_per_min", 0) or 0)
    key = (max_concurrent, per_minute)
    with _chat_guard_lock:
        if _chat_guard_key != key:
            _chat_slots = threading.BoundedSemaphore(max_concurrent) if max_concurrent > 0 else None
            _chat_limiter = SessionRateLimiter(per_minute, 60.0) if per_minute > 0 else None
            _chat_guard_key = key
        return _chat_slots, _chat_limiter


def _positive_int(value: Any) -> int:
    """A user id sent by rox-chat, or 0 when it is missing or not a positive whole number."""
    if isinstance(value, bool):
        return 0
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def generate_sts_room_code() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"sts-simran-{suffix}"


def create_participant_token(
    settings: StsSettings, *, identity: str, room: str, display_name: str | None = None
) -> str:
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(display_name or identity)
        .with_ttl(timedelta(hours=2))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )


def _with_livekit(settings: StsSettings, work: Callable[[api.LiveKitAPI], Awaitable[Any]]) -> Any:
    # A LiveKit call that never answers must not hold the global lock (and so every other user) forever.
    # 0 = no timeout (the old behaviour).
    timeout = float(getattr(settings, "livekit_timeout_sec", 0) or 0)

    async def run() -> Any:
        async with api.LiveKitAPI(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        ) as lk_api:
            if timeout > 0:
                return await asyncio.wait_for(work(lk_api), timeout)
            return await work(lk_api)

    if timeout <= 0:
        with _dispatch_lock:
            return asyncio.run(run())

    if not _dispatch_lock.acquire(timeout=timeout):
        raise TimeoutError("LiveKit dispatch is busy: waited %.1fs for the lock" % timeout)
    try:
        return asyncio.run(run())
    finally:
        _dispatch_lock.release()


def _dispatch_is_live(dispatch: Any) -> bool:
    """True if this agent dispatch still has (or is about to get) a running Simran.

    In simple words: a dispatch is the 'please send Simran to this room' ticket.
    The ticket is 'live' if Simran is working on it, or has not picked it up yet.
    It is NOT live if she already finished (she leaves after handing the user off).
    """
    state = dispatch.state
    if getattr(state, "deleted_at", 0):
        return False
    jobs = list(state.jobs)
    if not jobs:
        return True  # ticket just created, no Simran assigned yet
    live = (api.JobStatus.JS_PENDING, api.JobStatus.JS_RUNNING)
    return any(job.state.status in live for job in jobs)


async def ensure_room_and_dispatch(
    lk_api: api.LiveKitAPI, *, room: str, agent_name: str
) -> None:
    """Make sure the room exists, then send Simran unless one is already there.

    The room is created FIRST on purpose. Asking LiveKit which agents are in a room that does not
    exist yet takes about 3 SECONDS (and ends in an error). When the two calls ran at the same time,
    the question usually arrived before the room existed, so almost every new session paid the 3 s.
    Creating the room takes ~0.01 s, after which the question is answered instantly.
    """
    try:
        logger.info("Ensuring room %s on LiveKit...", room)
        await lk_api.room.create_room(api.CreateRoomRequest(name=room, empty_timeout=300))
    except Exception as exc:  # "already exists" is fine
        logger.debug("Room creation notice: %s", exc)

    try:
        # Check if an agent is already dispatched or working in this room
        existing = await lk_api.agent_dispatch.list_dispatch(room_name=room)
        if any(d.agent_name == agent_name and _dispatch_is_live(d) for d in existing):
            logger.info("Agent '%s' already live/dispatched to room '%s', skipping duplicate dispatch", agent_name, room)
            return
        logger.info("Dispatching agent '%s' to room '%s'...", agent_name, room)
        await lk_api.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
        )
    except Exception as exc:
        logger.debug("Agent dispatch notice: %s", exc)


async def prepare_private_room(
    lk_api: api.LiveKitAPI,
    *,
    room: str,
    agent_name: str,
    max_sessions: int,
    allow_new_session: Callable[[], bool],
) -> str:
    """Get one user's private Simran room ready. Returns one of:

      "reused"       the user already has a live Simran in this room (refresh / double tap): do nothing new
      "started"      a new room was prepared and ONE Simran was sent to it
      "busy"         too many conversations are live right now (cost / capacity protection)
      "rate_limited" this user has started too many sessions this hour

    Why not just dispatch every time (like the lab does)? Because a WebView refresh or a double tap
    would then put TWO Simrans in the same room talking over each other, and cost double.
    """
    # One cheap call tells us which rooms exist. We need it for two things below.
    listing = await lk_api.room.list_rooms(api.ListRoomsRequest())
    room_exists = any(r.name == room for r in listing.rooms)

    # 1) Is a Simran already working in this user's room? Then just let them back in.
    #    Only ask when the room exists: LiveKit takes about 3 SECONDS to answer (with an error)
    #    for a room that was never created, and that is every brand-new session. If the room does
    #    not exist, there cannot be a Simran in it.
    existing: list = []
    if room_exists:
        try:
            existing = await lk_api.agent_dispatch.list_dispatch(room_name=room)
        except Exception as exc:  # LiveKit hiccup: treat as "no Simran yet"
            logger.debug("list_dispatch notice: %s", exc)
    if any(d.agent_name == agent_name and _dispatch_is_live(d) for d in existing):
        return "reused"

    # 2) New session. First the global ceiling: count the other live Simran rooms.
    if max_sessions > 0:
        others = [r for r in listing.rooms if r.name.startswith(SIMRAN_ROOM_PREFIX) and r.name != room]
        if len(others) >= max_sessions:
            return "busy"

    # 3) Then this user's own hourly allowance. (Done last so refreshes / busy answers never use it up.)
    if not allow_new_session():
        return "rate_limited"

    # 4) Create the private room (2 people + Simran at most; empty rooms clean themselves up after 2 min)
    #    and send exactly one Simran.
    try:
        await lk_api.room.create_room(api.CreateRoomRequest(name=room, empty_timeout=120, max_participants=3))
    except Exception as exc:  # "already exists" is fine
        logger.debug("Room creation notice: %s", exc)
    await lk_api.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
    )
    return "started"


def clean_display_name(raw: Any) -> str:
    """The name shown on screen. Display only: identity and room never come from it."""
    text = "".join(ch for ch in str(raw or "") if ch.isprintable()).strip()[:40]
    return text or "Friend"


class StsTokenHandler(BaseHTTPRequestHandler):
    settings: StsSettings

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        origin = self.headers.get("Origin", "*")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key, Authorization, ngrok-skip-browser-warning")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_admin(self, method: str) -> None:
        """Delegate /api/admin/* to the framework-free handler (auth via X-Admin-Key)."""
        try:
            body = self._read_json() if method == "POST" else None
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return
        # Behind a reverse proxy the socket peer can look local; a forwarded header means it is not.
        client_ip = "proxied" if self.headers.get("X-Forwarded-For") else self.client_address[0]
        resp = handle_admin_request(method, self.path, body, self.headers.get("X-Admin-Key"), _admin_runner,
                                    client_ip=client_ip)
        origin = self.headers.get("Origin", "*")
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key")
        for key, value in resp.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(resp.body)

    def _serve_static_file(self, file_path: Path) -> None:
        if not file_path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "File not found"})
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        try:
            content = file_path.read_bytes()
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self.headers.get("Origin", "*")
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key, Authorization, ngrok-skip-browser-warning")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/admin"):
            self._handle_admin("GET")
            return
        if self.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "sts-token-server",
                    "persona": "Simran",
                    "model": self.settings.model,
                    "voice": self.settings.voice,
                },
            )
            return
        elif self.path == "/duets":
            if self.settings.is_roxstar_mode:
                # Production never shows the built-in demo rooms. Real rooms come from rox-partyroom via the worker.
                self._send_json(HTTPStatus.OK, {"duets": []})
                return
            from sts_lab.onboarding import DuetRoomRegistry
            registry = DuetRoomRegistry()
            rooms = [
                {
                    "room_id": r.room_id,
                    "title": r.title,
                    "genre": r.genre,
                    "host_name": r.host_name,
                    "song_title": r.song_title,
                    "singers_count": r.singers_count,
                }
                for r in registry.list_available()
            ]
            self._send_json(HTTPStatus.OK, {"duets": rooms})
            return

        # Check for static frontend distribution
        if _dist_dir.is_dir():
            clean_path = self.path.split("?")[0].lstrip("/")
            target = (_dist_dir / clean_path).resolve()
            # Ensure target stays within _dist_dir (path traversal protection)
            if _dist_dir in target.parents or target == _dist_dir:
                if target.is_file():
                    self._serve_static_file(target)
                    return
                # SPA fallback: serve index.html for application routes
                index_file = _dist_dir / "index.html"
                if index_file.is_file():
                    self._serve_static_file(index_file)
                    return

        if self.path == "/":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "sts-token-server",
                    "persona": "Simran",
                    "model": self.settings.model,
                    "voice": self.settings.voice,
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 8192:
            raise ValueError("Request too large")
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("Expected JSON body")
        return body

    def _session_expired(self, room: str) -> bool:
        """One conversation per user (when switched on): has this user's one conversation already happened?"""
        return SessionGate(self.settings.single_session_per_user).has_used(room)

    def _send_session_expired(self) -> None:
        # 410 Gone: this room's one conversation is over. The page shows "session expired".
        self._send_json(HTTPStatus.GONE, {"error": "session_expired"})

    def _handle_roxstar_token(self) -> None:
        """POST /token in RoxStar mode: a real, logged-in RoxStar user gets ONE private room with Simran.

        Everything that matters is decided HERE on the server, never by the browser:
          - who the user is   -> from their verified RoxStar login token
          - which room        -> sts-simran-<their user id> (a room name sent by the client is ignored)
          - their LiveKit id  -> rx-<their user id>
        """
        settings = self.settings
        # Read the (small, size-capped) request body FIRST. If we answered 401 while the body was still unread,
        # the OS would reset the connection and the app would see a network error instead of a clean 401.
        body = self._read_json()
        # 1) Who is calling? Every failure looks the same to the caller; the reason goes only to our log.
        try:
            user_id = verify_access_token(parse_bearer(self.headers.get("Authorization")), settings.jwt_api_key)
        except AuthError as exc:
            logger.info("Rejected Simran token request: %s", exc)
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        room = room_for_user(user_id)
        if self._session_expired(room):
            logger.info("User %s tried to re-enter: their one conversation with Simran is over", user_id)
            self._send_session_expired()
            return
        limiter = _session_limiter

        # 2) Prepare the private room (also enforces the capacity cap and the per-user hourly limit).
        outcome = _with_livekit(
            settings,
            lambda lk: prepare_private_room(
                lk,
                room=room,
                agent_name=settings.agent_name,
                max_sessions=settings.max_concurrent_sessions,
                allow_new_session=lambda: limiter.allow(str(user_id)) if limiter else True,
            ),
        )
        if outcome == "busy":
            logger.warning("Simran at capacity (%s sessions); user %s told to retry later", settings.max_concurrent_sessions, user_id)
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "busy"})
            return
        if outcome == "rate_limited":
            logger.info("User %s hit the Simran session limit", user_id)
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return

        # 2b) Early start only: Simran may already be waiting in the room. Tell her the user is about to
        #     walk in, so she can start her first line NOW instead of waiting to see them arrive
        #     (LiveKit tells her about a new person ~1-2 s late). The note lives in the room's
        #     metadata, so she sees it whether she was ready before or after this moment.
        #     Best effort: if it fails, she simply greets when she sees the user.
        if settings.prewarm_enabled:
            try:
                _with_livekit(
                    settings,
                    lambda lk: lk.room.update_room_metadata(
                        api.UpdateRoomMetadataRequest(room=room, metadata=json.dumps({"user_arriving": time.time()}))
                    ),
                )
            except Exception as exc:
                logger.info("Could not signal the arriving user to Simran (non-fatal): %s", exc)

        # 3) Tell rox-chat this user opened Simran so their 2-minute popup is cancelled (best effort, background).
        notify_session_started_async(settings.chat_base_url, settings.simran_internal_secret, user_id)

        token = create_participant_token(
            settings,
            identity=identity_for_user(user_id),
            room=room,
            display_name=clean_display_name(body.get("name")),
        )
        logger.info("Simran session %s for user %s", outcome, user_id)
        self._send_json(
            HTTPStatus.OK,
            {
                "token": token,
                "url": settings.livekit_url,
                "room": room,
                "persona": "Simran",
                "model": settings.model,
                "voice": settings.voice,
                "max_session_sec": settings.max_session_sec,
            },
        )

    def _handle_prewarm(self) -> None:
        """POST /prewarm: the app says "this user just tapped join" so Simran can get ready early.

        In simple words: it does the SAME room preparation /token does (private room + one Simran),
        just a few seconds sooner, while the page is still loading. It returns no token. When the
        real /token call arrives, it finds Simran already there ("reused"), so there is never a
        second Simran and the user's hourly allowance is used only once.
        Same login check as /token. Off unless STS_PREWARM_ENABLED is on.
        """
        settings = self.settings
        if not settings.prewarm_enabled:
            self._drain_body()
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return

        if not settings.is_roxstar_mode:
            # Standalone / lab mode (no login): same as the lab's /token, the page names the room.
            try:
                body = self._read_json()
            except Exception:
                body = {}
            room = str(body.get("room", "")).strip().lower()
            if not _ROOM_CODE.match(room):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid room code."})
                return
            if self._session_expired(room):
                self._send_json(HTTPStatus.ACCEPTED, {"status": "expired"})
                return
            _with_livekit(
                settings,
                lambda lk: ensure_room_and_dispatch(lk, room=room, agent_name=settings.agent_name),
            )
            logger.info("Simran prewarm (standalone) for room %s", room)
            self._send_json(HTTPStatus.ACCEPTED, {"status": "started"})
            return

        self._drain_body()
        try:
            user_id = verify_access_token(parse_bearer(self.headers.get("Authorization")), settings.jwt_api_key)
        except AuthError as exc:
            logger.info("Rejected Simran prewarm request: %s", exc)
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        if self._session_expired(room_for_user(user_id)):
            self._send_json(HTTPStatus.ACCEPTED, {"status": "expired"})  # nothing to prepare
            return
        limiter = _session_limiter
        outcome = _with_livekit(
            settings,
            lambda lk: prepare_private_room(
                lk,
                room=room_for_user(user_id),
                agent_name=settings.agent_name,
                max_sessions=settings.max_concurrent_sessions,
                allow_new_session=lambda: limiter.allow(str(user_id)) if limiter else True,
            ),
        )
        logger.info("Simran prewarm %s for user %s", outcome, user_id)
        # The app ignores the body; the outcome is only for our logs and tests.
        self._send_json(HTTPStatus.ACCEPTED, {"status": outcome})

    def _drain_body(self) -> None:
        """Read and discard a small request body before answering without using it.

        If we reply while the body is still unread, the OS can reset the connection and the caller sees a
        network error instead of our clean 404 / 401.
        """
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if 0 < length <= 8192:
                self.rfile.read(length)
        except Exception:
            pass

    def _internal_secret_ok(self, configured_secret: str) -> bool:
        """True only if the caller sent the right internal secret. Never raises, whatever the headers contain."""
        incoming = self.headers.get("X-Simran-Secret") or ""
        if not incoming:
            try:
                incoming = parse_bearer(self.headers.get("Authorization"))
            except AuthError:
                return False
        try:
            # Compare as bytes: comparing text with non-ASCII characters raises instead of answering "no".
            return hmac.compare_digest(incoming.encode("utf-8"), configured_secret.encode("utf-8"))
        except Exception:
            return False

    def _handle_simran_chat_reply(self) -> None:
        """Handle POST /api/simran/chat-reply from rox-chat microservice."""
        configured_secret = getattr(self.settings, "simran_internal_secret", "") or os.getenv("SIMRAN_INTERNAL_SECRET", "")
        if configured_secret:
            if not self._internal_secret_ok(configured_secret):
                self._drain_body()
                logger.warning("Unauthorized /api/simran/chat-reply attempt")
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Invalid internal secret"})
                return
        elif getattr(self.settings, "require_internal_secret", True):
            # No secret configured means anybody who can reach this port could spend our Gemini budget.
            self._drain_body()
            logger.error("Refusing /api/simran/chat-reply: SIMRAN_INTERNAL_SECRET is not set")
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "chat_unavailable"})
            return

        try:
            body = self._read_json()
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        user_message = str(body.get("user_message") or body.get("message") or "").strip()
        user_name = clean_display_name(body.get("user_name") or body.get("name") or "dost")
        recent_history = body.get("recent_history") or body.get("history") or []

        if not user_message:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing user_message"})
            return

        # One user cannot run up the Gemini bill: a per-minute limit, then a cap on replies generated at once.
        # In both cases rox-chat simply uses its own fallback reply.
        slots, limiter = _get_chat_guards(self.settings)
        chat_user = _positive_int(body.get("user_id"))
        if limiter is not None and chat_user and not limiter.allow(f"chat:{chat_user}"):
            logger.info("Simran chat reply rate-limited for user %s", chat_user)
            self._send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
            return
        if slots is not None and not slots.acquire(blocking=False):
            logger.warning("Simran chat replies at capacity (%s at once)", self.settings.chat_max_concurrent)
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "busy"})
            return
        try:
            engine = get_chat_engine()
            reply_data = engine.generate_reply(
                user_message=user_message,
                user_name=user_name,
                recent_history=recent_history,
                timeout_sec=float(getattr(self.settings, "chat_timeout_sec", 3.0)),
            )
        except Exception as exc:  # engine could not even start (for example no Gemini key): never crash the handler
            logger.error("Simran chat engine unavailable: %s", exc)
            self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "chat_unavailable"})
            return
        finally:
            if slots is not None:
                slots.release()
        self._send_json(HTTPStatus.OK, reply_data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/admin"):
            self._handle_admin("POST")
            return
        if self.path == "/api/simran/chat-reply":
            self._handle_simran_chat_reply()
            return
        if self.path == "/prewarm":
            try:
                self._handle_prewarm()
            except Exception as exc:
                logger.error("Prewarm error: %s", exc, exc_info=True)
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Could not prepare a session."})
            return
        if self.path not in ("/token", "/rooms"):
            self._drain_body()
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return

        # RoxStar mode: no anonymous room creation at all. /token (with a real login) is the only door in.
        if self.settings.is_roxstar_mode:
            if self.path == "/rooms":
                self._drain_body()
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
                return
            try:
                self._handle_roxstar_token()
            except Exception as exc:
                logger.error("Token error: %s", exc, exc_info=True)
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Could not start a session. Please try again."})
            return

        try:
            body = self._read_json()

            if self.path == "/rooms":
                room = generate_sts_room_code()
                _with_livekit(
                    self.settings,
                    lambda lk: ensure_room_and_dispatch(
                        lk, room=room, agent_name=self.settings.agent_name
                    ),
                )
                self._send_json(HTTPStatus.CREATED, {"room": room, "title": "Simran STS Lab"})
                return

            # POST /token
            raw_name = str(body.get("name", "Guest")).strip()[:64]
            name = raw_name if raw_name else f"Guest-{secrets.token_hex(2)}"
            room = str(body.get("room", "")).strip().lower()
            if not room:
                room = generate_sts_room_code()
            elif not _ROOM_CODE.match(room):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid room code."})
                return

            if self._session_expired(room):
                logger.info("Room %s: its one conversation with Simran is over", room)
                self._send_session_expired()
                return

            _with_livekit(
                self.settings,
                lambda lk: ensure_room_and_dispatch(
                    lk, room=room, agent_name=self.settings.agent_name
                ),
            )

            # Early start only: tell a Simran who is already waiting that the user is about to walk in.
            if self.settings.prewarm_enabled:
                try:
                    _with_livekit(
                        self.settings,
                        lambda lk: lk.room.update_room_metadata(
                            api.UpdateRoomMetadataRequest(room=room, metadata=json.dumps({"user_arriving": time.time()}))
                        ),
                    )
                except Exception as exc:
                    logger.info("Could not signal the arriving user to Simran (non-fatal): %s", exc)

            # A per-browser visitor id keeps two people who type the same name apart in the database
            visitor =re.sub(r"[^a-z0-9]", "", str(body.get("visitor_id", "")).lower())[:16]
            identity = f"{name}~{visitor}" if visitor else name
            token = create_participant_token(self.settings, identity=identity, room=room, display_name=name)
            self._send_json(
                HTTPStatus.OK,
                {
                    "token": token,
                    "url": self.settings.livekit_url,
                    "room": room,
                    "persona": "Simran",
                    "model": self.settings.model,
                    "voice": self.settings.voice,
                },
            )
        except Exception as exc:
            logger.error("Token error: %s", exc, exc_info=True)
            # Details stay in the server log; clients get a generic message.
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Could not start a session. Please try again."})

    def log_message(self, format: str, *args: Any) -> None:
        pass


def main() -> None:
    global _session_limiter
    settings = StsSettings.load()
    if settings.is_roxstar_mode:
        # Refuse to start half-configured: without the secret every login check would fail (or worse, be skipped).
        if not settings.jwt_api_key:
            raise ValueError("STS_AUTH_MODE=roxstar needs JWT_API_KEY (the secret RoxStar Auth signs logins with).")
        if not settings.chat_base_url or not settings.simran_internal_secret:
            logger.warning("CHAT_BASE_URL / SIMRAN_INTERNAL_SECRET not set: the 2-minute popup will not be cancelled.")
        _session_limiter = SessionRateLimiter(settings.user_sessions_per_hour, 3600.0)
        logger.info(
            "RoxStar mode ON: login required, max %s live sessions, %s sessions/user/hour",
            settings.max_concurrent_sessions, settings.user_sessions_per_hour,
        )
    if not settings.simran_internal_secret and settings.require_internal_secret:
        logger.error("SIMRAN_INTERNAL_SECRET is not set: /api/simran/chat-reply will refuse every request.")
    StsTokenHandler.settings = settings
    if getattr(settings, "chat_warmup", True):
        threading.Thread(target=_warm_chat_engine, name="chat-warmup", daemon=True).start()
    host = settings.host
    port = settings.port
    server = ThreadingHTTPServer((host, port), StsTokenHandler)
    logger.info("Simran STS Token Server running on http://%s:%d", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
