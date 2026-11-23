"""Configuration for STS Lab (Gemini 3.8 Live Speech-to-Speech)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

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


def _float_env(name: str, default: float) -> float:
    """Read a number env var; a missing or garbled value falls back to the default."""
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    """Read a true/false env var. Empty or missing = the default; only an explicit value flips it."""
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _digits_only(value: str) -> str:
    """A post id is a number. Anything else (typo, URL pasted by mistake) turns the feature off."""
    value = (value or "").strip()
    return value if value.isdigit() else ""


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
    # Head start: the app calls POST /prewarm when the user taps "join", so Simran is already in the
    # room (and her Gemini session is ready) while the page loads. OFF by default.
    prewarm_enabled: bool = False
    # If nobody joins a pre-warmed room within this many seconds, Simran leaves (saves Gemini cost).
    prewarm_idle_sec: int = 20
    # One conversation per user: once Simran has talked to a user, coming back shows "session expired".
    single_session_per_user: bool = False
    # Final handoff: at the end of the conversation Simran signs off and the app opens this duet POST
    # (a RoxStar post id, e.g. Harshit singing "Tum Hi Ho"). Empty = feature OFF (normal duet pitch).
    # The id is per environment (production and staging have different posts), so it lives in the env.
    duet_post_id: str = ""
    duet_host_name: str = "Harshit"
    duet_song_title: str = "Tum Hi Ho"
    # --- Protection for the text-chat endpoint and LiveKit calls (safe defaults; each has an off switch) ---
    # The text-chat endpoint refuses every request while SIMRAN_INTERNAL_SECRET is unset. Set false ONLY to get
    # the old "open when no secret" behaviour back (for example an isolated local lab).
    require_internal_secret: bool = True
    # Overall time for one Gemini text reply, retries included, in seconds. 0 = no timeout. rox-chat waits the
    # same 20 s (SIMRAN_HTTP_TIMEOUT_MS), so the engine keeps a small margin back and answers just before it.
    chat_timeout_sec: float = 20.0
    # Backup model for text replies when the main one is overloaded or out of quota. "off" = no backup.
    chat_fallback_model: str = "gemini-3.1-flash-lite"
    # Open the Gemini connection at start-up so the first user does not pay for it.
    chat_warmup: bool = True
    # Text replies being generated at the same moment. More get a quick "busy" (rox-chat then uses its own
    # fallback). 0 = no cap.
    chat_max_concurrent: int = 32
    # Text replies per user per minute. 0 = no limit.
    chat_replies_per_min: int = 30
    # Time one LiveKit job (and the wait for the global dispatch lock) may take, in seconds. 0 = no timeout.
    livekit_timeout_sec: float = 8.0

    @property
    def is_roxstar_mode(self) -> bool:
        return self.auth_mode == "roxstar"

    @classmethod
    def load(cls) -> StsSettings:
        load_dotenv(dotenv_path=_ENV_PATH)
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
            prewarm_enabled=os.getenv("STS_PREWARM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
            prewarm_idle_sec=max(5, _int_env("STS_PREWARM_IDLE_SEC", 20)),
            single_session_per_user=os.getenv("STS_SINGLE_SESSION_PER_USER", "false").strip().lower() in {"1", "true", "yes", "on"},
            duet_post_id=_digits_only(os.getenv("STS_DUET_POST_ID", "")),
            duet_host_name=os.getenv("STS_DUET_HOST_NAME", "Harshit").strip() or "Harshit",
            duet_song_title=os.getenv("STS_DUET_SONG_TITLE", "Tum Hi Ho").strip() or "Tum Hi Ho",
            require_internal_secret=_bool_env("STS_REQUIRE_INTERNAL_SECRET", True),
            chat_timeout_sec=_float_env("STS_CHAT_TIMEOUT_SEC", 20.0),
            chat_fallback_model=os.getenv("STS_CHAT_FALLBACK_MODEL", "gemini-3.1-flash-lite").strip(),
            chat_warmup=_bool_env("STS_CHAT_WARMUP", True),
            chat_max_concurrent=_int_env("STS_CHAT_MAX_CONCURRENT", 32),
            chat_replies_per_min=_int_env("STS_CHAT_REPLIES_PER_MIN", 30),
            livekit_timeout_sec=_float_env("STS_LIVEKIT_TIMEOUT_SEC", 8.0),
        )
