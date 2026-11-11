"""Tests for the conversation persistence engine and the admin API (db/ package).

No LiveKit or network access is needed: the recorder is exercised directly against a temporary SQLite file.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import time
from pathlib import Path

from sqlalchemy import func, select

from sts_lab.db import SessionRecorder, infer_stage
from sts_lab.db.admin_api import AdminDbRunner, handle_admin_request
from sts_lab.db.database import acquire_database, release_database, resolve_database_url
from sts_lab.db.models import ConversationSession, Message, User

KEY = "test-admin-key"


def _url(tmp_path: Path, name: str = "t.db") -> str:
    return f"sqlite+aiosqlite:///{tmp_path.as_posix()}/{name}"


def _run_session(url: str, *, identity: str = "Rahul", exit_reason: str | None = "duet_handoff",
                 fields: dict[str, str] | None = None, turns: int = 2, user_text: str = "Rahul") -> str:
    async def go() -> str:
        rec = SessionRecorder(room_name="sts-simran-abcd", identity=identity, model="m", voice="Leda", database_url=url)
        rec.start()
        for i in range(turns):
            rec.record_assistant_turn(f"Simran line {i}")
            rec.record_metrics(150.0 + i * 100, 20.0, 1.1)
            rec.record_user_turn(f"{user_text} {i}")
            rec.record_user_turn("  ")  # blank segments are ignored
        for k, v in (fields or {}).items():
            rec.record_profile_field(k, v)
        if exit_reason:
            rec.mark_exit(exit_reason)
        rec._t0 -= 60  # pretend the call lasted a minute so it is not auto-labelled "abandoned"
        assert await rec.close()
        return rec.session_id

    return asyncio.run(go())


async def _count(url: str, model) -> int:
    db = await acquire_database(url)
    try:
        async with db.session() as s:
            return (await s.execute(select(func.count()).select_from(model))).scalar_one()
    finally:
        await release_database(db)


def test_url_resolution_rewrites_drivers() -> None:
    assert resolve_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")
    assert resolve_database_url("postgresql://u:p@h/db").startswith("postgresql+asyncpg://")
    assert resolve_database_url("sqlite:///x.db").startswith("sqlite+aiosqlite://")
    assert resolve_database_url(None).startswith("sqlite+aiosqlite://")


def test_url_resolution_accepts_libpq_params_from_neon() -> None:
    url = resolve_database_url("postgresql://u:p@h-pooler.neon.tech/db?channel_binding=require&sslmode=require")
    assert url.startswith("postgresql+asyncpg://u:p@h-pooler.neon.tech/db")
    assert "sslmode" not in url and "channel_binding" not in url
    assert "ssl=require" in url


def test_session_user_and_messages_are_created(tmp_path: Path) -> None:
    url = _url(tmp_path)
    sid = _run_session(url, fields={"name": "Rahul", "location": "Pune", "musical_role": "singer",
                                    "music_taste": "Arijit", "favorite_song": "Kesariya"})

    async def check() -> None:
        db = await acquire_database(url)
        try:
            async with db.session() as s:
                sess = await s.get(ConversationSession, sid)
                assert sess is not None and sess.exit_reason == "duet_handoff"
                assert sess.total_turns == 4 and sess.final_stage == 2
                assert sess.ended_at is not None and sess.duration_seconds >= 59
                assert sess.avg_ttft_ms == 200.0
                user = await s.get(User, sess.user_id)
                assert user.location == "Pune" and user.musical_role == "singer"
                assert user.music_taste == ["Arijit"] and user.favorite_song == "Kesariya"
                assert user.is_onboarded is True
                msgs = (await s.execute(select(Message).where(Message.session_id == sid)
                                        .order_by(Message.turn_index))).scalars().all()
                assert [m.turn_index for m in msgs] == [0, 1, 2, 3]
                assert [m.speaker for m in msgs] == ["Simran", "User", "Simran", "User"]
                assert msgs[0].ttft_ms == 150.0 and msgs[2].ttft_ms == 250.0
                captured = msgs[-1].profile_fields_captured
                assert captured["location"] == "Pune" and captured["favorite_song"] == "Kesariya"
        finally:
            await release_database(db)

    asyncio.run(check())


def test_metrics_can_arrive_before_or_after_the_turn(tmp_path: Path) -> None:
    url = _url(tmp_path)

    async def go() -> str:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url)
        rec.start()
        rec.record_metrics(300.0, 18.0, 2.0)  # arrives before the Simran turn is logged
        rec.record_assistant_turn("first")
        rec.record_assistant_turn("second")
        rec.record_metrics(410.0, 19.0, 1.0)  # arrives after, attaches to "second"
        await rec.close()
        return rec.session_id

    sid = asyncio.run(go())

    async def check() -> None:
        db = await acquire_database(url)
        try:
            async with db.session() as s:
                rows = (await s.execute(select(Message.transcript, Message.ttft_ms).where(Message.session_id == sid)
                                        .order_by(Message.turn_index))).all()
                assert rows == [("first", 300.0), ("second", 410.0)]
        finally:
            await release_database(db)

    asyncio.run(check())


def test_unknown_negative_ttft_is_never_stored(tmp_path: Path) -> None:
    url = _url(tmp_path)

    async def go() -> str:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url)
        rec.start()
        rec.record_assistant_turn("hello")
        rec.record_metrics(-1000.0, 18.0, 1.0)  # LiveKit "unknown" sentinel
        await rec.close()
        assert rec._ttfts == []
        return rec.session_id

    sid = asyncio.run(go())

    async def check() -> None:
        db = await acquire_database(url)
        try:
            async with db.session() as s:
                row = (await s.execute(select(Message.ttft_ms).where(Message.session_id == sid))).scalar_one()
                assert row is None
        finally:
            await release_database(db)

    asyncio.run(check())


def test_split_final_user_segments_are_merged(tmp_path: Path) -> None:
    url = _url(tmp_path)

    async def go() -> str:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url)
        rec.start()
        rec.record_user_turn("mera naam")
        rec.record_user_turn("Ananya hai")
        await rec.close()
        return rec.session_id

    sid = asyncio.run(go())

    async def check() -> None:
        db = await acquire_database(url)
        try:
            async with db.session() as s:
                texts = (await s.execute(select(Message.transcript).where(Message.session_id == sid))).scalars().all()
                assert texts == ["mera naam Ananya hai"]
        finally:
            await release_database(db)

    asyncio.run(check())


def test_rapid_turns_never_block_the_event_loop(tmp_path: Path) -> None:
    url = _url(tmp_path)

    async def go() -> tuple[float, float, int]:
        rec = SessionRecorder(room_name="r", identity="Fast", database_url=url)
        rec.start()
        gaps: list[float] = []

        async def heartbeat() -> None:
            last = time.perf_counter()
            while True:
                await asyncio.sleep(0.01)
                now = time.perf_counter()
                gaps.append(now - last - 0.01)
                last = now

        hb = asyncio.create_task(heartbeat())
        t0 = time.perf_counter()
        for i in range(300):
            rec.record_assistant_turn(f"bot {i}")
            rec.record_metrics(120.0, 20.0, 0.5)
            rec.record_user_turn(f"user {i}")
            await asyncio.sleep(0)
            rec._last_turn_speaker = "Simran"  # keep each user line its own turn
        enqueue_seconds = time.perf_counter() - t0
        assert await rec.close(timeout=20.0)
        hb.cancel()
        return enqueue_seconds, max(gaps), rec._turn

    enqueue_seconds, worst_gap, turns = asyncio.run(go())
    assert enqueue_seconds < 1.0, "enqueueing must be effectively instant"
    assert worst_gap < 0.5, f"event loop stalled for {worst_gap:.3f}s during persistence"
    assert turns == 600
    assert asyncio.run(_count(url, Message)) == 600


def test_database_outage_never_crashes_and_recovers(tmp_path: Path) -> None:
    missing_dir = tmp_path / "later"
    url = f"sqlite+aiosqlite:///{missing_dir.as_posix()}/t.db"  # directory does not exist yet: every write fails

    async def go() -> tuple[bool, SessionRecorder]:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url, retry_delay=0.05, max_retry_delay=0.1)
        rec.start()
        t0 = time.perf_counter()
        rec.record_assistant_turn("hello while the database is down")
        rec.record_user_turn("still talking")
        assert time.perf_counter() - t0 < 0.05  # the voice path is not affected
        await asyncio.sleep(0.4)
        assert rec.failed_attempts >= 1  # failures were logged and retried, nothing raised
        missing_dir.mkdir()  # database becomes reachable
        ok = await rec.close(timeout=10.0)
        return ok, rec

    ok, rec = asyncio.run(go())
    assert ok and rec.dropped_ops == 0
    assert asyncio.run(_count(url, Message)) == 2


def test_outage_that_never_ends_gives_up_at_close_without_raising(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'never').as_posix()}/t.db"

    async def go() -> bool:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url, retry_delay=0.05, max_retry_delay=0.1)
        rec.start()
        rec.record_assistant_turn("lost")
        return await rec.close(timeout=0.6)

    assert asyncio.run(go()) is False


def test_queue_overflow_drops_instead_of_growing_forever(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'nope').as_posix()}/t.db"

    async def go() -> int:
        rec = SessionRecorder(room_name="r", identity="Ana", database_url=url, queue_max=5, retry_delay=5.0)
        rec.start()
        for i in range(50):
            rec.record_assistant_turn(f"line {i}")
        dropped = rec.dropped_ops
        rec._task.cancel()
        return dropped

    assert asyncio.run(go()) > 0


def test_exit_reason_defaults(tmp_path: Path) -> None:
    url = _url(tmp_path)

    async def go(user_turns: int, long_call: bool, explicit: str | None) -> str:
        rec = SessionRecorder(room_name="r", identity=f"u{user_turns}{long_call}{explicit}", database_url=url)
        rec.start()
        rec.record_assistant_turn("hi")
        for i in range(user_turns):
            rec.record_user_turn(f"msg {i}")
            rec._last_turn_speaker = "Simran"
        if explicit:
            rec.mark_exit(explicit)
            rec.mark_exit("solo_handoff")  # the first explicit reason wins
        if long_call:
            rec._t0 -= 120
        await rec.close()
        return rec.session_id

    ids = {
        "abandoned_no_user": asyncio.run(go(0, True, None)),
        "disconnected": asyncio.run(go(3, True, None)),
        "short": asyncio.run(go(3, False, None)),
        "decline": asyncio.run(go(3, True, "two_decline_exit")),
    }

    async def reasons() -> dict[str, str | None]:
        db = await acquire_database(url)
        try:
            async with db.session() as s:
                return {k: (await s.get(ConversationSession, v)).exit_reason for k, v in ids.items()}
        finally:
            await release_database(db)

    assert asyncio.run(reasons()) == {
        "abandoned_no_user": "abandoned", "disconnected": "user_disconnected",
        "short": "abandoned", "decline": "two_decline_exit",
    }


def test_stage_inference() -> None:
    assert infer_stage(["name", "location", "occupation"]) == 1
    assert infer_stage(["musical_role"]) == 2
    assert infer_stage(["music_taste", "favorite_song"]) == 2
    assert infer_stage(["expectations"]) == 3
    assert infer_stage(["coins_explained", "musical_role"]) == 3
    assert infer_stage(["name"], pitched=True) == 4
    assert infer_stage(["duet_attempted"]) == 4


# --------------------------------------------------------------------------- admin API
def _admin(url: str) -> AdminDbRunner:
    return AdminDbRunner(url)


def _call(runner: AdminDbRunner, method: str, path: str, body: dict | None = None, key: str | None = KEY):
    return handle_admin_request(method, path, body, key, runner, expected_key=KEY)


def test_admin_requires_a_key(tmp_path: Path) -> None:
    runner = _admin(_url(tmp_path))
    try:
        # Development mode: no key configured -> open to this machine only
        open_local = handle_admin_request("GET", "/api/admin/metrics", None, None, runner, expected_key="")
        assert open_local.status == 200
        remote = handle_admin_request("GET", "/api/admin/metrics", None, None, runner, expected_key="",
                                      client_ip="203.0.113.9")
        assert remote.status == 403
        mode_open = handle_admin_request("GET", "/api/admin/auth-mode", None, None, runner, expected_key="")
        assert json.loads(mode_open.body) == {"auth_required": False}
        assert json.loads(_call(runner, "GET", "/api/admin/auth-mode", key=None).body) == {"auth_required": True}
        # With a key configured, a request from anywhere still needs it
        assert handle_admin_request("GET", "/api/admin/metrics", None, None, runner, expected_key=KEY,
                                    client_ip="203.0.113.9").status == 401
        assert _call(runner, "GET", "/api/admin/metrics", key=None).status == 401
        assert _call(runner, "GET", "/api/admin/metrics", key="wrong").status == 401
        assert _call(runner, "GET", "/api/admin/metrics").status == 200
        assert _call(runner, "GET", "/api/admin/nope").status == 404
    finally:
        runner.close()


def _seed(url: str) -> dict[str, str]:
    return {
        "duet": _run_session(url, identity="Aman", exit_reason="duet_handoff",
                             fields={"location": "Delhi", "musical_role": "singer", "favorite_song": "Kesariya",
                                     "expectations": "duet jam", "duet_attempted": "true"}),
        "decline": _run_session(url, identity="Riya", exit_reason="two_decline_exit",
                                fields={"location": "Mumbai", "musical_role": "listener", "favorite_song": "Tum Hi Ho"}),
        "drop": _run_session(url, identity="Zed", exit_reason="abandoned", fields={"name": "Zed"}, turns=1),
    }


def test_admin_metrics_funnel_sessions_users_and_filters(tmp_path: Path) -> None:
    url = _url(tmp_path)
    ids = _seed(url)
    runner = _admin(url)
    try:
        m = json.loads(_call(runner, "GET", "/api/admin/metrics?days=30").body)
        assert m["total_conversations"] == 3
        assert m["duet_conversion_rate"] == 33.3 and m["two_decline_exit_rate"] == 33.3
        assert m["onboarding_completion_rate"] == 33.3  # only Aman reached the duet pitch
        assert m["ttft_p50_ms"] is not None and m["ttft_samples"] == 5

        f = json.loads(_call(runner, "GET", "/api/admin/funnel?days=30").body)
        assert [s["sessions"] for s in f["stages"][:4]] == [3, 2, 1, 1]
        assert f["stages"][-1]["sessions"] == 1 and f["daily"][0]["sessions"] == 3

        everything = json.loads(_call(runner, "GET", "/api/admin/sessions").body)
        assert everything["total"] == 3
        by_reason = json.loads(_call(runner, "GET", "/api/admin/sessions?exit_reason=two_decline_exit").body)
        assert [i["session_id"] for i in by_reason["items"]] == [ids["decline"]]
        by_user = json.loads(_call(runner, "GET", "/api/admin/sessions?q=aman").body)
        assert [i["session_id"] for i in by_user["items"]] == [ids["duet"]]
        by_role = json.loads(_call(runner, "GET", "/api/admin/sessions?role=listener").body)
        assert [i["session_id"] for i in by_role["items"]] == [ids["decline"]]
        future = json.loads(_call(runner, "GET", "/api/admin/sessions?date_from=2999-01-01").body)
        assert future["total"] == 0
        paged = json.loads(_call(runner, "GET", "/api/admin/sessions?page=2&page_size=2").body)
        assert len(paged["items"]) == 1 and paged["total"] == 3
        wildcard = json.loads(_call(runner, "GET", "/api/admin/sessions?q=%25").body)
        assert wildcard["total"] == 0  # % is escaped, not treated as a wildcard

        users = json.loads(_call(runner, "GET", "/api/admin/users").body)
        assert users["total"] == 3
        assert {c["name"] for c in users["breakdown"]["top_cities"]} == {"Delhi", "Mumbai"}
        assert {r["name"] for r in users["breakdown"]["roles"]} == {"singer", "listener"}
        by_city = json.loads(_call(runner, "GET", "/api/admin/users?city=mum").body)
        assert [u["identity"] for u in by_city["items"]] == ["riya"]
        by_song = json.loads(_call(runner, "GET", "/api/admin/users?song=kesariya").body)
        assert [u["identity"] for u in by_song["items"]] == ["aman"]
    finally:
        runner.close()


def test_admin_session_detail_flagging_review_and_export(tmp_path: Path) -> None:
    url = _url(tmp_path)
    sid = _run_session(url, identity="Aman", fields={"location": "Delhi"}, user_text="=HYPERLINK(evil)")
    runner = _admin(url)
    try:
        detail = json.loads(_call(runner, "GET", f"/api/admin/sessions/{sid}").body)
        assert detail["session"]["exit_reason"] == "duet_handoff" and detail["user"]["location"] == "Delhi"
        assert len(detail["messages"]) == 4
        assert _call(runner, "GET", "/api/admin/sessions/" + "0" * 32).status == 404
        assert _call(runner, "GET", "/api/admin/sessions/not-an-id").status == 404

        target = detail["messages"][0]["id"]
        assert _call(runner, "POST", f"/api/admin/messages/{target}/flag", {"reason": "bogus"}).status == 400
        flagged = json.loads(_call(runner, "POST", f"/api/admin/messages/{target}/flag",
                                   {"reason": "too_long", "note": "ran past 30 words"}).body)
        assert flagged["flagged_issue"] is True and flagged["admin_tag"] == "too_long"
        assert _call(runner, "POST", "/api/admin/messages/" + "1" * 32 + "/flag", {"reason": "other"}).status == 404

        only_flagged = json.loads(_call(runner, "GET", "/api/admin/sessions?flagged=true").body)
        assert [i["session_id"] for i in only_flagged["items"]] == [sid] and only_flagged["items"][0]["has_flagged_turns"]
        assert json.loads(_call(runner, "GET", "/api/admin/metrics").body)["flagged_turns"] == 1

        assert _call(runner, "POST", f"/api/admin/sessions/{sid}/review", {"notes": "Good pacing", "rating": 9}).status == 200
        reviewed = json.loads(_call(runner, "GET", f"/api/admin/sessions/{sid}").body)["session"]
        assert reviewed["admin_notes"] == "Good pacing" and reviewed["feedback_rating"] == 5  # clamped to 1..5

        as_json = _call(runner, "POST", "/api/admin/export", {"format": "json"})
        rows = json.loads(as_json.body)["rows"]
        assert as_json.headers["Content-Disposition"].endswith('.json"') and len(rows) == 4
        only = json.loads(_call(runner, "POST", "/api/admin/export", {"format": "json", "flagged_only": True}).body)
        assert only["count"] == 1 and only["rows"][0]["admin_tag"] == "too_long"

        as_csv = _call(runner, "POST", "/api/admin/export", {"format": "csv", "exit_reason": "duet_handoff"})
        assert as_csv.content_type.startswith("text/csv")
        parsed = list(csv.DictReader(io.StringIO(as_csv.body.decode("utf-8"))))
        assert len(parsed) == 4
        user_lines = [r["transcript"] for r in parsed if r["speaker"] == "User"]
        assert all(not t.startswith("=") for t in user_lines), "spreadsheet formulas must be neutralised"
        assert _call(runner, "POST", "/api/admin/export", {"format": "xml"}).status == 400
    finally:
        runner.close()
