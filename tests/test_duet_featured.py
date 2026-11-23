"""Final handoff: one featured duet POST (Harshit, "Tum Hi Ho"). OFF unless STS_DUET_POST_ID is set."""

import pytest

from sts_lab.config import StsSettings
from sts_lab.onboarding import DuetRoom, DuetRoomRegistry


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.invalid")
    monkeypatch.setenv("LIVEKIT_API_KEY", "k")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    for name in ("STS_DUET_POST_ID", "STS_DUET_HOST_NAME", "STS_DUET_SONG_TITLE"):
        monkeypatch.delenv(name, raising=False)


def _featured() -> DuetRoom:
    return DuetRoom(
        room_id="post-411", title="Tum Hi Ho duet", genre="Bollywood",
        host_name="Harshit", song_title="Tum Hi Ho", post_id="411",
    )


def test_feature_is_off_by_default():
    s = StsSettings.load()
    assert s.duet_post_id == ""
    assert (s.duet_host_name, s.duet_song_title) == ("Harshit", "Tum Hi Ho")


def test_post_id_is_read_from_env(monkeypatch):
    monkeypatch.setenv("STS_DUET_POST_ID", " 411 ")
    assert StsSettings.load().duet_post_id == "411"


@pytest.mark.parametrize("bad", ["abc", "41 1", "https://roxstar.in/link?data=x", "-5"])
def test_a_garbled_post_id_turns_the_feature_off(monkeypatch, bad):
    monkeypatch.setenv("STS_DUET_POST_ID", bad)
    assert StsSettings.load().duet_post_id == ""


def test_featured_room_is_the_only_option():
    reg = DuetRoomRegistry(strict=True, featured=_featured())
    rooms = reg.list_available()
    assert [r.post_id for r in rooms] == ["411"]
    assert reg.list_available("Retro")[0].host_name == "Harshit"


def test_featured_room_is_found_whatever_id_the_model_passes():
    reg = DuetRoomRegistry(strict=True, featured=_featured())
    assert reg.get_room("post-411").post_id == "411"
    assert reg.get_room("duet-kesariya").post_id == "411"


def test_featured_room_skips_the_live_list_lookup():
    calls = []
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: calls.append(1) or [], featured=_featured())
    reg.refresh()
    assert calls == []


def test_pitch_waits_for_the_user_and_offers_no_choice():
    from sts_lab.onboarding import featured_duet_pitch

    text = featured_duet_pitch(_featured())
    assert "Harshit" in text and "Tum Hi Ho" in text
    assert "do NOT offer a choice" in text
    assert "wait for the user's answer" in text
    assert "Do NOT call navigate_to_duet yet" in text
    assert "sending them there" not in text  # the old "no waiting for a yes" wording is gone


def test_without_featured_nothing_changes():
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: [{"room_id": "7"}])
    assert reg.featured is None
    reg.refresh()
    assert [r.room_id for r in reg.list_available()] == ["7"]
    assert reg.get_room("post-411") is None
