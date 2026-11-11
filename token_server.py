"""Dedicated Token Server for STS Lab (Port 8001).

Issues tokens for the Gemini 3.8 Live Speech-to-Speech test room and dispatches 'sts-simran'.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
import secrets
import sys
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

_admin_runner = AdminDbRunner()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sts_token_server")

_dispatch_lock = Lock()
_ROOM_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$")
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"


def generate_sts_room_code() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"sts-simran-{suffix}"


def create_participant_token(settings: StsSettings, *, identity: str, room: str) -> str:
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
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
    async def run() -> Any:
        async with api.LiveKitAPI(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        ) as lk_api:
            return await work(lk_api)

    with _dispatch_lock:
        return asyncio.run(run())


async def ensure_room_and_dispatch(
    lk_api: api.LiveKitAPI, *, room: str, agent_name: str
) -> None:
    """Ensure room exists and dispatch agent concurrently for minimum startup latency."""
    async def create_room_task() -> None:
        try:
            logger.info("Ensuring room %s on LiveKit...", room)
            await lk_api.room.create_room(
                api.CreateRoomRequest(name=room, empty_timeout=300)
            )
        except Exception as exc:
            logger.debug("Room creation notice: %s", exc)

    async def dispatch_agent_task() -> None:
        try:
            logger.info("Dispatching agent '%s' to room '%s'...", agent_name, room)
            await lk_api.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
            )
        except Exception as exc:
            logger.debug("Agent dispatch notice: %s", exc)

    # Concurrently create room and dispatch agent in parallel (saving ~1-1.5s of round-trips)
    await asyncio.gather(create_room_task(), dispatch_agent_task())


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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key")
        self.end_headers()
        self.wfile.write(payload)

    def _handle_admin(self, method: str) -> None:
        """Delegate /api/admin/* to the framework-free handler (auth via X-Admin-Key)."""
        try:
            body = self._read_json() if method == "POST" else None
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
            return
        resp = handle_admin_request(method, self.path, body, self.headers.get("X-Admin-Key"), _admin_runner,
                                    client_ip=self.client_address[0])
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key")
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

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/admin"):
            self._handle_admin("POST")
            return
        if self.path not in ("/token", "/rooms"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
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
            raw_name = str(body.get("name", "Guest")).strip()
            name = raw_name if raw_name else f"Guest-{secrets.token_hex(2)}"
            room = str(body.get("room", "")).strip().lower()
            if not room:
                room = generate_sts_room_code()

            _with_livekit(
                self.settings,
                lambda lk: ensure_room_and_dispatch(
                    lk, room=room, agent_name=self.settings.agent_name
                ),
            )

            token = create_participant_token(self.settings, identity=name, room=room)
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
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        pass


def main() -> None:
    settings = StsSettings.load()
    StsTokenHandler.settings = settings
    host = settings.host
    port = settings.port
    server = ThreadingHTTPServer((host, port), StsTokenHandler)
    logger.info("Simran STS Token Server running on http://%s:%d", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
