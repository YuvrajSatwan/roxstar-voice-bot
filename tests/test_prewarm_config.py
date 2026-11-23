"""The early-start flag is OFF unless explicitly switched on."""

import pytest

from sts_lab.config import StsSettings


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.invalid")
    monkeypatch.setenv("LIVEKIT_API_KEY", "k")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.delenv("STS_PREWARM_ENABLED", raising=False)
    monkeypatch.delenv("STS_PREWARM_IDLE_SEC", raising=False)


def test_prewarm_is_off_by_default():
    s = StsSettings.load()
    assert s.prewarm_enabled is False
    assert s.prewarm_idle_sec == 20


@pytest.mark.parametrize("value,expected", [("true", True), ("1", True), ("ON", True), ("false", False), ("", False), ("nope", False)])
def test_prewarm_flag_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("STS_PREWARM_ENABLED", value)
    assert StsSettings.load().prewarm_enabled is expected


def test_idle_seconds_has_a_floor(monkeypatch):
    monkeypatch.setenv("STS_PREWARM_IDLE_SEC", "1")
    assert StsSettings.load().prewarm_idle_sec == 5
