"""Automated test suite validating all scenarios for Simran's Onboarding & Guidance Prototype.

Scenarios covered:
1. New user providing name and music preferences.
2. User skipping introduction questions.
3. User changing the subject.
4. User starting singing.
5. User completing a recording without posting it.
6. User posting a song.
7. User wanting to join a duet (with live rooms).
8. User declining a duet.
9. User when no duet rooms are available.
10. User asking how to earn free coins.
11. Returning user who has already completed onboarding.
12. User asked to join duet/solo 2-3 times but keeps chatting.
13. User says they cannot sing -> two attempts encouragement.
14. User initially hesitates but says YES after convincing.
"""

from __future__ import annotations

from pathlib import Path
from sts_lab.onboarding import (
    SIMRAN_DUET_HANDOFF_EXCUSES,
    SIMRAN_SIGNOFF_EXCUSES,
    SAARA_DUET_HANDOFF_EXCUSES,
    SAARA_SIGNOFF_EXCUSES,
    DuetRoom,
    DuetRoomRegistry,
    OnboardingTracker,
    UserDiscoveryProfile,
    UserProfileStore,
)


def test_scenario_1_new_user_name_and_music() -> None:
    """1. A new user who provides their name and music preferences."""
    profile = UserDiscoveryProfile(user_id="user_rahul")
    tracker = OnboardingTracker(profile=profile)

    assert not tracker.profile.is_returning
    # Simran discovers name and music taste
    tracker.save_field("name", "Rahul")
    tracker.save_field("music_taste", "Arijit Singh")
    tracker.save_field("music_taste", "Retro 90s")

    assert tracker.profile.name == "Rahul"
    assert "Arijit Singh" in tracker.profile.music_taste
    assert "name" in tracker.discovered_topics
    assert "music_taste" in tracker.discovered_topics

    summary = tracker.get_summary_context()
    assert "Name: Rahul" in summary
    assert "Music Taste: Arijit Singh, Retro 90s" in summary
    assert "ALREADY KNOWN (DO NOT ASK AGAIN)" in summary


def test_scenario_2_user_skips_intro_question() -> None:
    """2. A user who skips introduction questions."""
    profile = UserDiscoveryProfile(user_id="user_shy")
    tracker = OnboardingTracker(profile=profile)

    # User tells name, but ignores location when asked and talks about rain
    tracker.save_field("name", "Ananya")
    assert "location" not in tracker.discovered_topics

    # The tracker leaves location in unexplored topics without breaking or forcing it
    summary = tracker.get_summary_context()
    assert "location" in summary
    assert tracker.profile.location is None


def test_scenario_3_user_changes_subject() -> None:
    """3. A user who changes the subject."""
    profile = UserDiscoveryProfile(user_id="user_dynamic")
    tracker = OnboardingTracker(profile=profile)

    # User changes subject to weekend movie
    tracker.save_field("hobbies", "watching movies")
    summary = tracker.get_summary_context()
    assert "watching movies" in summary
    # Conversation continues naturally without rigid flow constraint


def test_scenario_4_user_starts_singing() -> None:
    """4. A user who starts singing (event-driven)."""
    profile = UserDiscoveryProfile(user_id="singer_1")
    tracker = OnboardingTracker(profile=profile)

    tooltip, hint = tracker.process_app_event("singing_started", {"song": "Kesariya"})

    assert tracker.has_started_singing
    assert tooltip is not None
    assert tooltip["id"] == "singing_started"
    assert "Kesariya" in (hint or "")
    assert "Listen quietly without interrupting" in (hint or "")

    # Duplicate singing event does not fire duplicate tooltip
    dup_tooltip, _ = tracker.process_app_event("singing_started", {"song": "Kesariya"})
    assert dup_tooltip is None


def test_scenario_5_user_completes_recording_no_post() -> None:
    """5. A user who completes a recording but does not post it."""
    profile = UserDiscoveryProfile(user_id="singer_2")
    tracker = OnboardingTracker(profile=profile)

    # 1. Start singing
    tracker.process_app_event("singing_started", {"song": "Tum Hi Ho"})
    # 2. Complete recording
    tooltip, hint = tracker.process_app_event("recording_completed", {"duration_s": 40, "song": "Tum Hi Ho"})

    assert tracker.has_completed_recording
    assert not tracker.has_posted_song
    assert tooltip is not None
    assert tooltip["id"] == "posting"
    assert "Post Your Recording" in tooltip["title"]
    assert "40s recording" in (hint or "")


def test_scenario_6_user_posts_song() -> None:
    """6. A user who posts a song."""
    profile = UserDiscoveryProfile(user_id="singer_3")
    tracker = OnboardingTracker(profile=profile)

    # User finishes recording and publishes
    tracker.process_app_event("recording_completed", {"duration_s": 50})
    tooltip, hint = tracker.process_app_event("song_published", {"title": "Pehla Nasha"})

    assert tracker.has_posted_song
    assert tooltip is not None
    assert tooltip["id"] == "commenting"
    assert "Community Love" in tooltip["title"]
    assert "Pehla Nasha" in (hint or "")
    assert "leave appreciation comments" in (hint or "")


def test_scenario_7_user_joins_duet_available() -> None:
    """7. A user who wants to join a duet (with available rooms)."""
    registry = DuetRoomRegistry([
        DuetRoom(
            room_id="duet-1",
            title="Arijit Lovers Jam",
            genre="Romantic",
            host_name="Kabir",
            song_title="Channa Mereya",
        )
    ])
    profile = UserDiscoveryProfile(user_id="user_duet", music_taste=["Romantic"])
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    can_suggest, hint, room = tracker.suggest_duet()
    assert can_suggest
    assert room is not None
    assert room.host_name == "Kabir"
    assert room.song_title == "Channa Mereya"
    assert "Channa Mereya" in hint


def test_scenario_8_user_declines_duet() -> None:
    """8. A user who declines a duet."""
    registry = DuetRoomRegistry()
    profile = UserDiscoveryProfile(user_id="user_solo")
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    # User declines
    tracker.record_duet_declined()
    assert tracker.duet_declined
    assert "duet" in tracker.declined_topics

    # Subsequent duet attempt must be blocked
    can_suggest, hint, room = tracker.suggest_duet()
    assert not can_suggest
    assert room is None
    assert "User previously declined a duet. Do not suggest again." in hint

    # Summary context must warn against asking
    summary = tracker.get_summary_context()
    assert "USER DECLINED (DO NOT ASK AGAIN): duet" in summary


def test_scenario_9_no_duet_rooms_available() -> None:
    """9. A user when no duet rooms are available."""
    empty_registry = DuetRoomRegistry(initial_rooms=[])
    profile = UserDiscoveryProfile(user_id="user_unlucky")
    tracker = OnboardingTracker(profile=profile, duet_registry=empty_registry)

    can_suggest, hint, room = tracker.suggest_duet()
    assert not can_suggest
    assert room is None
    assert "No duet rooms currently available. Do NOT pretend rooms exist." in hint

    # App event for duet request with empty rooms
    _, event_hint = tracker.process_app_event("duet_requested")
    assert "NO duet rooms are currently active" in (event_hint or "")
    assert "suggest recording solo" in (event_hint or "")


def test_scenario_10_user_asking_free_coins() -> None:
    """10. A user asking how to earn free coins."""
    profile = UserDiscoveryProfile(user_id="user_coins")
    tracker = OnboardingTracker(profile=profile)

    tooltip, hint = tracker.process_app_event("coins_info_requested")

    assert tracker.coins_guidance_given
    assert tracker.profile.coins_explained
    assert "coins_explained" in tracker.discovered_topics
    assert tooltip is not None
    assert tooltip["id"] == "gifting"
    assert "daily check-ins accumulate coins" in (hint or "")
    assert "without spending money" in (hint or "")


def test_scenario_11_returning_user_already_onboarded(tmp_path: Path) -> None:
    """11. A returning user who has already completed onboarding."""
    store_file = tmp_path / "scenario_users.json"
    store = UserProfileStore(file_path=store_file)

    # Session 1: User onboarded
    p1, _ = store.get_or_create("Priya")
    p1.name = "Priya"
    p1.location = "Jaipur"
    p1.occupation = "Graphic Designer"
    p1.music_taste = ["Indie Pop", "Prateek Kuhad"]
    p1.coins_explained = True
    store.save(p1)

    # Session 2: User returns
    store2 = UserProfileStore(file_path=store_file)
    p2, returning = store2.get_or_create("Priya")

    assert returning
    assert p2.is_returning
    assert p2.name == "Priya"
    assert p2.location == "Jaipur"
    assert "Indie Pop" in p2.music_taste

    tracker2 = OnboardingTracker(profile=p2, store=store2)
    summary = tracker2.get_summary_context()
    assert "STATUS: Returning user. Greet warmly as a familiar friend; DO NOT repeat introduction/onboarding!" in summary
    assert "Name: Priya" in summary
    assert "Location: Jaipur" in summary
    assert "Occupation: Graphic Designer" in summary


def test_scenario_12_user_keeps_chatting_after_multiple_nudges() -> None:
    """12. User asked to join duet/solo 2-3 times but keeps chatting -> Simran gives realistic excuse and signs off."""
    registry = DuetRoomRegistry([
        DuetRoom(room_id="duet-1", title="Jam", genre="Romantic", host_name="Aman", song_title="Pehla Nasha")
    ])
    profile = UserDiscoveryProfile(user_id="talkative_user", name="Karan", music_taste=["Romantic"])
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    # Nudge 1: Suggest duet
    can_suggest, _, _ = tracker.suggest_duet()
    assert can_suggest
    assert tracker.action_nudge_count == 1
    assert not tracker.should_sign_off()

    # User declines duet -> Nudge 2 (solo option / second decline)
    tracker.record_duet_declined()
    assert tracker.action_nudge_count == 2
    assert tracker.should_sign_off()

    # Verify summary context instructs sign-off with realistic excuse
    summary = tracker.get_summary_context()
    assert "SIGN-OFF STATUS" in summary
    assert "realistic personal excuse" in summary

    # Verify random excuse picker returns one of Simran's authentic excuses
    excuse = tracker.get_random_excuse()
    assert excuse in SIMRAN_SIGNOFF_EXCUSES
    assert excuse in SAARA_SIGNOFF_EXCUSES
    assert any(keyword in excuse.lower() for keyword in ["client", "mummy", "swiggy", "parcel", "laptop", "friend", "deadline", "ritika"])


def test_scenario_13_user_says_cannot_sing_two_attempt_encouragement() -> None:
    """13. User says they cannot sing -> Simran encourages twice (Duet bridge, then solo/comment promise) before signing off."""
    registry = DuetRoomRegistry([
        DuetRoom(room_id="duet-romantic", title="Romantic Jam", genre="Romantic", host_name="Rhea", song_title="Tum Hi Ho")
    ])
    profile = UserDiscoveryProfile(user_id="user_hesitant", name="Rohit", music_taste=["Romantic"])
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    # Attempt 1: User says "nahi mujhe gana nahi aata" -> Duet bridge suggested (no perfect singer needed)
    can_suggest, hint, room = tracker.suggest_duet()
    assert can_suggest
    assert room is not None
    assert tracker.action_nudge_count == 1
    assert not tracker.should_sign_off()

    # Verify context guides to Attempt 2 encouragement
    summary1 = tracker.get_summary_context()
    assert "ENCOURAGEMENT ATTEMPT 2" in summary1
    assert "favorite song" in summary1

    # Attempt 2: User says "achha feature hai" but declines to sing right now -> Record decline
    tracker.record_duet_declined()
    assert tracker.action_nudge_count == 2
    assert tracker.should_sign_off()

    # After 2 attempts: sign-off triggers with realistic excuse
    summary2 = tracker.get_summary_context()
    assert "SIGN-OFF STATUS (CRITICAL)" in summary2
    excuse = tracker.get_random_excuse()
    assert excuse in SIMRAN_SIGNOFF_EXCUSES
    assert excuse in SAARA_SIGNOFF_EXCUSES


def test_scenario_14_user_says_yes_after_convincing() -> None:
    """14. User initially hesitates but says YES after convincing -> Simran celebrates and hands off stage cleanly."""
    registry = DuetRoomRegistry([
        DuetRoom(room_id="duet-romantic", title="Romantic Jam", genre="Romantic", host_name="Rhea", song_title="Tum Hi Ho")
    ])
    profile = UserDiscoveryProfile(user_id="user_convinced", name="Aakash", music_taste=["Romantic"])
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    # User hesitates, Simran suggests duet
    can_suggest, _, room = tracker.suggest_duet()
    assert can_suggest
    assert room is not None
    assert tracker.action_nudge_count == 1

    # User says YES ("Haan chalo try karte hain") -> duet handoff celebration in natural Hindi
    duet_handoff = tracker.get_random_duet_handoff_reason()
    assert duet_handoff in SIMRAN_DUET_HANDOFF_EXCUSES
    assert duet_handoff in SAARA_DUET_HANDOFF_EXCUSES
    assert any(w in duet_handoff for w in ["Yeh hui na baat", "Zabardast", "Sahi hai", "Kya baat"])

    # Bot marks turned off for duet
    tracker.mark_bot_turned_off("User entered live duet stage")
    assert tracker.bot_turned_off
    assert tracker.is_simran_away
    assert tracker.is_saara_away


