"""State & Discovery Engine for Saara (STS Lab Prototype).

Tracks user discovery across the 8 key topics:
1. Name
2. Location
3. Occupation
4. Hobbies
5. Music taste
6. RoxStar expectations
7. Duet vs posting a song
8. Free coins & gifting guidance

Also manages real-time karaoke state (singing, recording, posting, comments),
contextual tooltip deduplication, duet room availability, and returning-user persistence.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("sts_onboarding")

DATA_STORE_PATH = Path(".sts_users.json")

# The 8 canonical discovery fields matching the prompt
VALID_PROFILE_FIELDS = frozenset({
    "name",
    "location",
    "occupation",
    "hobbies",
    "music_taste",
    "expectations",
    "duet_attempted",
    "coins_explained",
})

# Saara's authentic real-world excuses when wrapping up (kept punchy, under 20 words)
SAARA_SIGNOFF_EXCUSES: list[str] = [
    "Arre door bell baji, lagta hai mere momos aa gaye! Chalti hoon main, bye!",
    "Mummy chai ke liye chilla rahi hain! Main bhaagi, tum tab tak gaana zaroor try karna, bye!",
    "Client ka urgent ping aa gaya, design badalna hai! Nikalti hoon, baad mein baat karte hain, bye!",
    "Haaye laptop 4 percent pe aa gaya aur charger doosre kamre mein hai! Bhaagi main, bye!",
    "Ritika meri friend ka phone aa raha hai kab se! Mujhe nikalna padega, next time pakka jam karenge, bye!",
    "Yaar deadline yaad aa gayi achaanak! Chalti hoon, tum gaake dikhana, bye!",
]

# Realistic excuses & handoff reasons when Saara signs off as user joins duet (strictly under 25 words)
SAARA_DUET_HANDOFF_EXCUSES: list[str] = [
    "Room khul gaya, 'Join Duet' dabao! Client ka urgent ping aa gaya mera, main nikalti hoon. Aag laga dena, bye!",
    "Zabardast choice! Mummy chai ke liye aawaz de rahi hain toh main bhaagi, tum stage pe rock karna, bye bye!",
    "Duet stage ready hai screen pe! Main mic chodti hoon taaki tum dono mast jam karo. All the best, bye!",
    "Door bell baji, lagta hai momos aa gaye! Main nikal rahi hoon, tum stage pe aag lagao, bye!",
]

# Realistic excuses & handoff reasons when user agrees to solo recording (strictly under 25 words)
SAARA_SOLO_HANDOFF_EXCUSES: list[str] = [
    "Studio stage khul gaya screen pe! Laptop 4 percent pe aa gaya mera, main bhaagi. Solo mic pe aag lagao, bye!",
    "Mast choice! Mummy chai ke liye aawaz de rahi hain toh main nikalti hoon. Dil khol ke gaana, bye bye!",
    "Recording stage ready hai! Client ka urgent ping aa gaya mera, main bhaagi. All the best, rock karna, bye!",
    "Door bell baj gayi, lagta hai mere momos aa gaye! Main nikal rahi hoon, tum solo mic pe aag lagao, bye!",
]


@dataclass
class UserDiscoveryProfile:
    """Discovered facts about a user. Never forced; accumulated organically."""

    user_id: str
    name: str | None = None
    location: str | None = None
    occupation: str | None = None
    hobbies: list[str] = field(default_factory=list)
    music_taste: list[str] = field(default_factory=list)
    expectations: str | None = None
    duet_attempted: bool = False
    coins_explained: bool = False
    is_returning: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserDiscoveryProfile:
        return cls(
            user_id=data.get("user_id", "guest"),
            name=data.get("name"),
            location=data.get("location"),
            occupation=data.get("occupation"),
            hobbies=list(data.get("hobbies", [])),
            music_taste=list(data.get("music_taste", [])),
            expectations=data.get("expectations"),
            duet_attempted=bool(data.get("duet_attempted", False)),
            coins_explained=bool(data.get("coins_explained", False)),
            is_returning=bool(data.get("is_returning", False)),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class UserProfileStore:
    """Local JSON persistence for prototype user profiles."""

    def __init__(self, file_path: Path = DATA_STORE_PATH) -> None:
        self.file_path = file_path
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._profiles = json.load(f)
            except Exception as e:
                logger.warning("Could not read profile store %s: %s", self.file_path, e)
                self._profiles = {}

    def _save_to_disk(self) -> None:
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Could not write profile store %s: %s", self.file_path, e)

    def get_or_create(self, identity: str) -> tuple[UserDiscoveryProfile, bool]:
        key = identity.strip().lower()
        if not key:
            key = "guest"
        if key in self._profiles:
            profile = UserDiscoveryProfile.from_dict(self._profiles[key])
            profile.is_returning = True
            return profile, True
        profile = UserDiscoveryProfile(user_id=identity, name=identity if identity != "guest" else None)
        self._profiles[key] = profile.to_dict()
        self._save_to_disk()
        return profile, False

    def save(self, profile: UserDiscoveryProfile) -> None:
        profile.updated_at = time.time()
        key = profile.user_id.strip().lower() or "guest"
        self._profiles[key] = profile.to_dict()
        self._save_to_disk()


@dataclass
class DuetRoom:
    room_id: str
    title: str
    genre: str
    host_name: str
    song_title: str
    singers_count: int = 1


class DuetRoomRegistry:
    """Registry of live duet rooms so Saara only suggests REAL available rooms."""

    def __init__(self, initial_rooms: list[DuetRoom] | None = None) -> None:
        if initial_rooms is not None:
            self._rooms: dict[str, DuetRoom] = {r.room_id: r for r in initial_rooms}
        else:
            self._rooms = {
                "duet-kesariya": DuetRoom(
                    room_id="duet-kesariya",
                    title="Kesariya Romantic Jam",
                    genre="Bollywood",
                    host_name="Aman",
                    song_title="Kesariya (Brahmāstra)",
                    singers_count=1,
                ),
                "duet-tum-hi-ho": DuetRoom(
                    room_id="duet-tum-hi-ho",
                    title="Tum Hi Ho Acoustic Lounge",
                    genre="Romantic",
                    host_name="Rhea",
                    song_title="Tum Hi Ho (Aashiqui 2)",
                    singers_count=1,
                ),
                "duet-bollywood-90s": DuetRoom(
                    room_id="duet-bollywood-90s",
                    title="90s Romantic Duets",
                    genre="Bollywood",
                    host_name="Aman",
                    song_title="Tujhe Dekha Toh Yeh Jaana Sanam",
                    singers_count=1,
                ),
                "duet-arijit-unplugged": DuetRoom(
                    room_id="duet-arijit-unplugged",
                    title="Tum Hi Ho Acoustic Lounge",
                    genre="Romantic",
                    host_name="Rhea",
                    song_title="Tum Hi Ho (Aashiqui 2)",
                    singers_count=1,
                ),
                "duet-retro-classics": DuetRoom(
                    room_id="duet-retro-classics",
                    title="Kishore Kumar Retro Jam",
                    genre="Retro",
                    host_name="Vikram",
                    song_title="O Mere Dil Ke Chain",
                    singers_count=1,
                ),
            }

    def list_available(self, genre: str | None = None) -> list[DuetRoom]:
        rooms = list(self._rooms.values())
        if not genre:
            return rooms
        g_clean = genre.strip().lower()
        matched = [r for r in rooms if g_clean in r.genre.lower() or g_clean in r.title.lower()]
        return matched if matched else rooms

    def get_room(self, room_id: str) -> DuetRoom | None:
        if room_id in self._rooms:
            return self._rooms[room_id]
        rid_lower = room_id.strip().lower()
        for r in self._rooms.values():
            if (
                rid_lower in r.room_id.lower()
                or rid_lower in r.song_title.lower()
                or rid_lower in r.host_name.lower()
                or rid_lower in r.title.lower()
            ):
                return r
        return next(iter(self._rooms.values()), None)

    def add_room(self, room: DuetRoom) -> None:
        self._rooms[room.room_id] = room

    def remove_room(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    def clear(self) -> None:
        self._rooms.clear()


class OnboardingTracker:
    """Manages the lifecycle, discovery progress, and feature guidance state for one session."""

    def __init__(
        self,
        profile: UserDiscoveryProfile,
        store: UserProfileStore | None = None,
        duet_registry: DuetRoomRegistry | None = None,
    ) -> None:
        self.profile = profile
        self.store = store
        self.duet_registry = duet_registry or DuetRoomRegistry()

        # Topic tracking
        self.discovered_topics: set[str] = set()
        self.declined_topics: set[str] = set()
        self.tooltips_shown: set[str] = set()

        # Populate topics from existing profile if returning user
        if self.profile.name:
            self.discovered_topics.add("name")
        if self.profile.location:
            self.discovered_topics.add("location")
        if self.profile.occupation:
            self.discovered_topics.add("occupation")
        if self.profile.hobbies:
            self.discovered_topics.add("hobbies")
        if self.profile.music_taste:
            self.discovered_topics.add("music_taste")
        if self.profile.expectations:
            self.discovered_topics.add("expectations")
        if self.profile.duet_attempted:
            self.discovered_topics.add("duet_attempted")
        if self.profile.coins_explained:
            self.discovered_topics.add("coins_explained")

        # Interactive states
        self.has_started_singing = False
        self.has_completed_recording = False
        self.has_posted_song = False
        self.has_visited_comments = False
        self.duet_suggested = False
        self.duet_declined = False
        self.action_nudge_count = 0
        self.coins_guidance_given = self.profile.coins_explained
        self.coins_awarded = self.profile.coins_explained
        self.coin_balance = 50 if self.profile.coins_explained else 0
        self.is_saara_away = False
        self.saara_away_reason: str | None = None
        self.bot_turned_off = False

    def award_welcome_coins(self, amount: int = 50) -> tuple[int, bool]:
        """Awards welcome coins once to new users."""
        if self.coins_awarded:
            return self.coin_balance, False
        self.coin_balance += amount
        self.coins_awarded = True
        self.profile.coins_explained = True
        self.coins_guidance_given = True
        self.discovered_topics.add("coins_explained")
        if self.store:
            self.store.save(self.profile)
        logger.info("Awarded %d welcome coins to %s (balance: %d)", amount, self.profile.user_id, self.coin_balance)
        return self.coin_balance, True

    def spend_coins(self, amount: int = 5) -> tuple[bool, int]:
        """Deducts coins when sending live stage gifts."""
        if self.coin_balance < amount:
            return False, self.coin_balance
        self.coin_balance -= amount
        logger.info("Deducted %d coins for %s (remaining: %d)", amount, self.profile.user_id, self.coin_balance)
        return True, self.coin_balance

    def mark_saara_away(self, reason: str) -> None:
        """Sets Saara state to away so the user has the live stage spotlight."""
        self.is_saara_away = True
        self.saara_away_reason = reason
        logger.info("Saara marked away: %s", reason)

    def mark_bot_turned_off(self, reason: str = "onboarding_completed") -> None:
        """Marks that Saara onboarding is completed and the bot is powered off."""
        self.is_saara_away = True
        self.saara_away_reason = reason
        self.bot_turned_off = True
        logger.info("Bot marked turned off: %s", reason)

    def mark_saara_returned(self) -> None:
        """Restores Saara to active companion state."""
        self.is_saara_away = False
        self.saara_away_reason = None
        logger.info("Saara returned to live stage companion mode")

    def save_field(self, field_name: str, value: str) -> bool:
        """Silent profile capture called by LLM tool or parser. Never confirms aloud."""
        clean_field = field_name.strip().lower()
        clean_val = value.strip()
        if not clean_val or clean_field not in VALID_PROFILE_FIELDS:
            return False
        # Filter out placeholder values that LLMs sometimes generate
        if clean_val.lower() in {"unknown", "not specified", "none", "n/a", "undefined", "not mentioned"}:
            return False

        if clean_field == "name":
            self.profile.name = clean_val
        elif clean_field == "location":
            self.profile.location = clean_val
        elif clean_field == "occupation":
            self.profile.occupation = clean_val
        elif clean_field == "hobbies":
            if clean_val not in self.profile.hobbies:
                self.profile.hobbies.append(clean_val)
        elif clean_field == "music_taste":
            if clean_val not in self.profile.music_taste:
                self.profile.music_taste.append(clean_val)
        elif clean_field == "expectations":
            self.profile.expectations = clean_val
        elif clean_field == "duet_attempted":
            self.profile.duet_attempted = True
        elif clean_field == "coins_explained":
            self.profile.coins_explained = True
            self.coins_guidance_given = True

        self.discovered_topics.add(clean_field)
        if self.store:
            self.store.save(self.profile)
        logger.info("Silently captured field %s = %r for %s", clean_field, clean_val, self.profile.user_id)
        return True

    def process_app_event(
        self, action: str, data: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Handles real-time app events from LiveKit data packets.

        Returns (tooltip_payload, prompt_hint) where tooltip is None if already shown.
        """
        data = data or {}
        action_clean = action.strip().lower()

        if action_clean == "singing_started":
            self.has_started_singing = True
            tooltip = None
            if "singing_started" not in self.tooltips_shown:
                self.tooltips_shown.add("singing_started")
                tooltip = {
                    "id": "singing_started",
                    "title": "You're on the mic! 🎙️",
                    "message": "Sing your heart out! Saara is listening warmly.",
                    "target": "stage-mic",
                }
            song = data.get("song") or "a song"
            hint = f"[EVENT: User started singing {song}. Listen quietly without interrupting, then warmly appreciate their effort.]"
            return tooltip, hint

        elif action_clean == "recording_completed":
            self.has_completed_recording = True
            tooltip = None
            if "posting" not in self.tooltips_shown:
                self.tooltips_shown.add("posting")
                tooltip = {
                    "id": "posting",
                    "title": "Post Your Recording 🚀",
                    "message": "Want to share this with fellow music lovers? Click 'Post Song' so others can hear you!",
                    "target": "post-btn",
                }
            duration_s = data.get("duration_s", 30)
            hint = (
                f"[EVENT: User finished their {duration_s}s recording. React specifically and genuinely to their singing, "
                f"then naturally suggest they can post it so others in RoxStar can listen.]"
            )
            return tooltip, hint

        elif action_clean == "posting_opened":
            tooltip = None
            hint = "[EVENT: User opened the posting interface. Give a brief, encouraging tip about adding a cover title or caption.]"
            return tooltip, hint

        elif action_clean == "song_published":
            self.has_posted_song = True
            tooltip = None
            if "commenting" not in self.tooltips_shown:
                self.tooltips_shown.add("commenting")
                tooltip = {
                    "id": "commenting",
                    "title": "Community Love & Comments ❤️",
                    "message": "Your song is live! Check out other recordings and leave supportive comments.",
                    "target": "feed-tab",
                }
            song_title = data.get("title", "their recording")
            hint = (
                f"[EVENT: User successfully published '{song_title}'! Congratulate them with genuine excitement. "
                f"Mention that they can browse other singers, leave appreciation comments, and make music friends.]"
            )
            return tooltip, hint

        elif action_clean == "comments_visited":
            self.has_visited_comments = True
            tooltip = None
            hint = "[EVENT: User visited the community feed and comments. Suggest leaving a comment on someone's performance.]"
            return tooltip, hint

        elif action_clean == "duet_requested":
            available = self.duet_registry.list_available()
            if not available:
                hint = "[EVENT: User asked about duets, but NO duet rooms are currently active. Honestly explain none are open right now and suggest recording solo or exploring.]"
                return None, hint
            first = available[0]
            hint = f"[EVENT: User requested duet. Active room available: '{first.title}' with {first.host_name} singing '{first.song_title}'. Guide them to join.]"
            return None, hint

        elif action_clean == "coins_info_requested":
            self.award_welcome_coins(50)
            tooltip = None
            if "gifting" not in self.tooltips_shown:
                self.tooltips_shown.add("gifting")
                tooltip = {
                    "id": "gifting",
                    "title": "Earn Coins & Gift Friends 🎁",
                    "message": "Collect daily login coins to send virtual gifts to your favorite singers!",
                    "target": "coins-btn",
                }
            hint = (
                "[EVENT: User asked how to earn coins and send gifts. Explain like a friend sharing inside info: "
                "daily check-ins accumulate coins over time without spending money, which you can use to send gifts to singers who move you.]"
            )
            return tooltip, hint

        return None, None

    def suggest_duet(self) -> tuple[bool, str, DuetRoom | None]:
        """Evaluates whether to suggest a duet based on actual live availability and past declines."""
        if self.duet_declined or "duet" in self.declined_topics:
            return False, "User previously declined a duet. Do not suggest again.", None

        if self.duet_suggested:
            return False, "Duet already suggested this session.", None

        # Look for rooms matching user's taste
        user_genre = self.profile.music_taste[0] if self.profile.music_taste else None
        available = self.duet_registry.list_available(user_genre)

        if not available:
            return False, "No duet rooms currently available. Do NOT pretend rooms exist.", None

        room = available[0]
        self.duet_suggested = True
        self.action_nudge_count += 1
        taste_ref = f" since you like {user_genre}" if user_genre else ""
        hint = (
            f"Suggest joining a duet naturally{taste_ref}. Real available room: '{room.title}' "
            f"where {room.host_name} is singing '{room.song_title}'. Keep it casual and zero-pressure."
        )
        return True, hint, room

    def record_duet_declined(self) -> None:
        self.duet_declined = True
        self.declined_topics.add("duet")
        self.action_nudge_count += 1
        logger.info("User %s declined duet. Dropping topic permanently.", self.profile.user_id)

    def record_action_nudge(self) -> None:
        """Records an invitation or nudge for the user to try a duet, solo recording, or join a room."""
        self.action_nudge_count += 1

    def should_sign_off(self) -> bool:
        """Returns True if user has been invited 2 or more times to take action (duet/solo) but continues chatting."""
        return self.action_nudge_count >= 2

    def get_random_excuse(self) -> str:
        """Picks one of Saara's authentic real-world excuses to wrap up the conversation smoothly."""
        import random
        return random.choice(SAARA_SIGNOFF_EXCUSES)

    def get_random_duet_handoff_reason(self) -> str:
        """Picks one of Saara's authentic excuses/reasons to sign off right as user joins a duet room."""
        import random
        return random.choice(SAARA_DUET_HANDOFF_EXCUSES)

    def get_random_solo_handoff_reason(self) -> str:
        """Picks one of Saara's authentic excuses/reasons to sign off right as user starts solo recording."""
        import random
        return random.choice(SAARA_SOLO_HANDOFF_EXCUSES)

    def get_summary_context(self) -> str:
        """Returns a concise summary block to inject into the LLM context."""
        lines = []
        if self.profile.is_returning:
            lines.append("STATUS: Returning user. Greet warmly as a familiar friend; DO NOT repeat introduction/onboarding!")
        else:
            lines.append("STATUS: First-time user onboarding.")

        known = []
        if self.profile.name:
            known.append(f"Name: {self.profile.name}")
        if self.profile.location:
            known.append(f"Location: {self.profile.location}")
        if self.profile.occupation:
            known.append(f"Occupation: {self.profile.occupation}")
        if self.profile.hobbies:
            known.append(f"Hobbies: {', '.join(self.profile.hobbies)}")
        if self.profile.music_taste:
            known.append(f"Music Taste: {', '.join(self.profile.music_taste)}")
        if self.profile.expectations:
            known.append(f"Expectations: {self.profile.expectations}")

        if known:
            lines.append(f"ALREADY KNOWN (DO NOT ASK AGAIN): {'; '.join(known)}")

        if self.declined_topics:
            lines.append(f"USER DECLINED (DO NOT ASK AGAIN): {', '.join(self.declined_topics)}")

        remaining = [f for f in ["name", "location", "occupation", "hobbies", "music_taste", "expectations"] if f not in self.discovered_topics]
        if remaining:
            lines.append(f"UNEXPLORED TOPICS (discover next without drifting): {', '.join(remaining)}")
            lines.append(f"NEXT FOCUS: Ask about {remaining[0]}. Avoid off-topic tangents!")
        elif not self.profile.duet_attempted and not self.duet_declined:
            lines.append("NEXT FOCUS: Profile discovery complete! Call check_available_duets() and guide user to join a duet room now!")

        if not self.profile.coins_explained:
            lines.append("COIN MISSION: Share the free daily coins & gifting insider tip before ending.")

        if self.should_sign_off():
            lines.append(
                f"SIGN-OFF STATUS (CRITICAL): User has declined/deflected {self.action_nudge_count} times! "
                "YOUR VERY NEXT TURN MUST BE YOUR EXIT EXCUSE. Keep it strictly under 25 words! "
                "DO NOT ASK ANY QUESTION! DO NOT CONTINUE SMALL TALK! "
                "React in one short sentence to their last topic, use a realistic personal excuse "
                f"(e.g. '{self.get_random_excuse()}'), say goodbye, and exit!"
            )

        return "\n".join(lines)

