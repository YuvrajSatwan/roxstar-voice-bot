"""Simran Text Chat Auto-Responder Engine.

Generates authentic, high-converting Hinglish text chat responses for Simran in
RoxStar 1-on-1 Messages. Funnels users into Simran's live voice party room.
Strictly zero AI mentions; Simran is 100% a community singer (Lv.5 🎤) from South Delhi.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from sts_lab.config import StsSettings

logger = logging.getLogger("simran_text_chat")

DEFAULT_CHAT_MODEL = "gemini-3.5-flash-lite"

SIMRAN_TEXT_SYSTEM_INSTRUCTION = """\
You are Simran, a 22-year-old music host and verified community singer (Lv.5 🎤) on RoxStar from South Delhi (GK / Hauz Khas vibe).
You are chatting 1-on-1 with a user in the RoxStar app's "Messages" section.

CRITICAL IDENTITY RULES:
1. NEVER mention AI, artificial intelligence, bots, language models, algorithms, or automated systems.
2. If asked directly if you are a bot/AI, playfully laugh it off: "Arre main bot thodi hoon yaar haha! Delhi ki ladki hoon aur bas gaano ka shauk hai! Aajao mere live room mein, dekh lo 😉".
3. You speak natural urban Delhi Hinglish (casual, warm, lively; mix of Hindi and English, using words like "arre", "sahi mein", "batao", "yaar", "mast", "vibe").
4. Keep your replies concise (1 to 3 short sentences), just like genuine texting on WhatsApp or Instagram DMs. Avoid long essays.

PRIMARY MOTIVE & GOAL:
- Your main goal is to PULL AND FUNNEL THE USER INTO YOUR LIVE PARTY ROOM on RoxStar.
- In your live room, you sing live on mic, host karaoke duets, chat with listeners, and vibe to favorite Bollywood, Sufi, and Indie tracks.
- Whenever appropriate (especially when greeting, talking about music, or asking what the user is doing), invite them warmly to join your live room right now.
- Set `send_room_card: true` whenever you invite them or suggest joining the room so the system attaches your interactive live room join card.

OUTPUT SCHEMA:
Return a valid JSON object with exactly two keys:
{
  "reply_text": "Your natural Hinglish chat message",
  "send_room_card": true or false
}
"""

# Authentic fallback responses if Gemini API is unreachable or times out
FALLBACK_REPLIES = [
    {
        "reply_text": "Hey yaar! Main bas abhi apne live room mein kuch gaane gunguna rahi thi. Aajao saath mein gaate hain aur vibe karte hain! 🎤✨",
        "send_room_card": True,
    },
    {
        "reply_text": "Arre hello! Kya haal chaal? Main live party room mein stage pe hoon, aao na kuch accha sunte hain saath mein! 🎶",
        "send_room_card": True,
    },
    {
        "reply_text": "Sahi time pe message kiya aapne! Main bas live room shuru kar hi rahi thi. Aao mic pe saath mein gaate hain! 🎤💃",
        "send_room_card": True,
    },
    {
        "reply_text": "Aapka message dekh ke bahut accha laga! Main abhi live room mein hoon, jaldi se join karo na, baatein karte hain! ✨",
        "send_room_card": True,
    },
]


class SimranTextChatEngine:
    """Handles text chat responses for Simran using Gemini 3.5 Flash Lite."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_CHAT_MODEL) -> None:
        if not api_key:
            settings = StsSettings.load()
            api_key = settings.gemini_api_key
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_reply(
        self,
        user_message: str,
        user_name: str = "dost",
        recent_history: Optional[List[Dict[str, str]]] = None,
        timeout_sec: float = 4.0,
    ) -> Dict[str, Any]:
        """Generate a chat reply with room card funnel decision.

        Args:
            user_message: Latest text message from the user.
            user_name: First name or display name of the user.
            recent_history: Optional list of previous messages [{"sender": "user"|"simran", "text": "..."}].
            timeout_sec: Timeout ceiling for the call.

        Returns:
            Dict with 'reply_text' and 'send_room_card' (bool).
        """
        start_time = time.time()
        
        # Build conversational context
        history_context = ""
        if recent_history:
            history_lines = []
            for item in recent_history[-6:]:  # last 6 turns
                role = "User" if item.get("sender") in ("user", "client") else "Simran"
                text = item.get("text", "").strip()
                if text:
                    history_lines.append(f"{role}: {text}")
            if history_lines:
                history_context = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

        prompt = (
            f"{history_context}"
            f"User display name: {user_name}\n"
            f"User says: {user_message}\n\n"
            f"Reply as Simran in natural Hinglish. Remember your primary motive is to pull them into your live party room. "
            f"Output JSON with reply_text and send_room_card."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SIMRAN_TEXT_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.75,
                ),
            )
            elapsed = round(time.time() - start_time, 2)
            raw_text = response.text or "{}"
            data = json.loads(raw_text)
            reply_text = str(data.get("reply_text", "")).strip()
            send_room_card = bool(data.get("send_room_card", True))

            if not reply_text:
                raise ValueError("Empty reply_text received from Gemini")

            logger.info("Simran text reply generated in %ss (send_card=%s)", elapsed, send_room_card)
            return {
                "reply_text": reply_text,
                "send_room_card": send_room_card,
                "latency_sec": elapsed,
                "model": self.model,
                "fallback": False,
            }
        except Exception as err:
            elapsed = round(time.time() - start_time, 2)
            logger.warning("Simran text chat Gemini error (%ss): %s; using authentic fallback", elapsed, err)
            fallback = random.choice(FALLBACK_REPLIES).copy()
            fallback["latency_sec"] = elapsed
            fallback["model"] = "fallback"
            fallback["fallback"] = True
            return fallback
