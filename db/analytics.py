"""Read-side queries for the admin dashboard: KPIs, funnel, sessions, users, export.

Aggregation that needs percentiles is done in Python so the same code runs on
SQLite and PostgreSQL. That is fine for lab and early-production volumes; move
heavy rollups into a materialised view if daily sessions reach the hundreds of
thousands.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EXIT_REASONS, ConversationSession, Message, User, iso

FLAG_REASONS = ("latency_spike", "hallucination", "persona_break", "missed_turn", "too_long", "interrupted", "other")
HANDOFF_REASONS = ("duet_handoff", "solo_handoff")


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    data = sorted(values)
    if len(data) == 1:
        return round(data[0], 1)
    k = (len(data) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(data) - 1)
    return round(data[lo] + (data[hi] - data[lo]) * (k - lo), 1)


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def parse_day(value: str | None, end: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        d = date.fromisoformat(value[:10])
    except ValueError:
        return None
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return dt + timedelta(days=1) if end else dt


def _like(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _apply_session_filters(stmt, f: dict[str, Any]):
    if f.get("exit_reason"):
        stmt = stmt.where(ConversationSession.exit_reason == f["exit_reason"])
    start, end = parse_day(f.get("date_from")), parse_day(f.get("date_to"), end=True)
    if start:
        stmt = stmt.where(ConversationSession.started_at >= start)
    if end:
        stmt = stmt.where(ConversationSession.started_at < end)
    if f.get("role"):
        stmt = stmt.where(User.musical_role.ilike(_like(f["role"]), escape="\\"))
    if f.get("q"):
        like = _like(f["q"])
        stmt = stmt.where(or_(User.name.ilike(like, escape="\\"), User.identity.ilike(like, escape="\\"),
                              ConversationSession.room_name.ilike(like, escape="\\")))
    if f.get("flagged"):
        flagged = select(Message.session_id).where(Message.flagged_issue.is_(True)).distinct()
        stmt = stmt.where(ConversationSession.id.in_(flagged))
    return stmt


# ----------------------------------------------------------------- KPIs
async def metrics(s: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    rows = (await s.execute(
        select(ConversationSession.id, ConversationSession.exit_reason, ConversationSession.final_stage,
               ConversationSession.duration_seconds)
        .where(ConversationSession.started_at >= since)
    )).all()
    total = len(rows)
    reasons = Counter((r.exit_reason or "in_progress") for r in rows)
    reached_pitch = sum(1 for r in rows if (r.final_stage or 1) >= 4)
    durations = [r.duration_seconds for r in rows if r.duration_seconds is not None]
    ttfts = [t for (t,) in (await s.execute(
        select(Message.ttft_ms).join(ConversationSession, Message.session_id == ConversationSession.id)
        .where(ConversationSession.started_at >= since, Message.speaker == "Simran", Message.ttft_ms.is_not(None))
    )).all()]
    flagged = (await s.execute(
        select(func.count(Message.id)).join(ConversationSession, Message.session_id == ConversationSession.id)
        .where(ConversationSession.started_at >= since, Message.flagged_issue.is_(True))
    )).scalar_one()
    return {
        "window_days": days,
        "total_conversations": total,
        "onboarding_completion_rate": _pct(reached_pitch, total),
        "duet_conversion_rate": _pct(reasons["duet_handoff"], total),
        "solo_conversion_rate": _pct(reasons["solo_handoff"], total),
        "two_decline_exit_rate": _pct(reasons["two_decline_exit"], total),
        "abandoned_rate": _pct(reasons["abandoned"], total),
        "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "ttft_p50_ms": percentile(ttfts, 50),
        "ttft_p95_ms": percentile(ttfts, 95),
        "ttft_samples": len(ttfts),
        "flagged_turns": flagged,
        "exit_reasons": {r: reasons.get(r, 0) for r in EXIT_REASONS},
    }


async def funnel(s: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    rows = (await s.execute(
        select(ConversationSession.id, ConversationSession.started_at, ConversationSession.final_stage,
               ConversationSession.exit_reason).where(ConversationSession.started_at >= since)
    )).all()
    total = len(rows)
    labels = ["Phase 1: Name and city", "Phase 2: Music", "Phase 3: Roxstar and coins", "Phase 4: Duet pitch"]
    stages = []
    prev = total
    for i, label in enumerate(labels, start=1):
        reached = sum(1 for r in rows if (r.final_stage or 1) >= i)
        stages.append({"stage": i, "label": label, "sessions": reached,
                       "pct_of_total": _pct(reached, total),
                       "drop_off_pct": _pct(prev - reached, prev) if i > 1 else 0.0})
        prev = reached
    handed = sum(1 for r in rows if r.exit_reason in HANDOFF_REASONS)
    stages.append({"stage": 5, "label": "Handoff to duet or solo", "sessions": handed,
                   "pct_of_total": _pct(handed, total), "drop_off_pct": _pct(prev - handed, prev)})

    ttft_rows = (await s.execute(
        select(ConversationSession.id, Message.ttft_ms)
        .join(Message, Message.session_id == ConversationSession.id)
        .where(ConversationSession.started_at >= since, Message.speaker == "Simran", Message.ttft_ms.is_not(None))
    )).all()
    day_of = {r.id: (r.started_at.date().isoformat() if r.started_at else "") for r in rows}
    daily: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = day_of[r.id]
        bucket = daily.setdefault(d, {"date": d, "sessions": 0, "reached_pitch": 0, "handoffs": 0, "ttfts": []})
        bucket["sessions"] += 1
        bucket["reached_pitch"] += 1 if (r.final_stage or 1) >= 4 else 0
        bucket["handoffs"] += 1 if r.exit_reason in HANDOFF_REASONS else 0
    for sid, ttft in ttft_rows:
        daily[day_of[sid]]["ttfts"].append(ttft)
    series = []
    for d in sorted(daily):
        b = daily[d]
        series.append({"date": d, "sessions": b["sessions"], "reached_pitch": b["reached_pitch"],
                       "handoffs": b["handoffs"], "conversion_pct": _pct(b["handoffs"], b["sessions"]),
                       "ttft_p50_ms": percentile(b["ttfts"], 50), "ttft_p95_ms": percentile(b["ttfts"], 95)})
    return {"window_days": days, "total": total, "stages": stages, "daily": series}


# ------------------------------------------------------------- sessions
async def list_sessions(s: AsyncSession, *, page: int = 1, page_size: int = 25, **filters: Any) -> dict[str, Any]:
    page, page_size = max(1, page), min(max(1, page_size), 200)
    base = select(ConversationSession, User).outerjoin(User, ConversationSession.user_id == User.id)
    base = _apply_session_filters(base, filters)
    count_stmt = _apply_session_filters(
        select(func.count(ConversationSession.id)).select_from(ConversationSession)
        .outerjoin(User, ConversationSession.user_id == User.id), filters)
    total = (await s.execute(count_stmt)).scalar_one()
    rows = (await s.execute(
        base.order_by(ConversationSession.started_at.desc()).limit(page_size).offset((page - 1) * page_size)
    )).all()
    ids = [sess.id for sess, _ in rows]
    flagged_ids: set[str] = set()
    if ids:
        flagged_ids = {sid for (sid,) in (await s.execute(
            select(Message.session_id).where(Message.session_id.in_(ids), Message.flagged_issue.is_(True)).distinct()
        )).all()}
    items = []
    for sess, user in rows:
        d = sess.to_dict()
        d.update(user_name=(user.name or user.identity) if user else None,
                 user_location=user.location if user else None,
                 musical_role=user.musical_role if user else None,
                 has_flagged_turns=sess.id in flagged_ids)
        items.append(d)
    return {"page": page, "page_size": page_size, "total": total, "items": items}


async def get_session(s: AsyncSession, session_id: str) -> dict[str, Any] | None:
    sess = await s.get(ConversationSession, session_id)
    if sess is None:
        return None
    user = await s.get(User, sess.user_id) if sess.user_id else None
    msgs = (await s.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.turn_index)
    )).scalars().all()
    return {"session": sess.to_dict(), "user": user.to_dict() if user else None,
            "messages": [m.to_dict() for m in msgs]}


async def update_session_review(s: AsyncSession, session_id: str, *, notes: str | None, rating: int | None) -> bool:
    sess = await s.get(ConversationSession, session_id)
    if sess is None:
        return False
    if notes is not None:
        sess.admin_notes = notes[:4000]
    if rating is not None:
        sess.feedback_rating = max(1, min(5, int(rating)))
    await s.commit()
    return True


async def flag_message(s: AsyncSession, message_id: str, *, flagged: bool = True,
                       tag: str | None = None, note: str | None = None) -> dict[str, Any] | None:
    msg = await s.get(Message, message_id)
    if msg is None:
        return None
    msg.flagged_issue = bool(flagged)
    msg.admin_tag = (tag or None) if flagged else None
    msg.flag_note = (note[:2000] if note else None) if flagged else None
    await s.commit()
    return msg.to_dict()


# ---------------------------------------------------------------- users
async def list_users(s: AsyncSession, *, page: int = 1, page_size: int = 25, city: str | None = None,
                     role: str | None = None, song: str | None = None, q: str | None = None) -> dict[str, Any]:
    page, page_size = max(1, page), min(max(1, page_size), 200)
    stmt = select(User)
    if city:
        stmt = stmt.where(User.location.ilike(_like(city), escape="\\"))
    if role:
        stmt = stmt.where(User.musical_role.ilike(_like(role), escape="\\"))
    if song:
        stmt = stmt.where(User.favorite_song.ilike(_like(song), escape="\\"))
    if q:
        stmt = stmt.where(or_(User.name.ilike(_like(q), escape="\\"), User.identity.ilike(_like(q), escape="\\")))
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    users = (await s.execute(
        stmt.order_by(User.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)
    )).scalars().all()

    everyone = (await s.execute(select(User.location, User.musical_role, User.favorite_song))).all()
    cities = Counter((c or "").strip().title() for c, _, _ in everyone if c and c.strip())
    roles = Counter((r or "").strip().lower() for _, r, _ in everyone if r and r.strip())
    songs = Counter((sg or "").strip().title() for _, _, sg in everyone if sg and sg.strip())
    return {
        "page": page, "page_size": page_size, "total": total,
        "items": [u.to_dict() for u in users],
        "breakdown": {
            "roles": [{"name": k, "count": v} for k, v in roles.most_common(10)],
            "top_cities": [{"name": k, "count": v} for k, v in cities.most_common(10)],
            "top_songs": [{"name": k, "count": v} for k, v in songs.most_common(10)],
        },
    }


# --------------------------------------------------------------- export
_EXPORT_COLUMNS = ["session_id", "room_name", "started_at", "exit_reason", "final_stage", "user_name", "user_location",
                   "musical_role", "turn_index", "speaker", "transcript", "timestamp", "ttft_ms",
                   "tokens_per_second", "audio_duration_seconds", "profile_fields_captured", "flagged_issue",
                   "admin_tag", "flag_note"]


async def export_rows(s: AsyncSession, *, limit: int = 20000, **filters: Any) -> list[dict[str, Any]]:
    stmt = (select(Message, ConversationSession, User)
            .join(ConversationSession, Message.session_id == ConversationSession.id)
            .outerjoin(User, ConversationSession.user_id == User.id))
    stmt = _apply_session_filters(stmt, filters)
    if filters.get("flagged_only"):
        stmt = stmt.where(Message.flagged_issue.is_(True))
    stmt = stmt.order_by(ConversationSession.started_at, Message.turn_index).limit(max(1, min(limit, 100000)))
    out = []
    for m, sess, user in (await s.execute(stmt)).all():
        out.append({
            "session_id": sess.id, "room_name": sess.room_name, "started_at": iso(sess.started_at),
            "exit_reason": sess.exit_reason, "final_stage": sess.final_stage,
            "user_name": (user.name or user.identity) if user else None,
            "user_location": user.location if user else None, "musical_role": user.musical_role if user else None,
            "turn_index": m.turn_index, "speaker": m.speaker, "transcript": m.transcript, "timestamp": iso(m.timestamp),
            "ttft_ms": m.ttft_ms, "tokens_per_second": m.tokens_per_second,
            "audio_duration_seconds": m.audio_duration_seconds,
            "profile_fields_captured": m.profile_fields_captured or {}, "flagged_issue": m.flagged_issue,
            "admin_tag": m.admin_tag, "flag_note": m.flag_note,
        })
    return out


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection in user-controlled transcripts."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        r = dict(r)
        r["profile_fields_captured"] = ";".join(f"{k}={v}" for k, v in (r.get("profile_fields_captured") or {}).items())
        writer.writerow({k: _csv_safe(v) for k, v in r.items()})
    return buf.getvalue()
