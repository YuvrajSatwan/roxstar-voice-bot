"""Tests for the live duet list in strict (production) mode.

In simple words: in production Simran may only send a user to a room that rox-partyroom
really reported. These tests prove she never guesses, never uses demo rooms, and falls
back to "no rooms" (so she offers solo recording) when the backend is down.
"""

from __future__ import annotations

from sts_lab.onboarding import DuetRoomRegistry


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _room(rid: str = "123", host: str = "Aman") -> dict[str, str]:
    return {"room_id": rid, "title": "Kesariya Jam", "host_name": host, "genre": "Bollywood", "song_title": "Kesariya"}


def test_strict_registry_starts_with_no_demo_rooms():
    reg = DuetRoomRegistry(strict=True)
    assert reg.list_available() == []


def test_refresh_loads_real_rooms():
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: [_room("123"), _room("456", "Rhea")])
    reg.refresh()
    assert [r.room_id for r in reg.list_available()] == ["123", "456"]
    assert reg.get_room("123").host_name == "Aman"


def test_strict_get_room_never_guesses():
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: [_room("123")])
    reg.refresh()
    assert reg.get_room("123") is not None
    assert reg.get_room("999") is None  # unknown id
    assert reg.get_room("Aman") is None  # no fuzzy match on host
    assert reg.get_room("Kesariya") is None  # no fuzzy match on song
    assert reg.get_room("") is None


def test_lab_mode_keeps_the_old_fuzzy_behaviour():
    reg = DuetRoomRegistry()  # default = lab mode, unchanged
    assert reg.get_room("kesariya") is not None
    assert reg.get_room("totally-unknown") is not None  # old "first room" fallback


def test_good_answers_are_cached_for_60_seconds():
    clock, calls = FakeClock(), []

    def fetch():
        calls.append(1)
        return [_room()]

    reg = DuetRoomRegistry(strict=True, fetcher=fetch, clock=clock)
    reg.refresh()
    clock.now = 59
    reg.refresh()
    assert len(calls) == 1
    clock.now = 61
    reg.refresh()
    assert len(calls) == 2


def test_empty_answers_are_rechecked_sooner():
    clock, calls = FakeClock(), []

    def fetch():
        calls.append(1)
        return []

    reg = DuetRoomRegistry(strict=True, fetcher=fetch, clock=clock)
    reg.refresh()
    clock.now = 11
    reg.refresh()
    assert len(calls) == 2


def test_backend_failure_means_no_rooms_not_stale_rooms():
    clock = FakeClock()
    state = {"fail": False}

    def fetch():
        if state["fail"]:
            raise RuntimeError("partyroom down")
        return [_room()]

    reg = DuetRoomRegistry(strict=True, fetcher=fetch, clock=clock)
    reg.refresh()
    assert reg.get_room("123") is not None
    state["fail"] = True
    clock.now = 61
    reg.refresh()  # must not raise
    assert reg.list_available() == []
    assert reg.get_room("123") is None


def test_a_room_that_closed_disappears_on_the_next_refresh():
    clock = FakeClock()
    rooms = [[_room("123")], []]
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: rooms.pop(0), clock=clock)
    reg.refresh()
    assert reg.get_room("123") is not None
    clock.now = 61
    reg.refresh()
    assert reg.get_room("123") is None


def test_rooms_without_an_id_are_ignored():
    reg = DuetRoomRegistry(strict=True, fetcher=lambda: [{"title": "x", "host_name": "y"}, _room("7")])
    reg.refresh()
    assert [r.room_id for r in reg.list_available()] == ["7"]


def test_refresh_without_a_fetcher_does_nothing():
    reg = DuetRoomRegistry()
    before = [r.room_id for r in reg.list_available()]
    reg.refresh()
    assert [r.room_id for r in reg.list_available()] == before
