"""One conversation per user: after Simran has talked to them once, coming back is 'session expired'."""

import json

import pytest

from sts_lab.session_gate import SessionGate


@pytest.fixture
def gate(tmp_path):
    return SessionGate(True, tmp_path / "used.json")


def test_off_by_default_never_blocks(tmp_path):
    g = SessionGate(False, tmp_path / "used.json")
    assert g.mark_used("sts-simran-42") is False
    assert g.has_used("sts-simran-42") is False


def test_first_conversation_then_expired(gate):
    assert gate.has_used("sts-simran-42") is False
    assert gate.mark_used("sts-simran-42") is True
    assert gate.has_used("sts-simran-42") is True
    assert gate.mark_used("sts-simran-42") is False  # already recorded


def test_each_user_has_their_own_conversation(gate):
    gate.mark_used("sts-simran-42")
    assert gate.has_used("sts-simran-43") is False


def test_lab_and_test_rooms_are_never_limited(gate):
    for room in ("sts-simran-ab3k", "demo-room", "sts-timing-probe-1", ""):
        assert gate.mark_used(room) is False
        assert gate.has_used(room) is False


def test_survives_a_restart(tmp_path):
    SessionGate(True, tmp_path / "used.json").mark_used("sts-simran-7")
    assert SessionGate(True, tmp_path / "used.json").has_used("sts-simran-7") is True


def test_reset_one_and_all(gate):
    gate.mark_used("sts-simran-1")
    gate.mark_used("sts-simran-2")
    assert gate.reset("sts-simran-1") == 1
    assert gate.has_used("sts-simran-1") is False and gate.has_used("sts-simran-2") is True
    assert gate.reset(None) == 1
    assert gate.has_used("sts-simran-2") is False


def test_a_corrupt_file_does_not_lock_everyone_out(tmp_path):
    f = tmp_path / "used.json"
    f.write_text("{not json", encoding="utf-8")
    g = SessionGate(True, f)
    assert g.has_used("sts-simran-42") is False
    assert g.mark_used("sts-simran-42") is True
    assert json.loads(f.read_text(encoding="utf-8")).keys() == {"sts-simran-42"}
