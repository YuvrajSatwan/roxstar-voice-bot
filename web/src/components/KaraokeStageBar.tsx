import React, { useEffect, useRef, useState } from 'react';
import {
  Award,
  Coins,
  Gift,
  Heart,
  MessageSquare,
  Mic,
  Music2,
  Pause,
  Play,
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
    genre: 'Bollywood',
    host_name: 'Aman',
    song_title: 'Kesariya (Brahmāstra)',
    singers_count: 1,
  },
  {
    room_id: 'duet-tum-hi-ho',
    title: 'Tum Hi Ho Acoustic Lounge',
    genre: 'Romantic',
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

  // Pillar 3 Karaoke Jam & Teleprompter state
  const [isJamming, setIsJamming] = useState(false);
  const [lyricIndex, setLyricIndex] = useState(0);
  const [pitchScore, setPitchScore] = useState(94);
  const [pitchTag, setPitchTag] = useState('Surila Vibe! 🔥');
  const [recentReactions, setRecentReactions] = useState<string[]>([
    '🌹 Pooja sent 5 Roses',
    '👏 24 listeners tuning in',
    '🔥 Mast aawaz!',
  ]);
  const [giftToast, setGiftToast] = useState<string | null>(null);
  const audioSynthRef = useRef<{ ctx: AudioContext | null; timer: number | null }>({ ctx: null, timer: null });

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
        const nextScore = Math.floor(90 + Math.random() * 8);
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

  const handleSendRose = async () => {
    if (!activeLiveDuet) return;
    if (coinBalance < 5) {
      setGiftToast('Need at least 5 coins! Ask Simran for free daily bonus.');
      setTimeout(() => setGiftToast(null), 3000);
      return;
    }

    if (onSendDuetGift) {
      await onSendDuetGift('rose', activeLiveDuet.host_name);
    }
    setRecentReactions((prev) => [`🌹 You sent a Rose to ${activeLiveDuet.host_name}!`, ...prev.slice(0, 3)]);
    setGiftToast(`Sent 🌹 Rose to ${activeLiveDuet.host_name}!`);
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
  }, [navigatedDuetRoom]);

  // Auto-launch Live Solo Recording Stage when Simran directs the user to record solo
  useEffect(() => {
    if (navigatedSoloRecording) {
      setActiveSoloStage({ song_title: navigatedSoloRecording });
      setIsRecording(true);
      setIsJamming(true);
      void onEmitAppEvent('singing_started', { song: navigatedSoloRecording });
      onClearSoloNavigation?.();
    }
  }, [navigatedSoloRecording]);

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
      await onEmitAppEvent('singing_started', { song: 'Tum Hi Ho' });
    } else {
      const duration = recordSeconds;
      setIsRecording(false);
      await onEmitAppEvent('recording_completed', {
        duration_s: duration,
        song: 'Tum Hi Ho',
      });
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
        setDuets(data.duets || []);
      }
    } catch {
      setDuets([]);
    } finally {
      setLoadingDuets(false);
    }
  };

  const handleJoinDuet = async (room: DuetRoomItem) => {
    await onEmitAppEvent('duet_requested', { room_id: room.room_id });
    setActiveLiveDuet(room);
    setShowDuetModal(false);
  };

  const handleDeclineDuet = async () => {
    await onDeclineDuet();
    setShowDuetModal(false);
  };

  const handleOpenCoins = async () => {
    setShowCoinsModal(true);
    await onEmitAppEvent('coins_info_requested');
  };

  const handleOpenComments = async () => {
    setShowCommentsModal(true);
    await onEmitAppEvent('comments_visited');
  };

  if (!isConnected) return null;

  return (
    <div className="karaoke-bar-container">
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
          className="karaoke-btn"
          title="Browse Available Duet Rooms"
        >
          <Users2 size={15} />
          <span>Duet Rooms</span>
        </button>

        {/* Free Coins & Gifts CTA */}
        <button
          type="button"
          onClick={handleOpenCoins}
          className="karaoke-btn"
          title="How to Earn Free Coins & Gift"
        >
          <Coins size={15} />
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
          <span>Comments</span>
        </button>
      </div>

      {/* Post Song Modal */}
      {showPostModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Music2 size={18} />
                <span>Publish Your Recording</span>
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
                Your vocal recording is ready! Share it with the RoxStar community so other
                music enthusiasts can listen, comment, and send gifts.
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
                <span>Post Song</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Duet Rooms Modal */}
      {showDuetModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Users2 size={18} />
                <span>Live Duet Rooms</span>
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
              {loadingDuets ? (
                <p className="duets-empty-note">Checking active duet rooms…</p>
              ) : duets.length === 0 ? (
                <div className="duets-empty-box">
                  <p className="duets-empty-title">No duet rooms available right now</p>
                  <p className="duets-empty-desc">
                    Nobody is singing a duet right now. You can record a solo song or check back
                    shortly!
                  </p>
                </div>
              ) : (
                <div className="duet-rooms-list">
                  {duets.map((r) => (
                    <div key={r.room_id} className="duet-room-card">
                      <div className="duet-room-card__info">
                        <span className="duet-room-card__title">{r.title}</span>
                        <span className="duet-room-card__meta">
                          {r.host_name} singing <em>{r.song_title}</em> · {r.genre}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleJoinDuet(r)}
                        className="duet-room-card__join-btn"
                      >
                        Join Duet
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
                Not Interested / Skip Duets
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Free Coins & Gifting Modal */}
      {showCoinsModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <Coins size={18} />
                <span>Earn Free Coins & Gifting</span>
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
                  <p>Log in every day to collect free coin rewards in your RoxStar wallet.</p>
                </div>
                <div className="coins-guide-item">
                  <span className="coins-badge">Singing Tasks</span>
                  <p>Record your first song or complete daily singing missions to earn bonus coins.</p>
                </div>
                <div className="coins-guide-item">
                  <span className="coins-badge">Community Gifting</span>
                  <p>Use your earned coins to send virtual roses, mics, and appreciation gifts to singers.</p>
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

      {/* Live Solo Recording Studio Stage Modal */}
      {activeSoloStage && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="duet-stage-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <span className="duet-live-badge">
                  <span className="duet-live-dot" /> LIVE RECORDING STUDIO
                </span>
                <span>{activeSoloStage.song_title}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="duet-stage-coins-pill" title="Recording time">
                  <Mic size={12} color="#ec4899" />
                  <span>{recordSeconds}s</span>
                </div>
                <button
                  type="button"
                  className="karaoke-modal__close"
                  onClick={() => {
                    setIsJamming(false);
                    setIsRecording(false);
                    setActiveSoloStage(null);
                  }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="karaoke-modal__body">
              <div className="duet-stage__singers-grid" style={{ gridTemplateColumns: '1fr' }}>
                {/* User Mic Live Card */}
                <div className="duet-singer-card duet-singer-card--user-active">
                  <div className="duet-singer-avatar" style={{ background: 'linear-gradient(135deg, #ec4899, #f43f5e)' }}>🎙️</div>
                  <span className="duet-singer-name">You (Lead Vocalist)</span>
                  <span className="duet-singer-role">Singing: {activeSoloStage.song_title}</span>
                  <div className="telemetry-pill" style={{ margin: 0, padding: '2px 8px', fontSize: '10px' }}>
                    <span style={{ color: '#0ea5e9' }}>● Mic Live · Recording ({recordSeconds}s)</span>
                  </div>
                </div>
              </div>

              {/* Karaoke Teleprompter & Backing Jam Control */}
              <div className="duet-teleprompter-box">
                <div className="duet-teleprompter-bar">
                  <div className="duet-teleprompter-status">
                    <span className="duet-teleprompter-pulse" />
                    <span>Synchronized Karaoke Teleprompter</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsJamming((prev) => !prev)}
                    className={`duet-jam-btn ${isJamming ? 'duet-jam-btn--active' : ''}`}
                    title={isJamming ? 'Pause Jam' : 'Play Instrumental & Teleprompter'}
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

                <div className="duet-lyrics-scroll-container">
                  {(activeSoloStage.song_title.toLowerCase().includes('kesariya')
                    ? KESARIYA_LYRICS
                    : TUM_HI_HO_LYRICS
                  ).map((line, idx) => {
                    const isCurrent = isJamming && idx === lyricIndex;
                    return (
                      <div
                        key={idx}
                        className={`duet-lyric-row ${isCurrent ? 'duet-lyric-row--current' : ''} duet-lyric-row--user`}
                      >
                        <span className="duet-lyric-singer-tag">
                          {isCurrent ? '🎤 Sing Now!' : 'Your Part'}
                        </span>
                        <div className="duet-lyric-text">{line.text}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Real-time Pitch & Performance Feedback Meter */}
              <div className="duet-pitch-card">
                <div className="duet-pitch-header">
                  <div className="duet-pitch-title">
                    <Trophy size={13} color="#ffd700" />
                    <span>Vocal Accuracy & Pitch</span>
                  </div>
                  <div className="duet-pitch-score-badge">
                    <span className="duet-pitch-pct">{isJamming ? `${pitchScore}%` : 'Ready'}</span>
                    <span className="duet-pitch-tag">{isJamming ? pitchTag : 'Singing On Air'}</span>
                  </div>
                </div>
                <div className="duet-pitch-bar-track">
                  <div
                    className="duet-pitch-bar-fill"
                    style={{ width: isJamming ? `${pitchScore}%` : '60%' }}
                  />
                </div>
              </div>
            </div>

            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-secondary"
                onClick={() => {
                  setIsJamming(false);
                  setIsRecording(false);
                  setActiveSoloStage(null);
                }}
              >
                Leave Studio
              </button>
              <button
                type="button"
                className="karaoke-modal__btn-primary"
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
                <span>Finish & Post Song</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Live Duet Stage (Demo Modal) */}
      {activeLiveDuet && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="duet-stage-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <span className="duet-live-badge">
                  <span className="duet-live-dot" /> LIVE DUET STAGE
                </span>
                <span>{activeLiveDuet.song_title}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className="duet-stage-coins-pill" title="Your current coin balance">
                  <Coins size={12} color="#ffd700" />
                  <span>{coinBalance} Coins</span>
                </div>
                <button
                  type="button"
                  className="karaoke-modal__close"
                  onClick={() => {
                    setIsJamming(false);
                    setActiveLiveDuet(null);
                  }}
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="karaoke-modal__body">
              <div className="duet-stage__singers-grid">
                {/* Host Singer */}
                <div className={`duet-singer-card ${isJamming && lyricIndex % 2 === 0 ? 'duet-singer-card--active' : ''}`}>
                  <div className="duet-singer-avatar">🎤</div>
                  <span className="duet-singer-name">{activeLiveDuet.host_name}</span>
                  <span className="duet-singer-role">Host · Part A</span>
                  <div className="telemetry-pill" style={{ margin: 0, padding: '2px 8px', fontSize: '10px' }}>
                    <span style={{ color: '#2ed573' }}>● On Air</span>
                  </div>
                </div>

                {/* Partner (User) */}
                <div className={`duet-singer-card ${isJamming && lyricIndex % 2 === 1 ? 'duet-singer-card--user-active' : ''}`}>
                  <div className="duet-singer-avatar" style={{ background: 'linear-gradient(135deg, #ec4899, #f43f5e)' }}>🎧</div>
                  <span className="duet-singer-name">You</span>
                  <span className="duet-singer-role">Partner · Part B</span>
                  <div className="telemetry-pill" style={{ margin: 0, padding: '2px 8px', fontSize: '10px' }}>
                    <span style={{ color: '#0ea5e9' }}>● Mic Live</span>
                  </div>
                </div>
              </div>

              {/* Karaoke Teleprompter & Backing Jam Control */}
              <div className="duet-teleprompter-box">
                <div className="duet-teleprompter-bar">
                  <div className="duet-teleprompter-status">
                    <span className="duet-teleprompter-pulse" />
                    <span>Synchronized Karaoke Teleprompter</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsJamming((prev) => !prev)}
                    className={`duet-jam-btn ${isJamming ? 'duet-jam-btn--active' : ''}`}
                    title={isJamming ? 'Pause Jam' : 'Play Instrumental & Teleprompter'}
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

                <div className="duet-lyrics-scroll-container">
                  {(activeLiveDuet.song_title.toLowerCase().includes('kesariya')
                    ? KESARIYA_LYRICS
                    : TUM_HI_HO_LYRICS
                  ).map((line, idx) => {
                    const isCurrent = isJamming && idx === lyricIndex;
                    return (
                      <div
                        key={idx}
                        className={`duet-lyric-row ${isCurrent ? 'duet-lyric-row--current' : ''} duet-lyric-row--${line.part}`}
                      >
                        <span className="duet-lyric-singer-tag">
                          {isCurrent ? line.badge : line.singer}
                        </span>
                        <div className="duet-lyric-text">{line.text}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Real-time Pitch & Performance Feedback Meter */}
              <div className="duet-pitch-card">
                <div className="duet-pitch-header">
                  <div className="duet-pitch-title">
                    <Trophy size={13} color="#ffd700" />
                    <span>Vocal Accuracy & Pitch</span>
                  </div>
                  <div className="duet-pitch-score-badge">
                    <span className="duet-pitch-pct">{isJamming ? `${pitchScore}%` : 'Ready'}</span>
                    <span className="duet-pitch-tag">{isJamming ? pitchTag : 'Tap Start Jamming'}</span>
                  </div>
                </div>
                <div className="duet-pitch-bar-track">
                  <div
                    className="duet-pitch-bar-fill"
                    style={{ width: isJamming ? `${pitchScore}%` : '50%' }}
                  />
                </div>
              </div>

              {/* Live Crowd Reactions & One-Click Gifting */}
              <div className="duet-audience-bar">
                <div className="duet-reactions-ticker">
                  {recentReactions.slice(0, 3).map((r, i) => (
                    <span key={i} className="duet-reaction-bubble">
                      {r}
                    </span>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={handleSendRose}
                  className="duet-gift-action-btn"
                  title="Send a Rose to the host using 5 coins"
                >
                  <Gift size={13} />
                  <span>Send Rose 🌹 (5 Coins)</span>
                </button>
              </div>

              {giftToast && <div className="duet-gift-toast">{giftToast}</div>}
            </div>

            <div className="karaoke-modal__footer">
              <button
                type="button"
                className="karaoke-modal__btn-secondary"
                onClick={() => {
                  setIsJamming(false);
                  setActiveLiveDuet(null);
                }}
              >
                Leave Duet Stage
              </button>
              <button
                type="button"
                className="karaoke-modal__btn-primary"
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
        </div>
      )}

      {/* Celebratory Free Coins Awarded Modal (Pillar 3 Dopamine Reward) */}
      {coinsAwardedEvent && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="coins-reward-modal">
            <div className="coins-reward-sparkles">✨ 🎉 ✨</div>
            <div className="coins-reward-icon-ring">
              <Coins size={36} className="coins-reward-gold" />
            </div>
            <h2 className="coins-reward-title">+{coinsAwardedEvent.amount} Free Coins Credited!</h2>
            <div className="coins-reward-balance-pill">
              <span>New Balance: {coinsAwardedEvent.balance} Roxstar Coins</span>
            </div>
            <p className="coins-reward-desc">
              {coinsAwardedEvent.reason} Simran unlocked your daily rewards! Use your coins on live stages to send Roses & cheer on your duet partner.
            </p>
            <button
              type="button"
              className="coins-reward-btn"
              onClick={onDismissCoinsReward}
            >
              Awesome! Let's Jam 🚀
            </button>
          </div>
        </div>
      )}

      {/* Comments & Community Modal */}
      {showCommentsModal && (
        <div className="karaoke-modal-backdrop" role="dialog" aria-modal="true">
          <div className="karaoke-modal">
            <div className="karaoke-modal__header">
              <div className="karaoke-modal__title">
                <MessageSquare size={18} />
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
                RoxStar is all about supporting fellow singers. Leave words of appreciation on
                recordings to brighten someone's day!
              </p>
              <div className="comment-sample-box">
                <div className="comment-sample">
                  <span className="comment-sample__author">Pooja:</span>
                  <span className="comment-sample__text">"What soulful vocals! Loved the high notes! ❤️"</span>
                </div>
                <div className="comment-sample">
                  <span className="comment-sample__author">Kunal:</span>
                  <span className="comment-sample__text">"Bahut badhiya gaya yaar! Keep it up! 🎶"</span>
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
                <span>Back to Studio</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
