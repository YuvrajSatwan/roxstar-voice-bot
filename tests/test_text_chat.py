"""Tests for Simran Text Chat Auto-Responder and /api/simran/chat-reply."""

import json
from unittest.mock import MagicMock, patch
import pytest

from sts_lab.text_chat import (
    SimranTextChatEngine,
    FALLBACK_REPLIES,
    SIMRAN_TEXT_SYSTEM_INSTRUCTION,
)


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


def test_fallback_structure():
    """Verify fallback replies match expected schema."""
    for item in FALLBACK_REPLIES:
        assert "reply_text" in item
        assert "send_room_card" in item
        assert isinstance(item["reply_text"], str)
        assert len(item["reply_text"]) > 10
        assert item["send_room_card"] is True


def test_engine_generate_reply_success():
    """Verify SimranTextChatEngine parses Gemini JSON response correctly."""
    engine = SimranTextChatEngine(api_key="fake-key")
    mock_payload = {
        "reply_text": "Hey yaar! Main toh stage pe gaane gaa rahi hoon, jaldi se join karo na!",
        "send_room_card": True,
    }
    with patch.object(
        engine.client.models,
        "generate_content",
        return_value=DummyResponse(json.dumps(mock_payload)),
    ):
        result = engine.generate_reply(
            user_message="Hey Simran kya kar rahi ho?",
            user_name="Aman",
            recent_history=[{"sender": "user", "text": "Hi"}],
        )
        assert result["reply_text"] == mock_payload["reply_text"]
        assert result["send_room_card"] is True
        assert result["fallback"] is False


def test_engine_fallback_on_exception():
    """Verify engine falls back to human-like template when Gemini API fails."""
    engine = SimranTextChatEngine(api_key="fake-key")
    with patch.object(
        engine.client.models,
        "generate_content",
        side_effect=RuntimeError("Quota exceeded"),
    ):
        result = engine.generate_reply(user_message="Hello")
        assert result["fallback"] is True
        assert result["model"] == "fallback"
        assert result["send_room_card"] is True
        assert len(result["reply_text"]) > 0


def test_engine_fallback_on_empty_text():
    """Verify engine falls back when Gemini returns empty text."""
    engine = SimranTextChatEngine(api_key="fake-key")
    with patch.object(
        engine.client.models,
        "generate_content",
        return_value=DummyResponse(""),
    ):
        result = engine.generate_reply(user_message="Hello")
        assert result["fallback"] is True
        assert result["send_room_card"] is True


def test_identity_prompt_contains_rules():
    """Ensure system prompt forbids AI mentions and enforces live room motive."""
    assert "NEVER mention AI" in SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "South Delhi" in SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "PRIMARY MOTIVE & GOAL" in SIMRAN_TEXT_SYSTEM_INSTRUCTION
    assert "PULL AND FUNNEL THE USER INTO YOUR LIVE PARTY ROOM" in SIMRAN_TEXT_SYSTEM_INSTRUCTION
