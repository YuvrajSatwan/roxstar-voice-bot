import React, { useEffect, useRef, useState } from 'react';
import {
  Award,
  Coins,
  Crown,
  Flame,
  Gift,
  Heart,
  MessageSquare,
  Mic,
  Music2,
  Pause,
  Play,
  Rocket,
  RotateCcw,
  Share2,
  Sparkles,
  Square,
  Trophy,
  Users2,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';

export interface CoinsAwardedEvent {
  amount: number;
  balance: number;
  reason: string;
}

interface DuetRoomItem {
  room_id: string;
  title: string;
  genre: string;
  host_name: string;
  song_title: string;
  singers_count: number;
}

interface LyricLine {
  part: 'host' | 'user' | 'both';
  singer: string;
  badge: string;
  text: string;
}

interface FloatingGift {
  id: string;
  emoji: string;
  left: number; // percentage (35% to 85%)
}

const KESARIYA_LYRICS: LyricLine[] = [
  {
    part: 'host',
    singer: 'Aman',
    badge: 'Part A · Host Singing',
    text: 'Mujhko itna bataaye koi... kaise tujhse dil na lagaaye koi...',
  },
  {
    part: 'user',
    singer: 'You',
    badge: 'Part B · Your Mic On Air! 🎤',
    text: '✨ "Kesariya tera ishq hai piya... rang jaaun jo main haath lagaun!" ✨',
  },
  {
    part: 'host',
    singer: 'Aman',
    badge: 'Part A · Host Singing',
    text: 'Din beete saara teri fikr mein... rain saari teri khair mangu...',
  },
  {
    part: 'both',
    singer: 'Duet Harmony',
    badge: 'Both Sing Together 💖',
    text: '🌟 "Patjhad ke mausam mein bhi... rang ghol de bas tera chehra!" 🌟',
  },
];

const TUM_HI_HO_LYRICS: LyricLine[] = [
  {
    part: 'host',
    singer: 'Rhea',
    badge: 'Part A · Host Singing',
    text: 'Hum tere bin ab reh nahi sakte... tere bina kya wajood mera...',
  },
  {
    part: 'user',
    singer: 'You',
    badge: 'Part B · Your Mic On Air! 🎤',
    text: '✨ "Kyunki tum hi ho, ab tum hi ho... zindagi ab tum hi ho!" ✨',
  },
  {
    part: 'host',
    singer: 'Rhea',
    badge: 'Part A · Host Singing',
    text: 'Chain bhi, mera dard bhi... meri aashiqui ab tum hi ho...',
  },
  {
    part: 'both',
    singer: 'Duet Harmony',
    badge: 'Both Sing Together 💖',
    text: '🌟 "Tere liye hi jiya main... khud ko jo yun de diya hai!" 🌟',
  },
];

const FAMOUS_DUETS: DuetRoomItem[] = [
  {
    room_id: 'duet-kesariya',
    title: 'Kesariya Romantic Jam',
    genre: 'Bollywood Romance',
    host_name: 'Aman',
    song_title: 'Kesariya (Brahmāstra)',
    singers_count: 1,
  },
  {
    room_id: 'duet-tum-hi-ho',
    title: 'Tum Hi Ho Acoustic Lounge',
    genre: 'Soulful Ballad',
    host_name: 'Rhea',
    song_title: 'Tum Hi Ho (Aashiqui 2)',
    singers_count: 1,
  },
];

interface KaraokeStageBarProps {
  isConnected: boolean;
  navigatedDuetRoom?: string | null;
  onClearDuetNavigation?: () => void;
  navigatedSoloRecording?: string | null;
  onClearSoloNavigation?: () => void;
  onEmitAppEvent: (action: string, data?: Record<string, any>) => Promise<void>;
  onDeclineDuet: () => Promise<void>;
  coinBalance?: number;
  coinsAwardedEvent?: CoinsAwardedEvent | null;
  onDismissCoinsReward?: () => void;
  onSendDuetGift?: (gift: string, recipient: string) => Promise<void>;
  onStageModeChange?: (mode: 'lounge' | 'duet' | 'solo') => void;
  latestSimranTranscript?: string;
  onTriggerCoinsPopup?: (amount?: number, reason?: string) => void;
}

export const KaraokeStageBar: React.FC<KaraokeStageBarProps> = ({
  isConnected,
  navigatedDuetRoom,
  onClearDuetNavigation,
  navigatedSoloRecording,
  onClearSoloNavigation,
  onEmitAppEvent,
  onDeclineDuet,
  coinBalance = 0,
  coinsAwardedEvent,
  onDismissCoinsReward,
  onSendDuetGift,
  onStageModeChange,
  latestSimranTranscript,
  onTriggerCoinsPopup,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);

  // Modals state
  const [showPostModal, setShowPostModal] = useState(false);
  const [postTitle, setPostTitle] = useState('Tum Hi Ho (Unplugged Cover)');
  const [showDuetModal, setShowDuetModal] = useState(false);
  const [duets, setDuets] = useState<DuetRoomItem[]>([]);
  const [loadingDuets, setLoadingDuets] = useState(false);
  const [showCoinsModal, setShowCoinsModal] = useState(false);
  const [showCommentsModal, setShowCommentsModal] = useState(false);
  const [activeLiveDuet, setActiveLiveDuet] = useState<DuetRoomItem | null>(null);
  const [activeSoloStage, setActiveSoloStage] = useState<{ song_title: string } | null>(null);

  // StarMaker Karaoke Jam & Teleprompter state
  const [isJamming, setIsJamming] = useState(false);
  const [lyricIndex, setLyricIndex] = useState(0);
  const [pitchScore, setPitchScore] = useState(94);
  const [pitchTag, setPitchTag] = useState('Surila Vibe! 🔥');
  const [reverbPreset, setReverbPreset] = useState<'studio' | 'ktv' | 'concert'>('ktv');

  // Floating Gifts Particle System
  const [floatingGifts, setFloatingGifts] = useState<FloatingGift[]>([]);

  const [recentReactions, setRecentReactions] = useState<string[]>([
    '🌹 Pooja sent 5 Roses',
    '👏 2,480 listeners tuning in',
    '🔥 Mast aawaz!',
    '👑 Kunal cheered with VIP Crown',
  ]);
  const [giftToast, setGiftToast] = useState<string | null>(null);
  const audioSynthRef = useRef<{ ctx: AudioContext | null; timer: number | null }>({ ctx: null, timer: null });

  // Sync stage mode changes to parent
  useEffect(() => {
    if (activeLiveDuet) {
      onStageModeChange?.('duet');
    } else if (activeSoloStage) {
      onStageModeChange?.('solo');
    } else {
      onStageModeChange?.('lounge');
    }
  }, [activeLiveDuet, activeSoloStage, onStageModeChange]);

  const startBackingAudio = () => {
    try {
      stopBackingAudio();
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      audioSynthRef.current.ctx = ctx;

      const chords = [
        [196.0, 246.94, 293.66], // G maj
        [261.63, 329.63, 392.0],  // C maj
        [146.83, 220.0, 293.66],  // D maj
        [164.81, 196.0, 246.94],  // Em
      ];
      let step = 0;

      const triggerChord = () => {
        if (!ctx || ctx.state === 'closed') return;
        const now = ctx.currentTime;
        const freqs = chords[step % chords.length];
        step++;

        freqs.forEach((f, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          const filter = ctx.createBiquadFilter();

          filter.type = 'lowpass';
          filter.frequency.setValueAtTime(550, now);

          osc.type = 'sine';
          osc.frequency.setValueAtTime(f, now);

          gain.gain.setValueAtTime(0.001, now);
          gain.gain.exponentialRampToValueAtTime(0.04, now + 0.12 + idx * 0.06);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + 3.4);

          osc.connect(filter);
          filter.connect(gain);
          gain.connect(ctx.destination);

          osc.start(now + idx * 0.06);
          osc.stop(now + 3.5);
        });
      };

      triggerChord();
      audioSynthRef.current.timer = window.setInterval(triggerChord, 3500);
    } catch (e) {
      console.warn('Audio synth error:', e);
    }
  };

  const stopBackingAudio = () => {
    if (audioSynthRef.current.timer) {
      clearInterval(audioSynthRef.current.timer);
      audioSynthRef.current.timer = null;
    }
    if (audioSynthRef.current.ctx) {
      audioSynthRef.current.ctx.close().catch(() => {});
      audioSynthRef.current.ctx = null;
    }
  };

  // Auto-advance lyrics & simulated pitch score when Jamming is active
  useEffect(() => {
    let lyricTimer: number | null = null;
    let pitchTimer: number | null = null;

    if (isJamming && (activeLiveDuet || activeSoloStage)) {
      startBackingAudio();

      lyricTimer = window.setInterval(() => {
        setLyricIndex((prev) => (prev + 1) % 4);
      }, 3500);

      const tags = ['Surila Vibe! 🔥', 'Hit the Note! ⭐', 'Pitch Perfect 🎯', 'Great Harmony 🎶'];
      pitchTimer = window.setInterval(() => {
        const nextScore = Math.floor(91 + Math.random() * 8);
        setPitchScore(nextScore);
        setPitchTag(tags[Math.floor(Math.random() * tags.length)]);
      }, 2500);
    } else {
      stopBackingAudio();
      setLyricIndex(0);
    }

    return () => {
      if (lyricTimer) clearInterval(lyricTimer);
      if (pitchTimer) clearInterval(pitchTimer);
      stopBackingAudio();
    };
  }, [isJamming, activeLiveDuet, activeSoloStage]);

  // StarMaker Multi-Gift Launcher with floating particles
  const handleSendStarMakerGift = async (giftType: 'rose' | 'mic' | 'crown' | 'rocket', cost: number, emoji: string) => {
    if (!activeLiveDuet) return;
    if (coinBalance < cost) {
      setGiftToast(`Need ${cost} coins! Claim free coins first.`);
      if (onTriggerCoinsPopup) {
        onTriggerCoinsPopup(50, 'Daily Free Jam Bonus Claimed!');
      }
      setTimeout(() => setGiftToast(null), 3000);
      return;
    }

    if (onSendDuetGift) {
      await onSendDuetGift(giftType, activeLiveDuet.host_name);
    }

    // Spawn 3-4 floating gift particles
    const count = giftType === 'rocket' ? 5 : 3;
    const newParticles: FloatingGift[] = Array.from({ length: count }).map((_, i) => ({
      id: `${Date.now()}-${i}-${Math.random()}`,
      emoji,
      left: 35 + Math.random() * 50,
    }));
    setFloatingGifts((prev) => [...prev, ...newParticles]);

    setTimeout(() => {
      setFloatingGifts((prev) => prev.filter((p) => !newParticles.some((np) => np.id === p.id)));
    }, 2400);

    const giftTitles: Record<string, string> = {
      rose: 'Rose 🌹',
      mic: 'Golden Mic 🎙️',
      crown: 'VIP Crown 👑',
      rocket: 'Star Rocket 🚀',
    };
    const title = giftTitles[giftType] || emoji;

    setRecentReactions((prev) => [
      `${emoji} You sent ${title} to ${activeLiveDuet.host_name}!`,
      ...prev.slice(0, 3),
    ]);
    setGiftToast(`Sent ${title} to ${activeLiveDuet.host_name}!`);
    setTimeout(() => setGiftToast(null), 2500);
  };

  // Auto-launch Live Duet Stage when Simran directs the user to a duet
  useEffect(() => {
    if (navigatedDuetRoom) {
      const targetLower = navigatedDuetRoom.toLowerCase();
      const match =
        FAMOUS_DUETS.find(
          (r) =>
            r.room_id === navigatedDuetRoom ||
            targetLower.includes(r.room_id.toLowerCase()) ||
            targetLower.includes(r.song_title.toLowerCase().split(' ')[0]) ||
            targetLower.includes(r.host_name.toLowerCase())
        ) || FAMOUS_DUETS[0];
      setActiveLiveDuet(match);
      setIsJamming(true);
      setShowDuetModal(false);
      onClearDuetNavigation?.();
    }
  }, [navigatedDuetRoom, onClearDuetNavigation]);

  // Auto-launch Live Solo Recording Stage when Simran directs the user to record solo
  useEffect(() => {
    if (navigatedSoloRecording) {
      setActiveSoloStage({ song_title: navigatedSoloRecording });
      setIsRecording(true);
      setIsJamming(true);
      void onEmitAppEvent('singing_started', { song: navigatedSoloRecording });
      onClearSoloNavigation?.();
    }
  }, [navigatedSoloRecording, onClearSoloNavigation, onEmitAppEvent]);

  // Record timer
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } else {
      setRecordSeconds(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRecording]);

  const handleToggleSinging = async () => {
    if (!isRecording) {
      setIsRecording(true);
      setActiveSoloStage({ song_title: 'Tum Hi Ho' });
      setIsJamming(true);
      await onEmitAppEvent('singing_started', { song: 'Tum Hi Ho' });
    } else {
      const duration = recordSeconds;
      setIsRecording(false);
      setIsJamming(false);
      await onEmitAppEvent('recording_completed', {
        duration_s: duration,
        song: activeSoloStage ? activeSoloStage.song_title : 'Tum Hi Ho',
      });
      setActiveSoloStage(null);
      setShowPostModal(true);
      await onEmitAppEvent('posting_opened');
    }
  };

  const handlePublishSong = async () => {
    await onEmitAppEvent('song_published', { title: postTitle });
    setShowPostModal(false);
  };

  const handleOpenDuets = async () => {
    setShowDuetModal(true);
    setLoadingDuets(true);
    try {
      const res = await fetch('http://127.0.0.1:8001/duets');
      if (res.ok) {
        const data = await res.json();
        setDuets(data.duets || FAMOUS_DUETS);
      } else {
        setDuets(FAMOUS_DUETS);
      }
    } catch {
      setDuets(FAMOUS_DUETS);
    } finally {
      setLoadingDuets(false);
    }
  };

  const handleJoinDuet = async (room: DuetRoomItem) => {
    await onEmitAppEvent('duet_requested', { room_id: room.room_id });
    setActiveLiveDuet(room);
    setIsJamming(true);
    setShowDuetModal(false);
  };

  const handleDeclineDuet = async () => {
    await onDeclineDuet();
    setShowDuetModal(false);
  };

  const handleOpenCoins = async () => {
    if (onTriggerCoinsPopup) {
      onTriggerCoinsPopup(50, 'Daily Login Bonus Claimed');
    } else {
      setShowCoinsModal(true);
    }
    await onEmitAppEvent('coins_info_requested');
  };

  const handleOpenComments = async () => {
    setShowCommentsModal(true);
    await onEmitAppEvent('comments_visited');
  };

  // Helper for pitch score grade
  const getPitchGrade = (score: number) => {
    if (score >= 96) return { grade: 'SSS', label: 'PERFECT! 🎯', color: '#ec4899' };
    if (score >= 91) return { grade: 'SS', label: 'EXCELLENT! 🔥', color: '#8b5cf6' };
    if (score >= 85) return { grade: 'S', label: 'SURILA! ⭐', color: '#06b6d4' };
    return { grade: 'A', label: 'GOOD VIBE! 🎶', color: '#10b981' };
  };

  const { grade: pitchGrade, color: pitchColor } = getPitchGrade(pitchScore);

  if (!isConnected) return null;

  return (
    <div className="karaoke-bar-container">
      {/* Sleek StarMaker Quick-Action Bar in Lounge Mode */}
      {!activeLiveDuet && !activeSoloStage && (
        <div className="karaoke-bar">
          {/* Sing / Record CTA */}
          <button
            type="button"
            onClick={handleToggleSinging}
            className={`karaoke-btn ${isRecording ? 'karaoke-btn--recording' : 'karaoke-btn--sing'}`}
            title={isRecording ? 'Finish Recording' : 'Start Singing a Song'}
          >
            {isRecording ? (
              <>
                <Square size={15} fill="currentColor" />
                <span>Finish ({recordSeconds}s)</span>
              </>
            ) : (
              <>
                <Mic size={15} />
                <span>Sing / Record</span>
              </>
            )}
          </button>

          {/* Duet Rooms CTA */}
          <button
            type="button"
            onClick={handleOpenDuets}
            className="karaoke-btn karaoke-btn--duet"
            title="Browse Available Duet Rooms"
          >
            <Users2 size={15} />
            <span>Duet Jam</span>
          </button>

          {/* Free Coins & Gifts CTA */}
          <button
            type="button"
            onClick={handleOpenCoins}
            className="karaoke-btn karaoke-btn--coins"
            title="Claim Daily Free Coins & Send Gifts"
          >
            <Coins size={15} className="coin-gold-icon" />
            <span>Coins ({coinBalance})</span>
          </button>

          {/* Community & Comments CTA */}
          <button
            type="button"
            onClick={handleOpenComments}
            className="karaoke-btn"
            title="Explore Community & Comments"
          >
            <MessageSquare size={15} />
            <span>Community</span>
          </button>
        </div>
      )}

      {/* Floating Gift Particles Shower */}
      {floatingGifts.length > 0 && (
        <div className="starmaker-floating-gifts-portal" aria-hidden="true">
          {floatingGifts.map((gift) => (
            <div
              key={gift.id}
              className="starmaker-floating-gift"
              style={{ left: `${gift.left}%` }}
            >
              {gift.emoji}
            </div>
          ))}
        </div>
      )}

      {/* ================================================================
          STARMAKER LIVE DUET STAGE (FULL IMMERSIVE STAGE EXPERIENCE)
         ================================================================ */}
      {activeLiveDuet && (
        <div className="starmaker-stage-container" role="region" aria-label="StarMaker Live Duet Stage">
          {/* Top Live Stage Banner */}
          <div className="starmaker-stage-header">
            <div className="starmaker-stage-header__left">
              <span className="starmaker-live-badge">
                <span className="duet-live-dot" /> LIVE DUET ROOM
              </span>
              <div className="starmaker-stage-title-wrap">
                <h3 className="starmaker-stage-title">{activeLiveDuet.song_title}</h3>
                <span className="starmaker-stage-genre">{activeLiveDuet.genre} · Room #{activeLiveDuet.room_id}</span>
              </div>
            </div>

            <div className="starmaker-stage-header__right">
              <div className="starmaker-audience-counter">
                <span className="starmaker-audience-dot" />
                <span>2,481 listening</span>
              </div>

              <button
                type="button"
                onClick={handleOpenCoins}
                className="starmaker-coins-badge"
                title="Your Roxstar Coin Balance"
              >
                <Coins size={13} className="coin-gold-icon" />
                <span>{coinBalance}</span>
              </button>

              <button
                type="button"
                className="starmaker-stage-close-btn"
                onClick={() => {
                  setIsJamming(false);
                  setActiveLiveDuet(null);
                }}
                title="Exit Duet Stage"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Split Singer Stage Performers */}
          <div className="starmaker-performers-grid">
            {/* Host Singer (Part A) */}
            <div className={`starmaker-performer-card ${isJamming && lyricIndex % 2 === 0 ? 'starmaker-performer-card--active' : ''}`}>
              <div className="starmaker-performer-avatar-wrap">
                <div className="starmaker-performer-avatar">🎤</div>
                <span className="starmaker-vip-tag">VIP 4</span>
              </div>
              <span className="starmaker-performer-name">{activeLiveDuet.host_name}</span>
              <span className="starmaker-performer-role">Host · Part A</span>
              <div className="starmaker-on-air-pill">
                <span className="starmaker-pulse-dot" />
                <span>{isJamming && lyricIndex % 2 === 0 ? 'Singing Now' : 'Listening'}</span>
              </div>
            </div>

            {/* Harmony Battle / Blend Center Node */}
            <div className="starmaker-stage-center-hub">
              <div className="starmaker-vs-pill">
                <Sparkles size={14} className="starmaker-sparkle-spin" />
                <span>DUET</span>
              </div>
              <div className="starmaker-stage-lights-beam" />
            </div>

            {/* User (Partner - Part B) */}
            <div className={`starmaker-performer-card ${isJamming && lyricIndex % 2 === 1 ? 'starmaker-performer-card--user-active' : ''}`}>
              <div className="starmaker-performer-avatar-wrap">
                <div className="starmaker-performer-avatar starmaker-performer-avatar--user">🎧</div>
                <span className="starmaker-vip-tag starmaker-vip-tag--gold">VIP 1</span>
              </div>
              <span className="starmaker-performer-name">You</span>
              <span className="starmaker-performer-role">Partner · Part B</span>
              <div className="starmaker-on-air-pill starmaker-on-air-pill--live">
                <span className="starmaker-pulse-dot starmaker-pulse-dot--cyan" />
                <span>{isJamming && lyricIndex % 2 === 1 ? '🎤 Your Turn!' : 'Mic Live'}</span>
              </div>
            </div>
          </div>

          {/* VIP Front-Row Cheer Pod with Simran */}
          <div className="starmaker-simran-cheer-pod">
            <div className="starmaker-simran-avatar">
              <span className="starmaker-crown-icon">👑</span>
              <span className="starmaker-simran-face">✨</span>
            </div>
            <div className="starmaker-simran-content">
              <div className="starmaker-simran-header">
                <span className="starmaker-simran-title">Simran · VIP Front Row</span>
                <span className="starmaker-simran-badge">Cheering You On</span>
              </div>
              <p className="starmaker-simran-quote">
                "{latestSimranTranscript && latestSimranTranscript.length > 5
                  ? latestSimranTranscript
                  : isJamming
                  ? 'Kya sur lagaya hai! Dono ki harmony ekdum mast match ho rahi hai! 👏🔥'
                  : 'Stage tumhara hai! "Start Jamming" dabaao aur Kesariya pe rock karo! 🎤'}"
              </p>
            </div>
          </div>

          {/* StarMaker Synchronized Teleprompter with Bouncing Ball */}
          <div className="starmaker-teleprompter-card">
            <div className="starmaker-teleprompter-header">
              <div className="starmaker-teleprompter-title">
                <Music2 size={13} className="neon-cyan" />
                <span>Synchronized StarMaker Teleprompter</span>
              </div>
              <button
                type="button"
                onClick={() => setIsJamming((prev) => !prev)}
                className={`starmaker-jam-toggle-btn ${isJamming ? 'starmaker-jam-toggle-btn--playing' : ''}`}
                title={isJamming ? 'Pause Jam' : 'Start Instrumental Jam'}
              >
                {isJamming ? (
                  <>
                    <Pause size={12} fill="currentColor" />
                    <span>Pause Jam</span>
                  </>
                ) : (
                  <>
                    <Play size={12} fill="currentColor" />
                    <span>Start Jamming</span>
                  </>
                )}
              </button>
            </div>

            {/* Bouncing Ball Track */}
            <div className="starmaker-bounce-track" aria-hidden="true">
              <div
                className="starmaker-bounce-ball"
                style={{
                  left: `${((lyricIndex * 26 + 18) % 86)}%`,
                }}
              >
                🎵
              </div>
            </div>

            {/* Scrolling Karaoke Lyrics */}
            <div className="starmaker-lyrics-stream">
              {(activeLiveDuet.song_title.toLowerCase().includes('kesariya')
                ? KESARIYA_LYRICS
                : TUM_HI_HO_LYRICS
              ).map((line, idx) => {
                const isCurrent = isJamming && idx === lyricIndex;
                return (
                  <div
                    key={idx}
                    className={`starmaker-lyric-row ${
                      isCurrent ? 'starmaker-lyric-row--current' : ''
                    } starmaker-lyric-row--${line.part}`}
                  >
                    <span className="starmaker-lyric-singer-tag">
                      {isCurrent ? line.badge : line.singer}
                    </span>
                    <div className="starmaker-lyric-text">{line.text}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Real-time Vocal Pitch & Score Meter */}
          <div className="starmaker-pitch-meter-card">
            <div className="starmaker-pitch-header">
              <div className="starmaker-pitch-title">
                <Trophy size={14} className="coin-gold-icon" />
                <span>Vocal Accuracy & Pitch</span>
              </div>
              <div className="starmaker-pitch-badge-group">
                <span className="starmaker-pitch-grade" style={{ color: pitchColor }}>
                  {pitchGrade}
                </span>
                <span className="starmaker-pitch-score-number">{isJamming ? `${pitchScore}%` : 'Ready'}</span>
                <span className="starmaker-pitch-tag">{isJamming ? pitchTag : 'Tap Jam'}</span>
              </div>
            </div>
            <div className="starmaker-pitch-track">
              <div
                className="starmaker-pitch-fill"
                style={{
                  width: isJamming ? `${pitchScore}%` : '50%',
                  background: `linear-gradient(90deg, #3b82f6, #10b981, #f59e0b, ${pitchColor})`,
                }}
              />
            </div>
          </div>

          {/* StarMaker Multi-Gift Launcher Dock */}
          <div className="starmaker-gift-dock">
            <div className="starmaker-gift-dock__label">
              <Gift size={13} />
              <span>Cheer Stage:</span>
            </div>

            <div className="starmaker-gift-dock__actions">
              <button
                type="button"
                onClick={() => handleSendStarMakerGift('rose', 5, '🌹')}
                className="starmaker-gift-btn"
                title="Send Rose (5 Coins)"
              >
                <span className="starmaker-gift-emoji">🌹</span>
                <span className="starmaker-gift-cost">5 C</span>
              </button>

              <button
                type="button"
                onClick={() => handleSendStarMakerGift('mic', 10, '🎙️')}
                className="starmaker-gift-btn"
                title="Send Golden Mic (10 Coins)"
              >
                <span className="starmaker-gift-emoji">🎙️</span>
                <span className="starmaker-gift-cost">10 C</span>
              </button>

              <button
                type="button"
                onClick={() => handleSendStarMakerGift('crown', 25, '👑')}
                className="starmaker-gift-btn"
                title="Send VIP Crown (25 Coins)"
              >
                <span className="starmaker-gift-emoji">👑</span>
                <span className="starmaker-gift-cost">25 C</span>
              </button>

              <button
                type="button"
                onClick={() => handleSendStarMakerGift('rocket', 50, '🚀')}
                className="starmaker-gift-btn starmaker-gift-btn--rocket"
                title="Send Star Rocket (50 Coins)"
              >
                <span className="starmaker-gift-emoji">🚀</span>
                <span className="starmaker-gift-cost">50 C</span>
              </button>
            </div>

            {giftToast && <div className="starmaker-gift-toast">{giftToast}</div>}
          </div>

          {/* Live Audience Reactions Ticker */}
          <div className="starmaker-audience-ticker">
            {recentReactions.slice(0, 3).map((r, i) => (
              <span key={i} className="starmaker-reaction-chip">
                {r}
              </span>
            ))}
          </div>

          {/* Stage Action Footer */}
          <div className="starmaker-stage-footer">
            <button
              type="button"
              className="starmaker-footer-btn-secondary"
              onClick={() => {
                setIsJamming(false);
                setActiveLiveDuet(null);
              }}
            >
              Leave Duet Stage
            </button>
            <button
              type="button"
              className="starmaker-footer-btn-primary"
              onClick={() => {
                setIsJamming(false);
                setActiveLiveDuet(null);
                setPostTitle(`${activeLiveDuet.song_title} (Duet with ${activeLiveDuet.host_name})`);
                setShowPostModal(true);
              }}
            >
              <Share2 size={14} />
              <span>Finish & Post Duet</span>
            </button>
          </div>
        </div>
      )}

      {/* ================================================================
          STARMAKER SOLO RECORDING STUDIO STAGE
         ================================================================ */}
      {activeSoloStage && (
        <div className="starmaker-stage-container" role="region" aria-label="StarMaker Solo Recording Stage">
          {/* Top Live Studio Banner */}
          <div className="starmaker-stage-header">
            <div className="starmaker-stage-header__left">
              <span className="starmaker-live-badge starmaker-live-badge--record">
                <span className="duet-live-dot" /> SOLO RECORDING STUDIO
              </span>
              <div className="starmaker-stage-title-wrap">
                <h3 className="starmaker-stage-title">{activeSoloStage.song_title}</h3>
                <span className="starmaker-stage-genre">High-Fidelity Studio Vocal Booth</span>
              </div>
            </div>

            <div className="starmaker-stage-header__right">
              <div className="starmaker-record-timer-pill">
                <Mic size={12} className="neon-pink" />
                <span>{recordSeconds}s</span>
              </div>

              <button
                type="button"
                className="starmaker-stage-close-btn"
                onClick={() => {
                  setIsJamming(false);
                  setIsRecording(false);
                  setActiveSoloStage(null);
                }}
                title="Exit Studio"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Solo Lead Vocalist Center Display */}
          <div className="starmaker-solo-vocal-display">
            <div className="starmaker-solo-mic-halo">
              <div className="starmaker-solo-mic-icon">🎙️</div>
              <div className="starmaker-solo-soundwave-ring" />
            </div>
            <h4 className="starmaker-solo-title">Lead Vocal Mic Active</h4>
            <span className="starmaker-solo-sub">Sing loudly and clearly into your headset</span>

            {/* Studio Reverb Preset Selector */}
            <div className="starmaker-fx-selector">
              <button
                type="button"
                className={`starmaker-fx-btn ${reverbPreset === 'studio' ? 'starmaker-fx-btn--active' : ''}`}
                onClick={() => setReverbPreset('studio')}
              >
                Studio Clean
              </button>
              <button
                type="button"
                className={`starmaker-fx-btn ${reverbPreset === 'ktv' ? 'starmaker-fx-btn--active' : ''}`}
                onClick={() => setReverbPreset('ktv')}
              >
                KTV Hall Reverb
              </button>
              <button
                type="button"
                className={`starmaker-fx-btn ${reverbPreset === 'concert' ? 'starmaker-fx-btn--active' : ''}`}
                onClick={() => setReverbPreset('concert')}
              >
                Concert Arena
              </button>
            </div>
          </div>

          {/* Teleprompter */}
          <div className="starmaker-teleprompter-card">
            <div className="starmaker-teleprompter-header">
              <div className="starmaker-teleprompter-title">
                <Music2 size={13} className="neon-cyan" />
                <span>Synchronized Lyrics Teleprompter</span>
              </div>
              <button
                type="button"
                onClick={() => setIsJamming((prev) => !prev)}
                className={`starmaker-jam-toggle-btn ${isJamming ? 'starmaker-jam-toggle-btn--playing' : ''}`}
              >
                {isJamming ? (
                  <>
                    <Pause size={12} fill="currentColor" />
                    <span>Pause Jam</span>
                  </>
                ) : (
                  <>
                    <Play size={12} fill="currentColor" />
                    <span>Start Jamming</span>
                  </>
                )}
              </button>
            </div>

            <div className="starmaker-bounce-track" aria-hidden="true">
              <div
                className="starmaker-bounce-ball"
                style={{
                  left: `${((lyricIndex * 26 + 18) % 86)}%`,
                }}
              >
                🎵
              </div>
            </div>

            <div className="starmaker-lyrics-stream">
              {(activeSoloStage.song_title.toLowerCase().includes('kesariya')
                ? KESARIYA_LYRICS
                : TUM_HI_HO_LYRICS
              ).map((line, idx) => {
                const isCurrent = isJamming && idx === lyricIndex;
                return (
                  <div
                    key={idx}
                    className={`starmaker-lyric-row ${
                      isCurrent ? 'starmaker-lyric-row--current' : ''
                    } starmaker-lyric-row--user`}
                  >
                    <span className="starmaker-lyric-singer-tag">
                      {isCurrent ? '🎤 Sing on Air!' : 'Your Vocal Line'}
                    </span>
                    <div className="starmaker-lyric-text">{line.text}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Vocal Pitch Bar */}
          <div className="starmaker-pitch-meter-card">
            <div className="starmaker-pitch-header">
              <div className="starmaker-pitch-title">
                <Trophy size={14} className="coin-gold-icon" />
                <span>Pitch Accuracy</span>
              </div>
              <div className="starmaker-pitch-badge-group">
                <span className="starmaker-pitch-grade" style={{ color: pitchColor }}>
                  {pitchGrade}
                </span>
                <span className="starmaker-pitch-score-number">{isJamming ? `${pitchScore}%` : 'Ready'}</span>
                <span className="starmaker-pitch-tag">{isJamming ? pitchTag : 'Singing On Air'}</span>
              </div>
            </div>
            <div className="starmaker-pitch-track">
              <div
                className="starmaker-pitch-fill"
                style={{
                  width: isJamming ? `${pitchScore}%` : '60%',
                  background: `linear-gradient(90deg, #3b82f6, #10b981, #f59e0b, ${pitchColor})`,
                }}
              />
            </div>
          </div>

          {/* Footer Controls */}
          <div className="starmaker-stage-footer">
            <button
              type="button"
              className="starmaker-footer-btn-secondary"
              onClick={() => {
                setIsJamming(false);
                setIsRecording(false);
                setActiveSoloStage(null);
              }}
            >
              Discard & Leave
            </button>
            <button
              type="button"
              className="starmaker-footer-btn-primary"
              onClick={async () => {
                const dur = recordSeconds;
                setIsJamming(false);
                setIsRecording(false);
                await onEmitAppEvent('recording_completed', { duration_s: dur, song: activeSoloStage.song_title });
                setPostTitle(`${activeSoloStage.song_title} (Solo Vocal)`);
                setActiveSoloStage(null);
                setShowPostModal(true);
                await onEmitAppEvent('posting_opened');
              }}
            >
              <Square size={14} fill="currentColor" />
              <span>Finish & Post Song ({recordSeconds}s)</span>
            </button>
          </div>
        </div>
      )}

      {/* ================================================================
          STARMAKER FREE COINS CELEBRATION REWARD POPUP
         ================================================================ */}
      {coinsAwardedEvent && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="starmaker-coins-reward-modal">
            <div className="starmaker-coins-sunburst" />
            <div className="starmaker-coins-reward-sparkles">✨ 🌟 🎉 🌟 ✨</div>

            <div className="starmaker-coins-gold-chest">
              <div className="starmaker-coins-spinning-coin">🪙</div>
            </div>

            <h2 className="starmaker-coins-headline">+{coinsAwardedEvent.amount} Free Coins Unlocked!</h2>
            <div className="starmaker-coins-balance-pill">
              <Coins size={14} className="coin-gold-icon" />
              <span>Wallet: {coinsAwardedEvent.balance} Roxstar Coins</span>
            </div>

            <p className="starmaker-coins-desc">
              {coinsAwardedEvent.reason}. Simran added welcome coins to your account! Spend them on live stages to send 🌹 Roses, 🎙️ Golden Mics, and 🚀 Rockets to fellow singers.
            </p>

            <button
              type="button"
              className="starmaker-coins-claim-btn"
              onClick={onDismissCoinsReward}
            >
              <Sparkles size={16} />
              <span>Awesome! Let's Jam 🚀</span>
            </button>
          </div>
        </div>
      )}

      {/* ================================================================
          DUET ROOMS BROWSER MODAL (STARMAKER DISCOVERY STYLE)
         ================================================================ */}
      {showDuetModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="starmaker-duet-list-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Users2 size={18} className="neon-cyan" />
                <span>Live Duet Jam Rooms</span>
              </div>
              <button
                type="button"
                className="karaoke-modal__close"
                onClick={() => setShowDuetModal(false)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="karaoke-modal__body">
              <p className="starmaker-modal-sub">
                Sing along with community vocalists! Pick a room and join Part B in real time.
              </p>

              {loadingDuets ? (
                <div className="starmaker-loading-box">
                  <div className="starmaker-loading-spinner" />
                  <p>Searching for live singers…</p>
                </div>
              ) : duets.length === 0 ? (
                <div className="duets-empty-box">
                  <p className="duets-empty-title">No duet rooms active right now</p>
                  <p className="duets-empty-desc">
                    Be the first! Start a solo recording or check back shortly.
                  </p>
                </div>
              ) : (
                <div className="starmaker-duet-cards-list">
                  {duets.map((r) => (
                    <div key={r.room_id} className="starmaker-duet-card-item">
                      <div className="starmaker-duet-card-avatar">
                        <span className="starmaker-card-icon">🎤</span>
                        <span className="starmaker-card-live-dot" />
                      </div>

                      <div className="starmaker-duet-card-info">
                        <div className="starmaker-card-title-row">
                          <h4 className="starmaker-card-song">{r.song_title}</h4>
                          <span className="starmaker-card-genre">{r.genre}</span>
                        </div>
                        <p className="starmaker-card-host">
                          Host: <strong>{r.host_name}</strong> · Part A recorded
                        </p>
                        <span className="starmaker-card-badge">Open for Part B · 1-Tap Join</span>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleJoinDuet(r)}
                        className="starmaker-join-duet-btn"
                      >
                        Join Duet 🎶
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-secondary"
                onClick={handleDeclineDuet}
              >
                Not Now / Skip Duets
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================
          POST SONG MODAL
         ================================================================ */}
      {showPostModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Music2 size={18} className="neon-pink" />
                <span>Publish to RoxStar Stage</span>
              </div>
              <button
                type="button"
                className="karaoke-modal__close"
                onClick={() => setShowPostModal(false)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="karaoke-modal__body">
              <p className="karaoke-modal__desc">
                Your vocal track is mastered and ready! Post it to the community feed where Simran and other singers can listen and comment.
              </p>
              <label className="karaoke-modal__label">
                <span>Song Title</span>
                <input
                  type="text"
                  value={postTitle}
                  onChange={(e) => setPostTitle(e.target.value)}
                  className="karaoke-modal__input"
                />
              </label>

              <div className="starmaker-post-tags">
                <span className="starmaker-tag">#RoxStarKaraoke</span>
                <span className="starmaker-tag">#SimranBuddy</span>
                <span className="starmaker-tag">#BollywoodVibes</span>
              </div>
            </div>
            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-secondary"
                onClick={() => setShowPostModal(false)}
              >
                Save as Draft
              </button>
              <button
                type="button"
                className="karaoke-modal__btn-primary"
                onClick={handlePublishSong}
              >
                <Share2 size={14} />
                <span>Post Song 🚀</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================
          COINS & REWARDS GUIDE MODAL
         ================================================================ */}
      {showCoinsModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Coins size={18} className="coin-gold-icon" />
                <span>RoxStar Coins & Gifting</span>
              </div>
              <button
                type="button"
                className="karaoke-modal__close"
                onClick={() => setShowCoinsModal(false)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="karaoke-modal__body">
              <div className="coins-guide-card">
                <div className="coins-guide-item">
                  <span className="coins-badge">Daily Check-in</span>
                  <p>Open RoxStar daily to receive 50 Free Welcome Coins directly in your wallet.</p>
                </div>
                <div className="coins-guide-item">
                  <span className="coins-badge">Singing Missions</span>
                  <p>Complete singing challenges and solo recordings to unlock special coin drops.</p>
                </div>
                <div className="coins-guide-item">
                  <span className="coins-badge">Live Stage Gifting</span>
                  <p>Use your coins to cheer on duet partners with Roses (5 C), Mics (10 C), Crowns (25 C), and Rockets (50 C).</p>
                </div>
              </div>
            </div>
            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-primary"
                onClick={() => setShowCoinsModal(false)}
              >
                Got It!
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================
          COMMUNITY & COMMENTS MODAL
         ================================================================ */}
      {showCommentsModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <MessageSquare size={18} className="neon-cyan" />
                <span>Community & Comments</span>
              </div>
              <button
                type="button"
                className="karaoke-modal__close"
                onClick={() => setShowCommentsModal(false)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="karaoke-modal__body">
              <p className="karaoke-modal__desc">
                RoxStar is all about encouraging fellow singers. Leave words of appreciation on
                recordings to brighten someone's day!
              </p>
              <div className="comment-sample-box">
                <div className="comment-sample">
                  <span className="comment-sample__author">Pooja:</span>
                  <span className="comment-sample__text">"What soulful vocals! Loved your high notes on Kesariya! ❤️"</span>
                </div>
                <div className="comment-sample">
                  <span className="comment-sample__author">Kunal:</span>
                  <span className="comment-sample__text">"Bahut badhiya gaya yaar! Keep it up! 🎶"</span>
                </div>
                <div className="comment-sample">
                  <span className="comment-sample__author">Simran (AI Buddy):</span>
                  <span className="comment-sample__text">"Next time hum dono sath mein duet gayenge! Super proud! 🌟"</span>
                </div>
              </div>
            </div>
            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-primary"
                onClick={() => setShowCommentsModal(false)}
              >
                <Heart size={14} />
                <span>Back to Stage</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
