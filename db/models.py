"""SQLAlchemy ORM models for the Simran conversation persistence engine.

Works on SQLite (local dev) and PostgreSQL (production). JSON columns use the
generic ``JSON`` type, which maps to JSON on SQLite and JSONB-compatible JSON on
PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EXIT_REASONS = (
    "duet_handoff",
    "solo_handoff",
    "two_decline_exit",
    "user_disconnected",
    "abandoned",
)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    """ISO-8601 in UTC. SQLite returns naive datetimes, which we store as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # LiveKit participant identity. Today this is the typed name, so it is a weak key.
    identity: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(128), index=True)
    occupation: Mapped[str | None] = mapped_column(String(256))
    hobbies: Mapped[list[str]] = mapped_column(JSON, default=list)
    music_taste: Mapped[list[str]] = mapped_column(JSON, default=list)
    favorite_song: Mapped[str | None] = mapped_column(String(256), index=True)
    musical_role: Mapped[str | None] = mapped_column(String(64), index=True)
    singing_comfort: Mapped[str | None] = mapped_column(String(64))
    referral_source: Mapped[str | None] = mapped_column(String(128))
    expectations: Mapped[str | None] = mapped_column(String(256))
    coin_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list["ConversationSession"]] = relationship(back_populates="user")

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.id,
            "identity": self.identity,
            "name": self.name,
            "location": self.location,
            "occupation": self.occupation,
            "hobbies": list(self.hobbies or []),
            "music_taste": list(self.music_taste or []),
            "favorite_song": self.favorite_song,
            "musical_role": self.musical_role,
            "singing_comfort": self.singing_comfort,
            "referral_source": self.referral_source,
            "expectations": self.expectations,
            "coin_balance": self.coin_balance,
            "is_onboarded": self.is_onboarded,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class ConversationSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_name: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(32), index=True)
    final_stage: Mapped[int] = mapped_column(Integer, default=1)
    avg_ttft_ms: Mapped[float | None] = mapped_column(Float)
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(64))
    voice: Mapped[str | None] = mapped_column(String(64))
    feedback_rating: Mapped[int | None] = mapped_column(Integer)
    admin_notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", order_by="Message.turn_index", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.id,
            "room_name": self.room_name,
            "user_id": self.user_id,
            "started_at": iso(self.started_at),
            "ended_at": iso(self.ended_at),
            "duration_seconds": self.duration_seconds,
            "exit_reason": self.exit_reason,
            "final_stage": self.final_stage,
            "avg_ttft_ms": self.avg_ttft_ms,
            "total_turns": self.total_turns,
            "model": self.model,
            "voice": self.voice,
            "feedback_rating": self.feedback_rating,
            "admin_notes": self.admin_notes,
        }


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_turn", "session_id", "turn_index"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    turn_index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(16))  # "Simran" | "User"
    transcript: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ttft_ms: Mapped[float | None] = mapped_column(Float)
    tokens_per_second: Mapped[float | None] = mapped_column(Float)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float)
    profile_fields_captured: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    flagged_issue: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    admin_tag: Mapped[str | None] = mapped_column(String(64))
    flag_note: Mapped[str | None] = mapped_column(Text)

    session: Mapped[ConversationSession] = relationship(back_populates="messages")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "speaker": self.speaker,
            "transcript": self.transcript,
            "timestamp": iso(self.timestamp),
            "ttft_ms": self.ttft_ms,
            "tokens_per_second": self.tokens_per_second,
            "audio_duration_seconds": self.audio_duration_seconds,
            "profile_fields_captured": self.profile_fields_captured or {},
            "flagged_issue": self.flagged_issue,
            "admin_tag": self.admin_tag,
            "flag_note": self.flag_note,
        }
