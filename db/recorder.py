"""Non-blocking conversation recorder used by the LiveKit worker.

Design rules (see AGENTS.md: the audio event loop must never stall):
  * Every public ``record_*`` / ``set_*`` / ``mark_*`` method is synchronous,
    does O(1) in-memory work and enqueues a database operation. Nothing awaits
    the database on the audio path.
  * One background consumer task drains the queue strictly in order, so an
    insert always lands before the update that references it.
  * If the database is unreachable the consumer logs a warning and retries with
    exponential backoff while operations wait in a bounded in-memory queue. The
    voice agent is never affected. When the queue is full the oldest-pending
    policy is "drop new operations" and the loss is counted and logged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from . import conversation_rules as rules
from . import repository as repo
from .database import Database, acquire_database, release_database

logger = logging.getLogger("sts_db.recorder")

Op = Callable[[Database], Awaitable[None]]

_STAGE2_FIELDS = {"musical_role", "singing_comfort", "music_taste", "favorite_song"}
_STAGE3_FIELDS = {"expectations", "coins_explained"}


def infer_stage(discovered: set[str] | list[str], *, pitched: bool = False) -> int:
    """Map captured fields to the funnel phase the conversation has reached (1 to 4)."""
    topics = set(discovered)
    if pitched or "duet_attempted" in topics:
        return 4
    if topics & _STAGE3_FIELDS:
        return 3
    if topics & _STAGE2_FIELDS:
        return 2
    return 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe(fn):
    """Recorder methods are called from the audio worker: they must never raise."""
    import functools

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Recorder.%s failed: %s", fn.__name__, exc)
            return None

    return wrapper


class NullRecorder:
    """Drop-in replacement when persistence is disabled."""

    session_id = ""
    enabled = False

    def start(self) -> None: ...
    def set_identity(self, identity: str) -> None: ...
    def record_user_turn(self, text: str) -> None: ...
    def record_assistant_turn(self, text: str) -> None: ...
    def record_metrics(self, ttft_ms: float | None, tokens_per_second: float | None, duration_s: float | None) -> None: ...
    def record_response_latency(self, ms: float) -> None: ...
    def record_profile_field(self, field: str, value: str) -> None: ...
    def record_coin_balance(self, balance: int) -> None: ...
    def set_stage(self, stage: int) -> None: ...
    def mark_exit(self, reason: str) -> None: ...
    async def close(self, default_reason: str = "user_disconnected", timeout: float = 8.0) -> bool:
        return True


class SessionRecorder:
    enabled = True

    def __init__(
        self,
        *,
        room_name: str,
        identity: str | None,
        model: str | None = None,
        voice: str | None = None,
        database_url: str | None = None,
        queue_max: int = 5000,
        retry_delay: float = 1.0,
        max_retry_delay: float = 30.0,
        user_turn_merge_seconds: float = 6.0,
    ) -> None:
        self.session_id = uuid4().hex
        self.room_name = room_name
        self.identity = identity
        self.model = model
        self.voice = voice
        self._url = database_url
        self._queue: asyncio.Queue[Op] = asyncio.Queue(maxsize=queue_max)
        self._retry_delay = retry_delay
        self._max_retry_delay = max_retry_delay
        self._merge_window = user_turn_merge_seconds
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        self._deadline = float("inf")
        self._closed = False
        self.dropped_ops = 0
        self.failed_attempts = 0

        self._user_id: str | None = None  # resolved by the start op
        self._started_at = _now()
        self._t0 = time.monotonic()
        self._turn = 0
        self._stage = 1
        self._exit_reason: str | None = None
        self._ttfts: list[float] = []
        self._user_turns = 0
        # last user / assistant turn bookkeeping for coalescing and metric attachment
        self._last_user: dict[str, Any] | None = None
        self._last_assistant: dict[str, Any] | None = None
        self._last_turn_speaker: str | None = None
        self._pending_metrics: tuple[float | None, float | None, float | None, float] | None = None
        self._pending_fields: dict[str, str] = {}
        self._pending_latency: tuple[float, float] | None = None
        self._open_question: dict[str, Any] | None = None
        self._fallbacks: list[asyncio.TimerHandle] = []
        self._deferred_list: list[tuple[str, dict[str, Any]]] = []
        self._assistant_texts: list[str] = []
        self._occupation_parts: list[str] = []
        self._coins_noted = False
        self.fallback_wait_seconds = 4.0

    # ------------------------------------------------------------ lifecycle
    @_safe
    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._consume())
        self._enqueue(self._op_start)

    async def close(self, default_reason: str = "user_disconnected", timeout: float = 8.0) -> bool:
        """Close the session row and flush the queue. Returns False if operations were lost."""
        if self._closed:
            return True
        self._flush_fallbacks()
        self._closed = True
        duration = time.monotonic() - self._t0
        reason = self._exit_reason or default_reason
        if self._exit_reason is None and (self._user_turns == 0 or duration < 15):
            reason = "abandoned"
        avg_ttft = round(sum(self._ttfts) / len(self._ttfts), 1) if self._ttfts else None
        is_onboarded = reason in ("duet_handoff", "solo_handoff", "two_decline_exit")
        ended_at = _now()
        total_turns, final_stage = self._turn, self._stage

        async def op_close(db: Database) -> None:
            async with db.session() as s:
                await repo.close_session(
                    s, session_id=self.session_id, user_id=self._user_id, ended_at=ended_at,
                    duration_seconds=duration, exit_reason=reason, final_stage=final_stage,
                    avg_ttft_ms=avg_ttft, total_turns=total_turns, is_onboarded=is_onboarded,
                )
                await s.commit()

        self._enqueue(op_close)
        self._closing = True
        self._deadline = time.monotonic() + timeout
        if self._task is None:
            return True
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout + 1.0)
        except asyncio.TimeoutError:
            self._task.cancel()
        except Exception as exc:  # pragma: no cover
            logger.warning("Recorder close error: %s", exc)
        lost = self._queue.qsize() + self.dropped_ops
        if lost:
            logger.warning("Recorder closed with %d unsaved operations for session %s", lost, self.session_id)
        return lost == 0

    # --------------------------------------------------------------- queue
    def _enqueue(self, op: Op) -> None:
        try:
            self._queue.put_nowait(op)
        except asyncio.QueueFull:
            self.dropped_ops += 1
            if self.dropped_ops in (1, 10, 100) or self.dropped_ops % 1000 == 0:
                logger.warning("Persistence queue full, dropped %d operations", self.dropped_ops)

    async def _consume(self) -> None:
        db: Database | None = None
        try:
            while True:
                if self._closing and self._queue.empty():
                    break
                try:
                    op = await asyncio.wait_for(self._queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                delay = self._retry_delay
                while True:
                    try:
                        if db is None:
                            db = await acquire_database(self._url)
                        await op(db)
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self.failed_attempts += 1
                        logger.warning("Persistence write failed (%s: %s). Retrying in %.1fs, %d queued.",
                                       type(exc).__name__, exc, delay, self._queue.qsize())
                        if self._closing and time.monotonic() >= self._deadline:
                            self.dropped_ops += 1
                            break
                        await asyncio.sleep(min(delay, max(0.05, self._deadline - time.monotonic())) if self._closing else delay)
                        delay = min(delay * 2, self._max_retry_delay)
                self._queue.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            if db is not None:
                try:
                    await release_database(db)
                except Exception:  # pragma: no cover
                    pass

    # ------------------------------------------------------------ operations
    async def _op_start(self, db: Database) -> None:
        async with db.session() as s:
            user = await repo.get_or_create_user(s, self.identity)
            self._user_id = user.id
            await repo.create_session(
                s, session_id=self.session_id, room_name=self.room_name, user_id=user.id,
                model=self.model, voice=self.voice, started_at=self._started_at,
            )
            await s.commit()

    @_safe
    def set_identity(self, identity: str) -> None:
        """Re-link the session to the real user once their participant joins."""
        if not identity or repo.clean_identity(identity) == repo.clean_identity(self.identity):
            return
        self.identity = identity

        async def op(db: Database) -> None:
            async with db.session() as s:
                user = await repo.get_or_create_user(s, identity)
                self._user_id = user.id
                await repo.set_session_user(s, self.session_id, user.id)
                await s.commit()

        self._enqueue(op)

    # ------------------------------------------------------------- turn log
    def _new_message(self, speaker: str, text: str, **extra: Any) -> dict[str, Any]:
        msg = {
            "id": uuid4().hex, "turn": self._turn, "speaker": speaker, "text": text,
            "time": time.monotonic(), "fields": {}, **extra,
        }
        self._turn += 1
        values = {
            "id": msg["id"], "session_id": self.session_id, "turn_index": msg["turn"],
            "speaker": speaker, "transcript": text, "timestamp": _now(),
            "ttft_ms": extra.get("ttft_ms"), "tokens_per_second": extra.get("tokens_per_second"),
            "audio_duration_seconds": extra.get("audio_duration_seconds"),
            "flagged_issue": bool(extra.get("flagged_issue", False)),
            "admin_tag": extra.get("admin_tag"), "flag_note": extra.get("flag_note"),
        }

        async def op(db: Database) -> None:
            async with db.session() as s:
                await repo.add_message(s, **values)
                await s.commit()

        self._enqueue(op)
        return msg

    def _update_message(self, message_id: str, **values: Any) -> None:
        async def op(db: Database) -> None:
            async with db.session() as s:
                await repo.update_message(s, message_id, **values)
                await s.commit()

        self._enqueue(op)

    @_safe
    def record_user_turn(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self._closed:
            return
        last = self._last_user
        # Gemini can emit several final segments for one utterance. Merge them.
        if (last is not None and self._last_turn_speaker == "User"
                and time.monotonic() - last["time"] < self._merge_window):
            last["text"] = f"{last['text']} {text}"
            last["time"] = time.monotonic()
            self._update_message(last["id"], transcript=last["text"])
            return
        msg = self._new_message("User", text)
        self._user_turns += 1
        if self._pending_fields:
            msg["fields"].update(self._pending_fields)
            self._update_message(msg["id"], profile_fields_captured=dict(msg["fields"]))
            self._pending_fields = {}
        self._last_user = msg
        self._last_turn_speaker = "User"
        question = self._open_question
        if question is not None and not question["used"]:
            question["used"] = True
            self._deferred_list.append((question["topic"], msg))
            self._fallbacks.append(asyncio.get_running_loop().call_later(
                self.fallback_wait_seconds, self._fallback_capture, question["topic"], msg))

    @_safe
    def record_assistant_turn(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self._closed:
            return
        ttft = tps = dur = None
        pending = self._pending_metrics
        used_pending = False
        if pending is not None and time.monotonic() - pending[3] < 20.0:
            ttft, tps, dur, _ = pending
            used_pending = True
        self._pending_metrics = None
        measured = self._pending_latency
        if measured is not None and time.monotonic() - measured[1] < 30.0:
            ttft = measured[0]  # the real "user stopped -> Simran started" delay beats the provider number
        elif ttft is not None:
            self._ttfts.append(float(ttft))
        self._pending_latency = None

        # Automatic review flags
        flag_tag = flag_note = None
        norm = "".join(ch for ch in text.lower() if ch.isalnum())
        if len(norm) >= 25 and norm in self._assistant_texts:
            flag_tag, flag_note = "repeated_turn", "Auto: Simran repeated an earlier line word for word."
        elif rules.INTERVIEW_PHRASE.search(text):
            flag_tag, flag_note = "interview_phrase", "Auto: interview-style lead-in (ye bataiye)."
        self._assistant_texts.append(norm)

        msg = self._new_message("Simran", text, ttft_ms=ttft, tokens_per_second=tps, audio_duration_seconds=dur,
                                flagged_issue=bool(flag_tag), admin_tag=flag_tag, flag_note=flag_note)
        msg["lat_set"] = measured is not None
        msg["metrics_set"] = used_pending
        self._last_assistant = msg
        self._last_turn_speaker = "Simran"

        # Funnel phase, exit and the open profile question, all read from what she said
        self.set_stage(rules.detect_stage(text))
        if rules.is_exit_line(text):
            self.mark_exit("two_decline_exit")
        if not self._coins_noted and "welcome coins" in text.lower():
            self._coins_noted = True  # she told the user about the 50 welcome coins
            self.set_stage(3)
            self.record_coin_balance(50)
        topic = rules.detect_question_topic(text)
        self._open_question = {"topic": topic, "used": False, "captured": False} if topic else None

    @_safe
    def record_metrics(self, ttft_ms: float | None, tokens_per_second: float | None, duration_s: float | None) -> None:
        """Attach latency metrics to the Simran turn they belong to (they may arrive before or after it)."""
        if (ttft_ms is not None and ttft_ms < 0) or (duration_s is not None and duration_s < 0.3):
            return  # "unknown" sentinel or an empty/interrupted generation: not a usable measurement
        if ttft_ms is not None and ttft_ms < 20:
            ttft_ms = None  # the provider reports a few milliseconds here, which cannot be real audio latency
        last = self._last_assistant
        if last is not None and not last.get("metrics_set") and time.monotonic() - last["time"] < 20.0:
            values: dict[str, Any] = {"tokens_per_second": tokens_per_second, "audio_duration_seconds": duration_s}
            last["metrics_set"] = True
            # A measured response latency (user stops -> Simran starts) always wins over the provider value
            if last.get("ttft_ms") is None and ttft_ms is not None:
                values["ttft_ms"] = last["ttft_ms"] = float(ttft_ms)
                self._ttfts.append(float(ttft_ms))
            self._update_message(last["id"], **values)
        else:
            self._pending_metrics = (ttft_ms, tokens_per_second, duration_s, time.monotonic())

    @_safe
    def record_response_latency(self, ms: float) -> None:
        """Measured delay between the user finishing speaking and Simran starting to speak."""
        if ms is None or ms < 0 or ms > 60000:
            return
        self._ttfts.append(float(ms))
        last = self._last_assistant
        if (last is not None and not last.get("lat_set") and self._last_turn_speaker == "Simran"
                and time.monotonic() - last["time"] < 3.0):
            last.update(ttft_ms=float(ms), lat_set=True)
            self._update_message(last["id"], ttft_ms=float(ms))
        else:
            self._pending_latency = (float(ms), time.monotonic())

    @_safe
    def record_profile_field(self, field: str, value: str) -> None:
        field = (field or "").strip().lower()
        value = (value or "").strip()
        if not field or not value or self._closed:
            return
        # Funnel stage inference
        if field in _STAGE2_FIELDS:
            self.set_stage(2)
        if field in _STAGE3_FIELDS:
            self.set_stage(3)
        if field == "duet_attempted":
            self.set_stage(4)
        if self._open_question is not None and field == self._open_question["topic"]:
            self._open_question["captured"] = True
        # Attach the capture to the user turn that produced it
        if self._last_user is not None:
            self._last_user["fields"][field] = value
            self._update_message(self._last_user["id"], profile_fields_captured=dict(self._last_user["fields"]))
        else:
            self._pending_fields[field] = value

        async def op(db: Database) -> None:
            async with db.session() as s:
                if self._user_id is None:
                    user = await repo.get_or_create_user(s, self.identity)
                    self._user_id = user.id
                await repo.apply_profile_field(s, self._user_id, field, value)
                await s.commit()

        if field in repo.SCALAR_FIELDS or field in repo.LIST_FIELDS:
            self._enqueue(op)

    @_safe
    def record_coin_balance(self, balance: int) -> None:
        async def op(db: Database) -> None:
            async with db.session() as s:
                if self._user_id is not None:
                    await repo.set_coin_balance(s, self._user_id, int(balance))
                    await s.commit()

        self._enqueue(op)

    def _flush_fallbacks(self) -> None:
        """Run pending fallback captures now (the session may end before the timer fires)."""
        for handle in self._fallbacks:
            handle.cancel()
        self._fallbacks = []
        pending, self._deferred_list = self._deferred_list, []
        for topic, message in pending:
            self._fallback_capture(topic, message)

    def _fallback_capture(self, topic: str, msg: dict[str, Any]) -> None:
        """Store the user's answer to the question Simran just asked when the model did not call save_profile.

        Marked ``_auto`` in the message so the dashboard shows it as inferred, not as a tool capture.
        """
        try:
            if self._closed or msg.get("fallback_done"):
                return
            msg["fallback_done"] = True
            question = self._open_question
            if question is not None and question["topic"] == topic and question["captured"]:
                return
            if topic in msg["fields"]:
                return
            value = rules.clean_answer(topic, msg["text"])
            if not value:
                return
            if topic == "occupation":
                self._occupation_parts.append(value)
                value = ", ".join(self._occupation_parts)
            msg["fields"][topic] = value
            msg["fields"][rules.AUTO_KEY] = list(msg["fields"].get(rules.AUTO_KEY, [])) + [topic]
            self._update_message(msg["id"], profile_fields_captured=dict(msg["fields"]))
            if topic in _STAGE2_FIELDS:
                self.set_stage(2)
            if topic in _STAGE3_FIELDS:
                self.set_stage(3)

            async def op(db: Database) -> None:
                async with db.session() as s:
                    if self._user_id is None:
                        user = await repo.get_or_create_user(s, self.identity)
                        self._user_id = user.id
                    await repo.apply_profile_field(s, self._user_id, topic, value)
                    await s.commit()

            if topic in repo.SCALAR_FIELDS or topic in repo.LIST_FIELDS:
                self._enqueue(op)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Fallback capture failed: %s", exc)

    @_safe
    def set_stage(self, stage: int) -> None:
        self._stage = max(self._stage, min(4, int(stage)))

    @_safe
    def mark_exit(self, reason: str) -> None:
        """First explicit reason wins (handoff or 2-decline exit)."""
        if self._exit_reason is None:
            self._exit_reason = reason


def create_recorder(
    *, room_name: str, identity: str | None, model: str | None = None, voice: str | None = None,
) -> SessionRecorder | NullRecorder:
    """Factory honouring ``STS_DB_ENABLED`` (default true)."""
    if os.getenv("STS_DB_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return NullRecorder()
    return SessionRecorder(room_name=room_name, identity=identity, model=model, voice=voice)
