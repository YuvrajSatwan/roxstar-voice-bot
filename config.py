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
        )
