"""Pure text rules used by the recorder (no I/O, easy to unit test).

The live model decides when to call ``save_profile``, and it sometimes forgets.
These rules read the transcript so the dashboard still shows the funnel phase,
the likely exit reason and (clearly marked as "auto") the answer to a profile
question Simran has just asked.

Markers cover Roman Hinglish and the common Devanagari spellings, because the
input transcription can return either script.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------- funnel phase
_STAGE_MARKERS: list[tuple[int, tuple[str, ...]]] = [
    (4, ("live duet stage", "duet stage pe", "kiske saath jam", "gaa raha hai, aur", "gaa rahe hain live",
         "गा रहा है", "गा रहे हैं लाइव")),
    (3, ("roxstar pe log", "live duets gaate", "sunne aaye ho ya khud", "welcome coins", "free coins",
         "coins aa gaye", "coins mile", "वेलकम कॉइन", "फ्री कॉइन")),
    (2, ("sunte ho ya", "gaane sirf sunte", "gunguna lete", "bathroom singer", "सुनते हो या", "गुनगुना")),
]


def detect_stage(simran_text: str) -> int:
    """Funnel phase (1 to 4) implied by something Simran said. 1 means no marker found."""
    low = simran_text.lower()
    for stage, markers in _STAGE_MARKERS:
        if any(m in low for m in markers):
            return stage
    return 1


# --------------------------------------------------------------------- exit lines
_EXIT_MARKERS = ("swiggy", "chai ke liye", "client ka", "laptop chaar", "ritika ka phone", "deadline yaad", "doorbell",
                 "स्विगी", "चाय के लिए", "क्लाइंट", "डेडलाइन", "डोरबेल")
_LEAVING = re.compile(r"chalti|nikalti|bhaagti|bhagti|चलती|निकलती|भागती")
_BYE = re.compile(r"\bbye\b|बाय")


def is_exit_line(simran_text: str) -> bool:
    """True for one of Simran's leave-taking excuses: a bye, a known excuse and a "I'm leaving" verb, and no question."""
    low = simran_text.lower()
    if "?" in low or not _BYE.search(low) or not _LEAVING.search(low):
        return False
    return any(m in low for m in _EXIT_MARKERS)


# ----------------------------------------------------------- which question was asked
_TOPIC_MARKERS: list[tuple[str, tuple[str, ...]]] = [
    ("name", ("naam kya", "apna naam", "aapka naam", "नाम क्या", "आपका नाम", "अपना नाम")),
    ("location", ("kis shehar", "kis sheher", "kaunse shehar", "kaunse sheher", "kahan se ho", "kahan se hain",
                  "kahan rehte", "kahan rehti", "कहाँ से", "कहां से", "किस शहर")),
    ("favorite_song", ("dimaag mein atka", "gaana loop pe")),
    ("musical_role", ("sunte ho ya", "sunte hain ya", "sirf sunte", "gunguna lete", "सुनते हो या")),
    ("singing_comfort", ("bathroom singer",)),
    ("expectations", ("sunne aaye ho ya khud", "khud bhi try karne", "kya karne aaye")),
    ("referral_source", ("kaise pahunche", "roxstar tak", "kaise pata chala", "kahan se pata chala")),
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
    last_sentence = re.split(r"[.!।]", head)[-1].lower()
    for topic, markers in _TOPIC_MARKERS:
        if any(m in last_sentence for m in markers):
            return topic
    return None


# ------------------------------------------------------------------ answer cleaning
_FILLER = {
    "name": {"mera", "meri", "naam", "name", "is", "hai", "main", "mai", "hoon", "hun", "my", "i", "am", "ji", "toh",
             "to", "haan", "han", "ha", "yes", "yeah", "boliye", "bolo", "hello", "hi", "hey", "ok", "okay", "sure",
             "achha", "accha", "so", "well", "um", "umm", "hmm"},
    "location": {"mai", "main", "me", "mein", "se", "hu", "hun", "hoon", "rehta", "rehti", "rahta", "rahti", "from",
                 "i", "am", "in", "live", "ka", "ki", "toh", "to", "abhi", "filhal", "fillhal", "hai", "reh", "raha",
                 "rahi", "rha", "rhi", "city", "shehar", "hi", "bhi", "ji", "haan", "han", "ha", "yes", "hee"},
}
_NO_ANSWER = {"", "o", "ok", "okay", "hmm", "hm", "mhm", "haan", "han", "ha", "nahi", "nhi", "no", "nope", "pata nahi",
              "pta nhi", "kuch nahi", "chhodo", "chhodo yaar", "rehne do", "yes", "yeah", "acha", "achha", "oh", "ohh",
              "pata nhi", "nahin", "kuch bhi", "kuch nhi", "पता नहीं", "नहीं", "हाँ", "हां"}
# A refusal or a deflection is not an answer, whatever the field is.
_REFUSAL = re.compile(
    r"\b(?:nahi|nhi|nahin|no|na)\s+(?:batana|bataunga|bataungi|bataoonga|bolna|bata|batau|batani|batani hai|dena|chahta|chahti)\b"
    r"|\bkyun?\s+bata|\bkyu\s+bata|\brehne\s+do\b|\bchh?odo\b|\bpata\s+n(?:ahi|hi)\b|\bn(?:ahi|hi)\s+pat[ae]\b|\bpta\s+nhi\b|\bskip\b|\bprivate\b"
    r"|\baap\s+(?:pehle\s+)?bata|\bpehle\s+aap\b|\bdon'?t\s+want\b|\bnot\s+telling\b"
    r"|नहीं\s*बताना|क्यों\s*बताऊं|छोड़ो|रहने\s*दो",
    re.IGNORECASE,
)
_CONTRAST = re.compile(r"\b(?:par|lekin|but|magar)\b", re.IGNORECASE)


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text.strip(" .,!?;:।\"'")


def clean_answer(field: str, text: str) -> str | None:
    """Short, storable value for a profile field from the user's reply, or None if it is not an answer."""
    text = _tidy(text)
    if text.lower() in _NO_ANSWER or len(text) < 2 or _REFUSAL.search(text):
        return None
    if field in _FILLER:
        if field == "location":
            text = _CONTRAST.split(text, maxsplit=1)[0].strip()  # "Noida mein hoon par Patna se" -> current city
        words = [w for w in re.split(r"\s+", text) if w.lower().strip(".,!?") not in _FILLER[field]]
        if not words or len(words) > 4:
            return None
        return " ".join(words).title()
    if field == "musical_role":
        low = text.lower()
        if any(k in low for k in ("dono", "both", "donon")):
            return "both"
        sings = bool(re.search(r"gaata|gaati|\bsing|gunguna|gana gata", low)) and not re.search(r"gaat[ai]\s+nahi", low)
        listens = bool(re.search(r"sirf sun|sunta|sunti|listen|sunne", low))
        not_listen = bool(re.search(r"sun(?:ta|ti|ne)?\s+(?:hi\s+)?nahi|not\s+(?:just\s+)?listen", low))
        if sings and (not_listen or not listens):
            return "singer"
        if sings and listens:
            return "both"
        if listens:
            return "listener"
        return text[:60]
    return text[:120]


AUTO_KEY = "_auto"

# "ye bataiye", "yeh bata do", "aur ye bataayiye": an interview-style lead-in the persona forbids.
INTERVIEW_PHRASE = re.compile(r"\b(?:aur\s+)?yeh?\s+bata(?:a)?\s*(?:iye|yiye|yeiye|o|do)\b|\bbatayeiye\b", re.IGNORECASE)
