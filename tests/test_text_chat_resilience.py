"""Resilience of Simran's text replies: retries, backup model, deadline, and why a canned line was used."""

from __future__ import annotations

import json
import threading
from unittest.mock import patch

import pytest
from google.genai import errors as genai_errors

from sts_lab import text_chat
from sts_lab.config import StsSettings
from sts_lab.text_chat import SimranTextChatEngine, classify_error

MAIN = "main-model"
BACKUP = "backup-model"
GOOD = json.dumps({"reply_text": "Achha, sahi hai. Main abhi live hoon, aaiye na wahin baat karte hain.", "send_room_card": True})


class Resp:
    def __init__(self, text):
        self.text = text


def api_error(code: int, status: str = "ERR"):
    cls = genai_errors.ServerError if code >= 500 else genai_errors.ClientError
    return cls(code, {"error": {"code": code, "message": f"{code} {status}", "status": status}})


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(text_chat, "RETRY_BACKOFF_SEC", 0.0)


def make_engine(script, fallback_model=BACKUP):
    """An engine whose Gemini calls follow `script`: one item per call, an Exception (raised) or text (answered).
    Returns (engine, calls) where calls lists the model of every call made."""
    engine = SimranTextChatEngine(api_key="fake-key", model=MAIN, fallback_model=fallback_model)
    calls: list[str] = []
    items = list(script)

    def fake_generate(**kw):
        calls.append(kw["model"])
        item = items.pop(0) if items else api_error(503, "UNAVAILABLE")
        if isinstance(item, BaseException):
            raise item
        return Resp(item)

    engine.client.models.generate_content = fake_generate  # type: ignore[method-assign]
    return engine, calls


# ------------------------------------------------------------------ retries and the backup model

def test_one_503_is_retried_on_the_same_model_and_gemini_answers():
    engine, calls = make_engine([api_error(503, "UNAVAILABLE"), GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False
    assert result["model"] == MAIN and result["attempts"] == 2
    assert calls == [MAIN, MAIN]
    assert "fallback_reason" not in result


def test_two_503s_on_the_main_model_switch_to_the_backup_model():
    engine, calls = make_engine([api_error(503), api_error(503), GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False
    assert result["model"] == BACKUP and result["attempts"] == 3
    assert calls == [MAIN, MAIN, BACKUP]


def test_quota_429_skips_straight_to_the_backup_model():
    engine, calls = make_engine([api_error(429, "RESOURCE_EXHAUSTED"), GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False and result["model"] == BACKUP
    assert calls == [MAIN, BACKUP]  # no pointless second try on a model whose quota is gone


def test_missing_model_404_skips_to_the_backup_model():
    engine, calls = make_engine([api_error(404, "NOT_FOUND"), GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False and result["model"] == BACKUP
    assert calls == [MAIN, BACKUP]


def test_refused_key_401_is_reported_as_auth():
    engine, _ = make_engine([api_error(401, "UNAUTHENTICATED")], fallback_model="off")
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "auth"


def test_quota_on_both_models_gives_a_canned_line_with_reason_quota():
    engine, calls = make_engine([api_error(429), api_error(429)])
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["model"] == "fallback"
    assert result["fallback_reason"] == "quota"
    assert result["attempts"] == 2 and calls == [MAIN, BACKUP]
    assert result["reply_text"] in [f["reply_text"] for f in text_chat.FALLBACK_REPLIES]


def test_everything_overloaded_stops_after_max_attempts_with_reason_overloaded():
    engine, calls = make_engine([])  # every call answers 503
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "overloaded"
    assert result["attempts"] == text_chat.MAX_ATTEMPTS == len(calls)
    assert calls == [MAIN, MAIN, BACKUP, BACKUP]


def test_backup_model_switched_off_means_one_model_only():
    engine, calls = make_engine([api_error(429)], fallback_model="off")
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "quota"
    assert calls == [MAIN]
    assert engine.fallback_model == ""


def test_backup_model_equal_to_main_is_not_used_twice():
    engine, calls = make_engine([api_error(503), api_error(503)], fallback_model=MAIN)
    engine.generate_reply("hi")
    assert calls == [MAIN, MAIN]


def test_an_unknown_exception_is_retried_then_falls_back_with_reason_error():
    engine, calls = make_engine([ConnectionError("reset"), ConnectionError("reset"), ConnectionError("x"), ConnectionError("y")])
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "error"
    assert len(calls) == 4


# ------------------------------------------------------------------ unusable answers

@pytest.mark.parametrize("bad", ["", "   ", "not json at all", "[1, 2]", '"just a string"', "{}", '{"reply_text": null}',
                                 '{"reply_text": ""}', '{"reply_text": 42}', None])
def test_unusable_answer_is_retried_and_then_a_good_one_is_used(bad):
    engine, calls = make_engine([bad, GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False and result["attempts"] == 2


def test_unusable_answers_every_time_give_reason_bad_reply():
    engine, _ = make_engine(["nope"] * 4)
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "bad_reply"


def test_a_reply_about_coins_is_retried_and_a_clean_one_wins():
    coins = json.dumps({"reply_text": "Room mein 50 coins mil rahe hain, aaiye!", "send_room_card": True})
    engine, calls = make_engine([coins, GOOD])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False and "coin" not in result["reply_text"].lower()
    assert result["attempts"] == 2


def test_coins_every_time_give_reason_banned_topic():
    coins = json.dumps({"reply_text": "Free reward milega, aaiye!", "send_room_card": True})
    engine, _ = make_engine([coins] * 4)
    result = engine.generate_reply("hi")
    assert result["fallback"] is True and result["fallback_reason"] == "banned_topic"


def test_json_wrapped_in_a_code_fence_is_accepted():
    engine, _ = make_engine(["```json\n" + GOOD + "\n```"])
    result = engine.generate_reply("hi")
    assert result["fallback"] is False and result["attempts"] == 1


def test_send_room_card_given_as_the_text_false_is_false():
    text = json.dumps({"reply_text": "Achha, sahi hai.", "send_room_card": "false"})
    engine, _ = make_engine([text])
    assert engine.generate_reply("hi")["send_room_card"] is False


def test_a_very_long_reply_is_cut_to_the_cap():
    long_reply = json.dumps({"reply_text": "a" * 5000, "send_room_card": False})
    engine, _ = make_engine([long_reply])
    assert len(engine.generate_reply("hi")["reply_text"]) <= text_chat.MAX_REPLY_CHARS


def test_the_room_card_rules_still_apply_to_a_good_answer():
    engine, _ = make_engine([GOOD])
    # They said "nahi": no join button even though the model asked for one.
    assert engine.generate_reply("nahi abhi nahi")["send_room_card"] is False


# ------------------------------------------------------------------ deadline

def test_a_hung_gemini_call_ends_inside_the_deadline_with_reason_timeout():
    gate = threading.Event()
    engine = SimranTextChatEngine(api_key="fake-key", model=MAIN, fallback_model="off")

    def hang(**kw):
        gate.wait(10)
        return Resp(GOOD)

    engine.client.models.generate_content = hang  # type: ignore[method-assign]
    try:
        import time
        start = time.monotonic()
        result = engine.generate_reply("hi", timeout_sec=1.5)
        assert time.monotonic() - start < 4
        assert result["fallback"] is True and result["fallback_reason"] == "timeout"
    finally:
        gate.set()


def test_a_slow_first_call_still_leaves_time_for_a_second_try_with_the_20s_budget():
    waits: list[float] = []
    engine = SimranTextChatEngine(api_key="fake-key", model=MAIN, fallback_model=BACKUP)
    answers = [TimeoutError("slow"), GOOD]

    def fake_call(model, prompt, wait_sec):
        waits.append(wait_sec)
        item = answers.pop(0)
        if isinstance(item, BaseException):
            raise item
        return Resp(item)

    engine._call_gemini = fake_call  # type: ignore[method-assign]
    result = engine.generate_reply("hi", timeout_sec=20.0)
    assert result["fallback"] is False and result["attempts"] == 2
    assert all(1.0 <= w <= text_chat.ATTEMPT_CAP_SEC for w in waits)


def test_default_budget_is_20_seconds_and_a_margin_is_kept_back():
    assert text_chat.DEFAULT_CHAT_TIMEOUT_SEC == 20.0
    assert StsSettings.__dataclass_fields__["chat_timeout_sec"].default == 20.0
    engine, _ = make_engine([GOOD])
    seen: dict = {}
    original = engine._call_gemini

    def spy(model, prompt, wait_sec):
        seen["wait"] = wait_sec
        return original(model, prompt, wait_sec)

    engine._call_gemini = spy  # type: ignore[method-assign]
    engine.generate_reply("hi", timeout_sec=20.0)
    assert seen["wait"] <= text_chat.ATTEMPT_CAP_SEC


def test_no_deadline_still_answers():
    engine, _ = make_engine([GOOD])
    assert engine.generate_reply("hi", timeout_sec=0)["fallback"] is False


# ------------------------------------------------------------------ classification and plumbing

@pytest.mark.parametrize("code,expected", [
    (429, ("quota", "next_model")), (401, ("auth", "next_model")), (403, ("auth", "next_model")),
    (400, ("model_error", "next_model")), (404, ("model_error", "next_model")),
    (500, ("overloaded", "retry")), (503, ("overloaded", "retry")), (504, ("overloaded", "retry")),
])
def test_error_classification(code, expected):
    assert classify_error(api_error(code)) == expected


def test_timeouts_and_odd_errors_are_retried():
    assert classify_error(TimeoutError("x")) == ("timeout", "retry")
    assert classify_error(RuntimeError("x")) == ("error", "retry")


def test_warm_up_never_raises_and_reports_the_result():
    engine = SimranTextChatEngine(api_key="fake-key", model=MAIN, fallback_model="off")
    with patch.object(engine.client.models, "get", return_value=object()):
        assert engine.warm_up() is True
    with patch.object(engine.client.models, "get", side_effect=api_error(503)):
        assert engine.warm_up() is False


def test_the_shared_engine_is_built_once_even_when_requests_arrive_together(monkeypatch):
    from sts_lab import token_server as ts

    built: list[int] = []

    class Fake:
        def __init__(self):
            built.append(1)

    monkeypatch.setattr(ts, "_chat_engine", None)
    monkeypatch.setattr(ts, "SimranTextChatEngine", Fake)
    threads = [threading.Thread(target=ts.get_chat_engine) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(built) == 1
