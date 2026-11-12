"""One-off data repair for rows written before the recorder rules existed.

Run:   py -m sts_lab.db.maintenance            (uses DATABASE_URL or the default SQLite file)

It is safe to run more than once. It only touches derived values:
  * removes impossible latency numbers (negative, or a few milliseconds) and bogus tokens/sec,
  * recomputes each session's turn count, average latency and funnel phase,
  * relabels sessions that ended with one of Simran's exit excuses as ``two_decline_exit``,
  * clears user names that were only the typed placeholder (shows as Guest until a real name is captured),
  * adds the automatic review flags (repeated turn, "ye bataiye" lead-in) to old turns.
Transcripts and profile data are never changed.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from sqlalchemy import select, update

from . import conversation_rules as rules
from .database import acquire_database, release_database
from .models import ConversationSession, Message, User

logger = logging.getLogger("sts_db.maintenance")


async def repair(db) -> dict[str, int]:
    stats = {"metrics_cleared": 0, "sessions_updated": 0, "flags_added": 0, "exit_relabelled": 0, "names_reset": 0}
    async with db.session() as s:
        msgs = (await s.execute(select(Message).order_by(Message.session_id, Message.turn_index))).scalars().all()
        by_session: dict[str, list[Message]] = {}
        for m in msgs:
            by_session.setdefault(m.session_id, []).append(m)
            bad_latency = m.ttft_ms is not None and m.ttft_ms < 20
            bad_gen = (m.audio_duration_seconds is not None and m.audio_duration_seconds < 0.3) or \
                      (m.tokens_per_second is not None and m.tokens_per_second > 300)
            if bad_latency or bad_gen:
                m.ttft_ms = None
                if bad_gen:
                    m.tokens_per_second = None
                    m.audio_duration_seconds = None
                stats["metrics_cleared"] += 1

        for session_id, turns in by_session.items():
            sess = await s.get(ConversationSession, session_id)
            if sess is None:
                continue
            seen: list[str] = []
            stage = sess.final_stage or 1
            exit_line = False
            for m in turns:
                if m.speaker != "Simran":
                    continue
                norm = "".join(ch for ch in m.transcript.lower() if ch.isalnum())
                if not m.flagged_issue:
                    tag = note = None
                    if len(norm) >= 25 and norm in seen:
                        tag, note = "repeated_turn", "Auto: Simran repeated an earlier line word for word."
                    elif rules.INTERVIEW_PHRASE.search(m.transcript):
                        tag, note = "interview_phrase", "Auto: interview-style lead-in (ye bataiye)."
                    if tag:
                        m.flagged_issue, m.admin_tag, m.flag_note = True, tag, note
                        stats["flags_added"] += 1
                seen.append(norm)
                stage = max(stage, rules.detect_stage(m.transcript))
                exit_line = exit_line or rules.is_exit_line(m.transcript)
            ttfts = [m.ttft_ms for m in turns if m.speaker == "Simran" and m.ttft_ms is not None]
            sess.total_turns = len(turns)
            sess.avg_ttft_ms = round(sum(ttfts) / len(ttfts), 1) if ttfts else None
            sess.final_stage = min(4, stage)
            if exit_line and sess.exit_reason in (None, "user_disconnected", "abandoned"):
                sess.exit_reason = "two_decline_exit"
                stats["exit_relabelled"] += 1
            stats["sessions_updated"] += 1
        await s.commit()

        # Old rows copied the typed placeholder name (default "Rahul") into users.name. If the name equals the
        # typed identity and no conversation ever captured it, clear it so the dashboard shows Guest.
        users = (await s.execute(select(User))).scalars().all()
        for u in users:
            typed = u.identity.split("~", 1)[0]
            if u.name and u.name.strip().lower() == typed:
                captured = False
                rows = (await s.execute(select(Message.profile_fields_captured).join(
                    ConversationSession, Message.session_id == ConversationSession.id
                ).where(ConversationSession.user_id == u.id, Message.speaker == "User"))).all()
                for (fields,) in rows:
                    if isinstance(fields, dict) and fields.get("name"):
                        u.name, captured = fields["name"], True
                        break
                if not captured:
                    u.name = None
                stats["names_reset"] += 1
        await s.commit()

        # sessions that never got a single message
        await s.execute(update(ConversationSession).where(~ConversationSession.id.in_(list(by_session) or [""]))
                        .values(total_turns=0))
        await s.commit()
    return stats


async def _main() -> dict[str, Any]:
    db = await acquire_database()
    try:
        return await repair(db)
    finally:
        await release_database(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(asyncio.run(_main()))
