"""Framework-free admin API handler.

``token_server.py`` (stdlib ``http.server``) delegates every ``/api/admin/*``
request to :func:`handle_admin_request`. Keeping it free of HTTP and LiveKit
imports makes it unit-testable.

Auth: if ``ADMIN_API_KEY`` is set, every request must carry a matching
``X-Admin-Key`` header. If it is NOT set (development), the API is open but
only to requests coming from the same machine (127.0.0.1 / ::1); any other
client gets 403. Transcripts contain personal data, so set the key before the
server is reachable from outside.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, urlparse

from . import analytics
from .database import Database, acquire_database

logger = logging.getLogger("sts_db.admin")

_ID = r"([0-9a-f]{32})"


@dataclass
class AdminResponse:
    status: int
    body: bytes
    content_type: str = "application/json"
    headers: dict[str, str] = field(default_factory=dict)


def _json(status: int, payload: Any) -> AdminResponse:
    return AdminResponse(status, json.dumps(payload, default=str).encode("utf-8"))


class AdminDbRunner:
    """Runs admin coroutines on one private event loop thread so sync HTTP handlers can use async SQLAlchemy."""

    def __init__(self, database_url: str | None = None) -> None:
        self._url = database_url
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._db: Database | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=loop.run_forever, name="admin-db-loop", daemon=True)
                self._thread.start()
                self._loop = loop
            return self._loop

    def run(self, fn: Callable[[Database], Awaitable[Any]], timeout: float = 20.0) -> Any:
        loop = self._ensure_loop()

        async def _go() -> Any:
            if self._db is None:
                self._db = await acquire_database(self._url)
            return await fn(self._db)

        future = asyncio.run_coroutine_threadsafe(_go(), loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            future.cancel()
            raise

    def close(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)


def _first(query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    vals = query.get(key)
    return vals[0] if vals else default


def _int(query: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int(_first(query, key, str(default)) or default)
    except ValueError:
        return default


def _filters(source: dict[str, Any]) -> dict[str, Any]:
    keys = ("exit_reason", "role", "q", "date_from", "date_to")
    out = {k: (source.get(k) or None) for k in keys}
    out["flagged"] = str(source.get("flagged", "")).lower() in ("1", "true", "yes")
    return out


def check_admin_key(provided: str | None, expected: str | None = None) -> bool:
    expected = expected if expected is not None else os.getenv("ADMIN_API_KEY", "")
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


_LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}


def handle_admin_request(
    method: str, raw_path: str, body: dict[str, Any] | None, admin_key: str | None, runner: AdminDbRunner,
    expected_key: str | None = None, client_ip: str | None = "127.0.0.1",
) -> AdminResponse:
    parsed = urlparse(raw_path)
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)
    body = body or {}

    configured = expected_key if expected_key is not None else os.getenv("ADMIN_API_KEY", "")
    if path == "/api/admin/auth-mode":
        return _json(200, {"auth_required": bool(configured)})
    if configured:
        if not check_admin_key(admin_key, configured):
            return _json(401, {"error": "Invalid or missing admin key."})
    elif (client_ip or "") not in _LOOPBACK:
        return _json(403, {"error": "No ADMIN_API_KEY is set, so the admin API only answers requests from this machine."})

    try:
        if method == "GET":
            if path == "/api/admin/metrics":
                days = _int(query, "days", 30)
                return _json(200, runner.run(lambda db: _with(db, lambda s: analytics.metrics(s, days))))
            if path == "/api/admin/funnel":
                days = _int(query, "days", 30)
                return _json(200, runner.run(lambda db: _with(db, lambda s: analytics.funnel(s, days))))
            if path == "/api/admin/sessions":
                flat = {k: v[0] for k, v in query.items() if v}
                page, size = _int(query, "page", 1), _int(query, "page_size", 25)
                return _json(200, runner.run(lambda db: _with(
                    db, lambda s: analytics.list_sessions(s, page=page, page_size=size, **_filters(flat)))))
            m = re.fullmatch(rf"/api/admin/sessions/{_ID}", path)
            if m:
                data = runner.run(lambda db: _with(db, lambda s: analytics.get_session(s, m.group(1))))
                return _json(200, data) if data else _json(404, {"error": "Session not found."})
            if path == "/api/admin/users":
                page, size = _int(query, "page", 1), _int(query, "page_size", 25)
                args = dict(city=_first(query, "city"), role=_first(query, "role"),
                            song=_first(query, "song"), q=_first(query, "q"))
                return _json(200, runner.run(lambda db: _with(
                    db, lambda s: analytics.list_users(s, page=page, page_size=size, **args))))
            m = re.fullmatch(rf"/api/admin/users/{_ID}", path)
            if m:
                data = runner.run(lambda db: _with(db, lambda s: analytics.get_user(s, m.group(1))))
                return _json(200, data) if data else _json(404, {"error": "User not found."})
            if path == "/api/admin/flag-reasons":
                return _json(200, {"reasons": list(analytics.FLAG_REASONS)})

        if method == "POST":
            m = re.fullmatch(rf"/api/admin/messages/{_ID}/flag", path)
            if m:
                tag = str(body.get("reason") or body.get("tag") or "other")[:64]
                if tag not in analytics.FLAG_REASONS:
                    return _json(400, {"error": f"reason must be one of {list(analytics.FLAG_REASONS)}"})
                flagged = bool(body.get("flagged", True))
                note = body.get("note")
                msg = runner.run(lambda db: _with(db, lambda s: analytics.flag_message(
                    s, m.group(1), flagged=flagged, tag=tag, note=str(note) if note else None)))
                return _json(200, msg) if msg else _json(404, {"error": "Message not found."})
            m = re.fullmatch(rf"/api/admin/sessions/{_ID}/review", path)
            if m:
                rating = body.get("rating")
                ok = runner.run(lambda db: _with(db, lambda s: analytics.update_session_review(
                    s, m.group(1), notes=body.get("notes"), rating=int(rating) if rating not in (None, "") else None)))
                return _json(200, {"ok": True}) if ok else _json(404, {"error": "Session not found."})
            m = re.fullmatch(rf"/api/admin/sessions/{_ID}/delete", path)
            if m:
                ok = runner.run(lambda db: _with(db, lambda s: analytics.delete_session(s, m.group(1))))
                return _json(200, {"ok": True}) if ok else _json(404, {"error": "Session not found."})
            if path == "/api/admin/export":
                fmt = str(body.get("format", "json")).lower()
                if fmt not in ("json", "csv"):
                    return _json(400, {"error": "format must be 'json' or 'csv'."})
                if str(body.get("kind", "conversations")) == "users":
                    urows = runner.run(lambda db: _with(db, lambda s: analytics.export_users(s)), timeout=60.0)
                    if fmt == "csv":
                        return AdminResponse(
                            200, analytics.rows_to_csv(urows, analytics.USER_EXPORT_COLUMNS).encode("utf-8"),
                            "text/csv; charset=utf-8",
                            {"Content-Disposition": 'attachment; filename="simran_users.csv"'})
                    return AdminResponse(200, json.dumps({"count": len(urows), "rows": urows}, default=str).encode("utf-8"),
                                         "application/json",
                                         {"Content-Disposition": 'attachment; filename="simran_users.json"'})
                filters = _filters(body)
                flagged_only = bool(body.get("flagged_only", False))
                rows = runner.run(lambda db: _with(db, lambda s: analytics.export_rows(
                    s, flagged_only=flagged_only, **filters)), timeout=60.0)
                if fmt == "csv":
                    return AdminResponse(200, analytics.rows_to_csv(rows).encode("utf-8"), "text/csv; charset=utf-8",
                                         {"Content-Disposition": 'attachment; filename="simran_conversations.csv"'})
                return AdminResponse(200, json.dumps({"count": len(rows), "rows": rows}, default=str).encode("utf-8"),
                                     "application/json",
                                     {"Content-Disposition": 'attachment; filename="simran_conversations.json"'})
    except FutureTimeout:
        return _json(504, {"error": "Database query timed out."})
    except Exception as exc:
        logger.error("Admin request failed: %s", exc, exc_info=True)
        return _json(500, {"error": "Admin query failed. See server logs."})

    return _json(404, {"error": "Unknown admin endpoint."})


async def _with(db: Database, fn: Callable[[Any], Awaitable[Any]]) -> Any:
    async with db.session() as s:
        return await fn(s)
