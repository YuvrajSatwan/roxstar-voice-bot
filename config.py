"""Configuration for STS Lab (Gemini 3.8 Live Speech-to-Speech)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

STS_AGENT_NAME = os.getenv("STS_AGENT_NAME", "sts-simran").strip()
STS_MODEL = os.getenv("STS_MODEL", "gemini-3.8-live").strip()
STS_VOICE = os.getenv("STS_VOICE", "Leda").strip()
STS_PORT = int(os.getenv("PORT", os.getenv("STS_PORT", "8001")))
STS_HOST = os.getenv("STS_HOST", "0.0.0.0").strip()


def _int_env(name: str, default: int) -> int:
    """Read an integer env var; a missing or garbled value falls back to the default."""
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class StsSettings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    gemini_api_key: str
    agent_name: str = STS_AGENT_NAME
    model: str = STS_MODEL
    voice: str = STS_VOICE
    port: int = STS_PORT
    host: str = STS_HOST
    # --- RoxStar integration (all OFF by default, so the standalone lab behaves exactly as before) ---
    # "standalone" = lab mode (anyone can get a token). "roxstar" = only real RoxStar users, own room only.
    auth_mode: str = "standalone"
    # Same secret the Auth service signs RoxStar login tokens with. Used ONLY to verify them.
    jwt_api_key: str = ""
    # Hard ceiling of simultaneous Simran voice sessions (protects Gemini / LiveKit quota and cost).
    max_concurrent_sessions: int = 50
    # How many new Simran sessions one user may start per hour.
    user_sessions_per_hour: int = 3
    # Simran wraps up warmly at this many seconds and powers off 60 s later (0 = no limit).
    max_session_sec: int = 480
    # rox-partyroom base URL (for the live duet list). Empty = no live list, Simran offers solo recording.
    partyroom_base_url: str = ""
    # rox-chat base URL (to cancel the 2-minute popup when a session starts). Empty = skip.
    chat_base_url: str = ""
    # Shared secret for Simran's internal calls to rox-partyroom and rox-chat.
    simran_internal_secret: str = ""

    @property
    def is_roxstar_mode(self) -> bool:
        return self.auth_mode == "roxstar"

    @classmethod
    def load(cls) -> StsSettings:
        load_dotenv()
        url = os.getenv("LIVEKIT_URL", "").strip()
        key = os.getenv("LIVEKIT_API_KEY", "").strip()
        secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        if not url:
            raise ValueError("LIVEKIT_URL is missing in environment.")
        if not key or not secret:
            raise ValueError("LIVEKIT_API_KEY or LIVEKIT_API_SECRET is missing.")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY is missing for Gemini 3.8 Live Speech-to-Speech.")

        return cls(
            livekit_url=url,
            livekit_api_key=key,
            livekit_api_secret=secret,
            gemini_api_key=gemini_key,
            agent_name=os.getenv("STS_AGENT_NAME", STS_AGENT_NAME).strip(),
            model=os.getenv("STS_MODEL", STS_MODEL).strip(),
            voice=os.getenv("STS_VOICE", STS_VOICE).strip(),
            port=int(os.getenv("PORT", os.getenv("STS_PORT", str(STS_PORT)))),
            host=os.getenv("STS_HOST", STS_HOST).strip(),
            auth_mode=os.getenv("STS_AUTH_MODE", "standalone").strip().lower() or "standalone",
            jwt_api_key=os.getenv("JWT_API_KEY", "").strip(),
            max_concurrent_sessions=_int_env("STS_MAX_CONCURRENT_SESSIONS", 50),
            user_sessions_per_hour=_int_env("STS_USER_SESSIONS_PER_HOUR", 3),
            max_session_sec=_int_env("STS_MAX_SESSION_SEC", 480),
            partyroom_base_url=os.getenv("PARTYROOM_BASE_URL", "").strip().rstrip("/"),
            chat_base_url=os.getenv("CHAT_BASE_URL", "").strip().rstrip("/"),
            simran_internal_secret=os.getenv("SIMRAN_INTERNAL_SECRET", "").strip(),
        )
