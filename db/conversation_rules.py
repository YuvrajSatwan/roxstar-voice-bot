"""Pure text rules used by the recorder (no I/O, easy to unit test).

The live model decides when to call ``save_profile``, and it sometimes forgets.
These rules read the transcript so the dashboard still shows the funnel phase,
the likely exit reason and (clearly marked as "auto") the answer to a profile
question Simran has just asked.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------- funnel phase
_STAGE_MARKERS: list[tuple[int, tuple[str, ...]]] = [
    (4, ("live duet stage", "duet stage pe", "kiske saath jam", "gaa raha hai, aur", "gaa rahe hain live")),
    (3, ("roxstar pe log", "live duets gaate", "sunne aaye ho ya khud", "welcome coins", "free coins")),
    (2, ("sunte ho ya", "gaane sirf sunte", "gunguna lete", "bathroom singer")),
]


def detect_stage(simran_text: str) -> int:
    """Funnel phase (1 to 4) implied by something Simran said. 1 means no marker found."""
    low = simran_text.lower()
    for stage, markers in _STAGE_MARKERS:
        if any(m in low for m in markers):
            return stage
    return 1


# --------------------------------------------------------------------- exit lines
_EXIT_MARKERS = ("swiggy", "chai ke liye", "client ka", "laptop chaar", "ritika ka phone", "deadline yaad", "doorbell")


def is_exit_line(simran_text: str) -> bool:
    low = simran_text.lower()
    return "bye" in low and any(m in low for m in _EXIT_MARKERS)


# ----------------------------------------------------------- which question was asked
_TOPIC_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("name", ("naam kya", "apna naam", "aapka naam")),
    ("location", ("kis shehar", "kahan se ho", "kahan se hain")),
    ("favorite_song", ("dimaag mein atka", "gaana loop pe")),
    ("musical_role", ("sunte ho ya", "sirf sunte", "gunguna lete")),
    ("singing_comfort", ("bathroom singer",)),
    ("expectations", ("sunne aaye ho ya khud", "khud bhi try karne", "kya karne aaye")),
    ("referral_source", ("kaise pahunche", "roxstar tak", "kaise pata chala")),
    ("hobbies", ("free time",)),
    ("occupation", ("job ya college", "kya karte ho", "kya karte hain", "job kis field", "role kya", "kya padh rahe",
                    "kaunsi stream", "kis cheez ka business", "business mein kya", "kya bana rahe", "kis field mein")),
    ("music_taste", ("kis tarah ke gaane", "kis type ke gaane", "kaunse gaane", "kaunsa gaana", "kaunse artist",
                     "gaane gungunana", "loop pe rehte")),
]


def detect_question_topic(simran_text: str) -> str | None:
    """Profile field Simran's LAST question in this turn is asking about, if any."""
    if "?" not in simran_text:
        return None
    head = simran_text[: simran_text.rfind("?")]
    last_sentence = re.split(r"[.!]", head)[-1].lower()
    for topic, markers in _TOPIC_MARKERS:
        if any(m in last_sentence for m in markers):
            return topic
    return None


# ------------------------------------------------------------------ answer cleaning
_FILLER = {
    "name": {"mera", "meri", "naam", "name", "is", "hai", "main", "mai", "hoon", "hun", "my", "i", "am", "ji", "toh", "to"},
    "location": {"mai", "main", "me", "mein", "se", "hu", "hun", "hoon", "rehta", "rehti", "rahta", "rahti", "from",
                 "i", "am", "in", "live", "ka", "ki", "toh", "to", "abhi", "filhal", "fillhal", "hai", "reh", "raha",
                 "rahi", "rha", "rhi", "city", "shehar"},
}
_NO_ANSWER = {"", "o", "ok", "okay", "hmm", "hm", "mhm", "haan", "han", "ha", "nahi", "nhi", "no", "nope", "pata nahi",
              "pta nhi", "kuch nahi", "chhodo", "chhodo yaar", "rehne do", "yes", "yeah", "acha", "achha", "oh", "ohh"}


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text.strip(" .,!?;:।\"'")


def clean_answer(field: str, text: str) -> str | None:
    """Short, storable value for a profile field from the user's reply, or None if it is not an answer."""
    text = _tidy(text)
    if text.lower() in _NO_ANSWER or len(text) < 2:
        return None
    if field in _FILLER:
        words = [w for w in re.split(r"\s+", text) if w.lower().strip(".,!?") not in _FILLER[field]]
        if not words or len(words) > 4:
            return None
        return " ".join(words).title()
    if field == "musical_role":
        low = text.lower()
        if any(k in low for k in ("dono", "both", "donon")):
            return "both"
        if any(k in low for k in ("sirf sun", "sunta", "sunti", "listen", "sunne")):
            return "listener"
        if any(k in low for k in ("gaata", "gaati", "sing", "gunguna", "gana gata")):
            return "singer"
        return text[:60]
    return text[:120]


AUTO_KEY = "_auto"

INTERVIEW_PHRASE = re.compile(r"\b(?:aur\s+)?ye\s+bata(?:iye|yeiye|o)\b|\bbatayeiye\b", re.IGNORECASE)
