"""One conversation per user ("this session has expired").

In simple words: when switched on, a user gets ONE conversation with Simran. Once Simran has started
talking to them, coming back into the room shows "session expired" instead of starting a new one.

How it works:
  - The worker calls ``mark_used(room)`` the moment the conversation really starts (Simran's first line).
  - The token server calls ``has_used(room)`` before it lets anybody in or sends Simran.
  - The "used" list is a small JSON file shared by both processes (they run on the same machine).

Only RoxStar user rooms (``sts-simran-<number>``) are covered. Lab rooms and test rooms are never blocked.
It is OFF unless STS_SINGLE_SESSION_PER_USER=true. To let a user talk to Simran again (testing), use
``py tools/reset_simran_session.py <user id>`` (or ``all``).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path

logger = logging.getLogger("sts_session_gate")

USER_ROOM = re.compile(r"^sts-simran-\d+$")
DEFAULT_FILE = Path(__file__).resolve().parent / ".sts_used_sessions.json"

_lock = threading.Lock()


class SessionGate:
    def __init__(self, enabled: bool, path: str | os.PathLike[str] | None = None) -> None:
        self.enabled = enabled
        self.path = Path(path) if path else DEFAULT_FILE

    def covers(self, room: str) -> bool:
        """Only RoxStar user rooms are limited to one conversation."""
        return self.enabled and bool(USER_ROOM.match(room or ""))

    def _read(self) -> dict[str, float]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            # An unreadable file must not lock everybody out (or let everybody in twice): treat as empty, say so.
            logger.warning("Could not read %s (%s); treating as empty", self.path, exc)
            return {}

    def _read_for_write(self) -> dict[str, float] | None:
        """The current records, for a read-then-write. None = could not be read right now: do NOT write.

        Writing after a failed read would replace everybody's records with one. So:
          - a missing file is simply empty,
          - a CORRUPT file is set aside as ``<name>.corrupt-<time>`` (so it can be recovered) and we start fresh,
          - any other read problem (file locked, permissions) means "try again later": nothing is written.
        """
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            reason: object = "not a JSON object"
        except FileNotFoundError:
            return {}
        except ValueError as exc:
            reason = exc
        except OSError as exc:
            logger.warning("Could not read %s (%s); not writing so existing records are kept", self.path, exc)
            return None
        aside = self.path.with_name(f"{self.path.name}.corrupt-{int(time.time())}")
        try:
            os.replace(self.path, aside)
            logger.error("%s is corrupt (%s); kept a copy at %s and starting a fresh file", self.path, reason, aside)
            return {}
        except OSError as exc:
            logger.error("%s is corrupt (%s) and could not be set aside (%s); not writing", self.path, reason, exc)
            return None

    def has_used(self, room: str) -> bool:
        if not self.covers(room):
            return False
        with _lock:
            return room in self._read()

    def mark_used(self, room: str) -> bool:
        """Record that this user's one conversation has started. Returns True if it was newly recorded."""
        if not self.covers(room):
            return False
        with _lock:
            data = self._read_for_write()
            if data is None:
                return False  # could not read safely: stay open for this user rather than damage the records
            if room in data:
                return False
            data[room] = time.time()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)  # atomic: the token server never sees a half-written file
            return True

    def reset(self, room: str | None = None) -> int:
        """Let one room (or, with None, everyone) have a new conversation. Returns how many were cleared."""
        with _lock:
            data = self._read_for_write()
            if data is None:
                raise OSError(f"Cannot read {self.path} safely, so nothing was reset. Try again.")
            if room is None:
                cleared = len(data)
                data = {}
            else:
                cleared = 1 if data.pop(room, None) is not None else 0
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return cleared
