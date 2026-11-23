"""Tests for Simran Text Chat Auto-Responder and /api/simran/chat-reply."""

import json
import re
from unittest.mock import patch

from sts_lab.text_chat import (
    SimranTextChatEngine,
    FALLBACK_REPLIES,
    SIMRAN_TEXT_SYSTEM_INSTRUCTION,
    decide_room_card,
    normalize_history,
)


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


def test_fallback_structure():
    """Fallbacks match the schema, use 'aap', never say tum, and are not all cards."""
    for item in FALLBACK_REPLIES:
        assert isinstance(item["reply_text"], str)
        assert len(item["reply_text"]) > 10
        assert isinstance(item["send_room_card"], bool)
        assert not re.search(r"\b(tum|tu|tumhara|tera)\b", item["reply_text"], re.IGNORECASE)
        assert "bot" not in item["reply_text"].lower()
    assert any(i["send_room_card"] for i in FALLBACK_REPLIES)
    assert any(not i["send_room_card"] for i in FALLBACK_REPLIES)


def test_engine_generate_reply_success():
    """Engine parses the Gemini JSON response."""
    engine = SimranTextChatEngine(api_key="fake-key")
    payload = {"reply_text": "Main abhi live hoon, aaiye na wahin baat karte hain.", "send_room_card": True}
    with patch.object(
        engine.client.models, "generate_content", return_value=DummyResponse(json.dumps(payload))
    ):
        result = engine.generate_reply(
            user_message="Hey Simran kya kar rahi ho?",
            user_name="Aman",
            recent_history=[{"sender": "user", "text": "Hi"}],
        )
        assert result["reply_text"] == payload["reply_text"]
        assert result["send_room_card"] is True
        assert result["fallback"] is False


def test_engine_fallback_on_exception():
    engine = SimranTextChatEngine(api_key="fake-key")
    with patch.object(
        engine.client.models, "generate_content", side_effect=RuntimeError("Quota exceeded")
    ):
        result = engine.generate_reply(user_message="Hello")
        assert result["fallback"] is True
        assert result["model"] == "fallback"
        assert len(result["reply_text"]) > 0


def test_engine_fallback_on_empty_text():
    engine = SimranTextChatEngine(api_key="fake-key")
    with patch.object(
        engine.client.models, "generate_content", return_value=DummyResponse("")
    ):
        result = engine.generate_reply(user_message="Hello")
        assert result["fallback"] is True


def test_prompt_persona_and_goal():
    """Prompt keeps the persona rules and the live-room goal, and never admits to AI."""
    p = SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "NEVER mention or hint at AI" in p
    assert "ALWAYS \"aap\"" in p
    assert "YOUR ONE GOAL: GET THEM INTO YOUR LIVE ROOM" in p
    assert "send_room_card" in p
    assert "South Delhi" not in p  # old, different persona
    assert "Lv.5" not in p


def test_normalize_history_accepts_both_shapes():
    history = normalize_history(
        [
            {"sender": "user", "text": "Hi"},
            {"role": "assistant", "content": "Hey!"},
            {"role": "user", "content": "kya haal"},
            {"role": "user", "content": "   "},
        ],
        user_message="kya haal",
    )
    assert [h["sender"] for h in history] == ["user", "simran"]
    assert history[1]["text"] == "Hey!"


def test_normalize_history_keeps_card_flag():
    history = normalize_history([{"sender": "simran", "text": "Aaiye room mein", "card": True}])
    assert history[0]["card"] is True


def test_room_card_cooldown():
    shown = [{"sender": "simran", "text": "aaiye room mein", "card": True}]
    assert decide_room_card(True, "hmm", shown) is False       # just shown, no interest
    assert decide_room_card(True, "haan kaise join karu", shown) is True  # interested
    assert decide_room_card(True, "hmm", []) is True            # never shown
    assert decide_room_card(False, "haan", []) is False         # model said no


def test_prompt_forbids_interviewing_and_pushes_the_live_room():
    p = SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "DO NOT interview them" in p
    assert "kya sunte ho" in p  # named as something she must not ask
    assert "live" in p and "send_room_card" in p


def test_prompt_answers_every_question_and_leads_the_whole_chat_to_the_room():
    from sts_lab.text_chat import conversation_state

    p = SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "REPLY TO EVERYTHING" in p
    assert "Never dodge a question" in p
    assert "THE WHOLE CONVERSATION LEADS TO THE ROOM" in p
    # After the first invite she keeps steering back to the room instead of just "chatting normally".
    invited = normalize_history([{"sender": "simran", "text": "Main live hoon abhi, aaiye na", "card": True}])
    state = conversation_state(invited, "kya kar rahi ho")
    assert "already invited" in state and "back to the room" in state


def test_no_fallback_interviews_the_user_about_music():
    for item in FALLBACK_REPLIES:
        low = item["reply_text"].lower()
        assert "gaana" not in low and "sunte ho" not in low and "gaate bhi" not in low


def test_state_line_first_reply_then_must_invite_then_already_invited():
    from sts_lab.text_chat import conversation_state

    assert "FIRST reply" in conversation_state([])
    welcome_only = normalize_history([{"sender": "simran", "text": "Hey! Main Simran 👋 Tap to talk to me!", "card": True}])
    assert "FIRST reply" in conversation_state(welcome_only)  # the welcome card is not a reply of hers
    no_invite = normalize_history([
        {"sender": "simran", "text": "Hey! Main Simran 👋 Tap to talk to me!", "card": True},
        {"sender": "user", "text": "hi"},
        {"sender": "simran", "text": "Hey! Kaise hain?"},
    ])
    assert "have not invited them" in conversation_state(no_invite)
    invited = normalize_history([
        {"sender": "user", "text": "hi"},
        {"sender": "simran", "text": "Main live hoon, aaiye", "card": True},
    ])
    assert "already invited" in conversation_state(invited)


def test_welcome_card_does_not_block_her_first_invite():
    welcome = normalize_history([{"sender": "simran", "text": "Hey! Main Simran 👋 Tap to talk to me!", "card": True}])
    assert decide_room_card(True, "hi", welcome) is True


def test_a_no_or_later_never_gets_a_join_button_right_after():
    from sts_lab.text_chat import conversation_state, user_declined

    for msg in ("nahi abhi nahi", "baad mein dekhta hoon", "not now", "no thanks", "rehne do"):
        assert user_declined(msg), msg
        assert decide_room_card(True, msg, []) is False
        assert "Do NOT invite" in conversation_state([], msg)
    for msg in ("haan aata hoon", "kaise join karu", "chalo"):
        assert not user_declined(msg), msg


def test_abhi_alone_is_not_interest():
    shown = [{"sender": "simran", "text": "aaiye room mein", "card": True}]
    assert decide_room_card(True, "abhi busy hoon", shown) is False


def test_prompt_bans_coins_and_music_and_keeps_context_rules():
    p = SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "NEVER mention coins" in p
    assert "MUSIC IS FINE WHEN THEY BRING IT UP" in p
    assert "never start the music topic yourself" in p.lower()
    assert "Stay in context" in p
    assert "50 welcome coins" not in p
    assert "karaoke app" not in p


def test_reply_mentioning_coins_or_music_falls_back():
    from sts_lab.text_chat import mentions_banned_topic

    assert mentions_banned_topic("Room mein 50 coins mil rahe hain")
    assert mentions_banned_topic("Reward milega, aaiye na")
    # Music talk is allowed now (she answers it when the user asks), so it is no longer replaced by a canned line.
    assert not mentions_banned_topic("Haan mujhe purane Bollywood gaane bahut pasand hain, live pe baat karte hain.")
    assert not mentions_banned_topic("Main abhi live hoon, aaiye na wahin baat karte hain.")

    engine = SimranTextChatEngine(api_key="fake-key")
    payload = {"reply_text": "Aaiye room mein, 50 coins wait kar rahe hain!", "send_room_card": True}
    with patch.object(
        engine.client.models, "generate_content", return_value=DummyResponse(json.dumps(payload))
    ):
        result = engine.generate_reply(user_message="hi")
    assert result["fallback"] is True
    assert "coin" not in result["reply_text"].lower()


def test_plain_text_invite_counts_as_already_invited():
    from sts_lab.text_chat import conversation_state

    history = normalize_history([
        {"sender": "user", "text": "hi"},
        {"sender": "simran", "text": "Main abhi live hoon, aaiye na wahin baat karte hain."},
    ])
    assert history[1]["invited"] is True
    assert "already invited" in conversation_state(history)
    assert decide_room_card(True, "hmm", history) is False  # just invited, no new push
