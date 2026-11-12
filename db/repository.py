"""Write-side repository functions. Every function takes an ``AsyncSession``.

All writes are idempotent so the recorder can safely retry an operation after a
transient database failure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConversationSession, Message, User, utcnow

LIST_FIELDS = frozenset({"hobbies", "music_taste"})
SCALAR_FIELDS = frozenset({
    "name", "location", "occupation", "favorite_song", "musical_role",
    "singing_comfort", "referral_source", "expectations",
})
_LIMITS = {"name": 128, "location": 128, "occupation": 256, "favorite_song": 256,
           "musical_role": 64, "singing_comfort": 64, "referral_source": 128, "expectations": 256}


def clean_identity(identity: str | None) -> str:
    return (identity or "guest").strip().lower()[:128] or "guest"


async def get_or_create_user(s: AsyncSession, identity: str | None) -> User:
    key = clean_identity(identity)
    user = (await s.execute(select(User).where(User.identity == key))).scalar_one_or_none()
    if user is None:
        # The name typed in the web box is only a placeholder (it defaults to "Rahul"), so the real name
        # stays empty until Simran learns it from the conversation.
        user = User(identity=key, name=None)
        s.add(user)
        await s.flush()
    return user


async def create_session(
    s: AsyncSession, *, session_id: str, room_name: str, user_id: str | None,
    model: str | None, voice: str | None, started_at: datetime,
) -> None:
    if await s.get(ConversationSession, session_id) is not None:
        return
    s.add(ConversationSession(
        id=session_id, room_name=room_name[:128], user_id=user_id,
        model=model, voice=voice, started_at=started_at,
    ))


async def set_session_user(s: AsyncSession, session_id: str, user_id: str) -> None:
    await s.execute(update(ConversationSession).where(ConversationSession.id == session_id).values(user_id=user_id))


async def add_message(s: AsyncSession, **values: Any) -> None:
    if await s.get(Message, values["id"]) is not None:
        return
    s.add(Message(**values))


async def update_message(s: AsyncSession, message_id: str, **values: Any) -> None:
    await s.execute(update(Message).where(Message.id == message_id).values(**values))


async def apply_profile_field(s: AsyncSession, user_id: str, field: str, value: str) -> None:
    user = await s.get(User, user_id)
    if user is None:
        return
    value = value.strip()
    if not value:
        return
    if field in LIST_FIELDS:
        current = list(getattr(user, field) or [])
        if value not in current:
            current.append(value[:128])
            setattr(user, field, current)
    elif field in SCALAR_FIELDS:
        setattr(user, field, value[: _LIMITS.get(field, 256)])
    user.updated_at = utcnow()


async def set_coin_balance(s: AsyncSession, user_id: str, balance: int) -> None:
    await s.execute(update(User).where(User.id == user_id).values(coin_balance=balance, updated_at=utcnow()))


async def close_session(
    s: AsyncSession, *, session_id: str, user_id: str | None, ended_at: datetime,
    duration_seconds: float, exit_reason: str, final_stage: int,
    avg_ttft_ms: float | None, total_turns: int, is_onboarded: bool,
) -> None:
    await s.execute(
        update(ConversationSession).where(ConversationSession.id == session_id).values(
            ended_at=ended_at, duration_seconds=round(duration_seconds, 2), exit_reason=exit_reason,
            final_stage=final_stage, avg_ttft_ms=avg_ttft_ms, total_turns=total_turns,
        )
    )
    if user_id and is_onboarded:
        await s.execute(update(User).where(User.id == user_id).values(is_onboarded=True, updated_at=utcnow()))
