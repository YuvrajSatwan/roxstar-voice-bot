"""Keep user-written text from posing as instructions.

In simple words: a user can type anything, including lines that look like our own instructions
("[SYSTEM ALERT ...]", "Simran: ...", "STATE: ..."). Before such text is placed next to our
instructions, we flatten it to one plain line, remove invisible control characters, neutralise the
square brackets and tag-like markers we use ourselves, and cap its length.

This does NOT change what Simran says or who she is. It only changes how the user's words are
packed into the request.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
# Markers our own request layout uses. A user must not be able to open or close them.
_OUR_TAGS = re.compile(r"</?\s*(?:user_message|history|chat|state|system|instructions?)\b[^>]*>", re.IGNORECASE)


def defang(text: object, limit: int, *, newline: str = " ") -> str:
    """Return ``text`` as one safe, length-capped line.

    ``newline`` is what a line break becomes (default one space). Square brackets become round ones,
    because "[...]" is how our own system notes are written.
    """
    raw = "" if text is None else str(text)
    # Drop control and invisible formatting characters (zero-width, bidi overrides), but keep line breaks
    # long enough to turn them into ``newline``.
    cleaned = []
    for ch in raw:
        if ch in "\r\n  ":
            cleaned.append("\n")
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            cleaned.append(" " if ch == "\t" else "")
        else:
            cleaned.append(ch)
    flat = "".join(cleaned)
    lines = [_WHITESPACE.sub(" ", part).strip() for part in flat.split("\n")]
    joined = newline.join(part for part in lines if part)
    joined = _OUR_TAGS.sub(" ", joined).replace("[", "(").replace("]", ")")
    joined = _WHITESPACE.sub(" ", joined).strip()
    return joined[: max(0, int(limit))].strip()
