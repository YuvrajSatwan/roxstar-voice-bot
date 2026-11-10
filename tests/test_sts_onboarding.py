"""Unit tests for sts_lab.onboarding module."""

from __future__ import annotations

from pathlib import Path
from sts_lab.onboarding import (
    DuetRoom,
    DuetRoomRegistry,
    OnboardingTracker,
    UserDiscoveryProfile,
    UserProfileStore,
)


def test_user_discovery_profile_serialization() -> None:
    profile = UserDiscoveryProfile(
        user_id="rahul123",
        name="Rahul",
        location="Pune",
        occupation="Software Engineer",
        hobbies=["guitar", "cricket"],
        music_taste=["Bollywood 90s", "Arijit"],
        expectations="singing duets and meeting music buddies",
    )
    d = profile.to_dict()
    assert d["user_id"] == "rahul123"
    assert d["name"] == "Rahul"
    assert "guitar" in d["hobbies"]

    restored = UserDiscoveryProfile.from_dict(d)
    assert restored.user_id == profile.user_id
    assert restored.location == "Pune"
    assert restored.hobbies == ["guitar", "cricket"]


def test_profile_store_get_or_create(tmp_path: Path) -> None:
    store_file = tmp_path / "test_users.json"
    store = UserProfileStore(file_path=store_file)

    # First time -> new user
    prof1, returning1 = store.get_or_create("rahul")
    assert not returning1
    prof1.music_taste.append("Retro")
    store.save(prof1)

    # Second time -> returning user
    store2 = UserProfileStore(file_path=store_file)
    prof2, returning2 = store2.get_or_create("rahul")
    assert returning2
    assert "Retro" in prof2.music_taste


def test_onboarding_tracker_silent_save_field() -> None:
    profile = UserDiscoveryProfile(user_id="guest1")
    tracker = OnboardingTracker(profile=profile)

    assert tracker.save_field("name", "Simran")
    assert tracker.profile.name == "Simran"
    assert "name" in tracker.discovered_topics

    assert tracker.save_field("music_taste", "Arijit Singh")
    assert "Arijit Singh" in tracker.profile.music_taste
    assert "music_taste" in tracker.discovered_topics

    # Invalid field should be rejected gracefully
    assert not tracker.save_field("invalid_field", "value")


def test_tooltip_deduplication() -> None:
    profile = UserDiscoveryProfile(user_id="singer1")
    tracker = OnboardingTracker(profile=profile)

    # First singing event -> tooltip provided
    tip1, hint1 = tracker.process_app_event("singing_started", {"song": "Kesariya"})
    assert tip1 is not None
    assert tip1["id"] == "singing_started"
    assert "Kesariya" in (hint1 or "")

    # Duplicate singing event -> NO duplicate tooltip
    tip2, hint2 = tracker.process_app_event("singing_started", {"song": "Kesariya"})
    assert tip2 is None
    assert hint2 is not None


def test_sequential_feature_guidance() -> None:
    profile = UserDiscoveryProfile(user_id="user123")
    tracker = OnboardingTracker(profile=profile)

    # 1. User starts singing
    tip_sing, hint_sing = tracker.process_app_event("singing_started")
    assert tip_sing is not None
    assert tracker.has_started_singing

    # 2. User completes recording -> posting tooltip
    tip_rec, hint_rec = tracker.process_app_event("recording_completed", {"duration_s": 45})
    assert tip_rec is not None
    assert tip_rec["id"] == "posting"
    assert tracker.has_completed_recording

    # 3. User publishes song -> commenting tooltip
    tip_post, hint_post = tracker.process_app_event("song_published", {"title": "Tum Hi Ho"})
    assert tip_post is not None
    assert tip_post["id"] == "commenting"
    assert tracker.has_posted_song


def test_duet_availability_and_declines() -> None:
    registry = DuetRoomRegistry()
    profile = UserDiscoveryProfile(user_id="rahul", music_taste=["Bollywood"])
    tracker = OnboardingTracker(profile=profile, duet_registry=registry)

    # Active rooms exist -> suggestion succeeds
    can_suggest, hint, room = tracker.suggest_duet()
    assert can_suggest
    assert room is not None
    assert "Bollywood" in hint or room.genre == "Bollywood"

    # Suggestion already made -> does not repeat immediately
    can_suggest_again, _, _ = tracker.suggest_duet()
    assert not can_suggest_again

    # User declines -> marked as declined
    tracker.record_duet_declined()
    assert tracker.duet_declined
    assert "duet" in tracker.declined_topics


def test_duet_no_rooms_available() -> None:
    empty_registry = DuetRoomRegistry(initial_rooms=[])
    profile = UserDiscoveryProfile(user_id="rahul")
    tracker = OnboardingTracker(profile=profile, duet_registry=empty_registry)

    can_suggest, hint, room = tracker.suggest_duet()
    assert not can_suggest
    assert room is None
    assert "No duet rooms currently available" in hint


def test_summary_context_reflects_known_and_declined() -> None:
    profile = UserDiscoveryProfile(user_id="rahul", name="Rahul", location="Delhi")
    tracker = OnboardingTracker(profile=profile)
    tracker.record_duet_declined()

    summary = tracker.get_summary_context()
    assert "Rahul" in summary
    assert "Delhi" in summary
    assert "duet" in summary
    assert "DO NOT ASK AGAIN" in summary


def test_onboarding_tracker_bot_turned_off() -> None:
    profile = UserDiscoveryProfile(user_id="rahul_stage")
    tracker = OnboardingTracker(profile=profile)
    assert not tracker.bot_turned_off
    assert not tracker.is_simran_away
    assert not tracker.is_saara_away

    tracker.mark_bot_turned_off("User entered solo recording stage")
    assert tracker.bot_turned_off
    assert tracker.is_simran_away
    assert tracker.is_saara_away
    assert tracker.simran_away_reason == "User entered solo recording stage"
    assert tracker.saara_away_reason == "User entered solo recording stage"

