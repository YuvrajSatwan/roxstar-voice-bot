"""The 'user is arriving' note only counts while it is fresh."""

import json
import time


def _fresh(metadata, now=None):
    # Mirror of worker.room_says_user_arriving (it is a closure inside entrypoint, so we test the rule itself).
    try:
        stamp = float(json.loads(metadata or "{}").get("user_arriving") or 0)
    except (ValueError, TypeError, AttributeError):
        return False
    return 0 < (now or time.time()) - stamp < 30.0


def test_a_fresh_note_counts():
    assert _fresh(json.dumps({"user_arriving": time.time()}))


def test_an_old_note_from_a_past_visit_does_not_count():
    assert not _fresh(json.dumps({"user_arriving": time.time() - 120}))


def test_junk_or_empty_never_counts():
    for junk in (None, "", "{}", "not json", json.dumps({"user_arriving": True}), json.dumps({"user_arriving": "x"})):
        assert not _fresh(junk)
