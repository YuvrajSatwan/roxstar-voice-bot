import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Mic,
  MicOff,
  Music2,
  Gift,
  Send,
  LogOut,
  Plus,
  Eye,
  Star,
  Sparkles,
  Volume2,
} from 'lucide-react';
import { useStsRoom, type TranscriptItem } from '../hooks/useStsRoom';
import {
  announceReady,
  closeSimran,
  getNativeName,
  initBridge,
  onNativeMessage,
  waitForAuthToken,
} from '../bridge';
import './simran-webview.css';

const BACKGROUND_GRACE_MS = 30_000;
const HANDOFF_FALLBACK_MS = 20_000;
const END_GRACE_MS = 1_500;
const AUTH_WAIT_MS = 4_000;

type Phase = 'waiting-auth' | 'ready' | 'connecting' | 'live' | 'problem';

interface Problem {
  reason: 'busy' | 'rate_limited' | 'unauthorized' | 'mic_denied' | 'error';
  title: string;
  message: string;
}

const PROBLEMS: Record<Problem['reason'], Omit<Problem, 'reason'>> = {
  busy: {
    title: 'Simran abhi busy hai',
    message: 'Bahut saare log party room mein hain. Thodi der baad dobara aana!',
  },
  rate_limited: {
    title: 'Thodi der baad milte hain',
    message: 'Aap kai baar join kar chuke ho. Thodi der rest leke phir aana!',
  },
  unauthorized: {
    title: 'Login check nahi ho paya',
    message: 'App ko ek baar band karke dobara open karo.',
  },
  mic_denied: {
    title: 'Microphone permission chahiye',
    message: 'Simran ke saath gaane ke liye app settings mein mic allow karo.',
  },
  error: {
    title: 'Connection disconnect ho gaya',
    message: 'Live room connect nahi ho paya. Dobara try karo!',
  },
};

function classifyProblem(message: string): Problem['reason'] {
  const m = message.toLowerCase();
  if (m === 'busy') return 'busy';
  if (m === 'rate_limited') return 'rate_limited';
  if (m === 'unauthorized') return 'unauthorized';
  if (/permission|denied|notallowed|not allowed|microphone/.test(m)) return 'mic_denied';
  return 'error';
}

export function SimranWebViewPage(): React.ReactElement {
  const [phase, setPhase] = useState<Phase>('waiting-auth');
  const [problem, setProblem] = useState<Problem | null>(null);
  const [inputText, setInputText] = useState('');
  const [showGiftToast, setShowGiftToast] = useState(false);
  const [viewersCount, setViewersCount] = useState(48);

  const commentsEndRef = useRef<HTMLDivElement | null>(null);

  const {
    isConnected,
    isConnecting,
    isMuted,
    simranState,
    audioLevel,
    error,
    transcripts,
    navigatedDuetRoom,
    navigatedSoloRecording,
    botTurnedOff,
    coinBalance,
    connect,
    disconnect,
    toggleMute,
    sendTextTurn,
    triggerCoinsPopup,
  } = useStsRoom();

  const userName = useMemo(() => getNativeName() || 'Guest', []);

  // Track handoff targets
  const handoffRef = useRef<{ duet: string | null; solo: string | null }>({ duet: null, solo: null });
  handoffRef.current = { duet: navigatedDuetRoom, solo: navigatedSoloRecording };

  const hangUp = useCallback(
    (message: Parameters<typeof closeSimran>[0]) => {
      void disconnect();
      closeSimran(message);
    },
    [disconnect],
  );

  // 1) Bridge initialization & token handshake
  useEffect(() => {
    initBridge();
    announceReady();
    let alive = true;
    void waitForAuthToken(AUTH_WAIT_MS).then((token) => {
      if (!alive) return;
      if (token || import.meta.env.DEV) {
        setPhase('ready');
        // Auto-connect as soon as user opens room
        void connect(getNativeName() || 'Guest');
      } else {
        setProblem({ reason: 'unauthorized', ...PROBLEMS.unauthorized });
        setPhase('problem');
      }
    });
    return () => {
      alive = false;
    };
  }, [connect]);

  // 2) Live status tracking
  useEffect(() => {
    if (isConnected) setPhase('live');
    else if (isConnecting) setPhase('connecting');
  }, [isConnected, isConnecting]);

  // 3) Error classified cleanly without AI keywords
  useEffect(() => {
    if (!error || phase === 'problem') return;
    const reason = classifyProblem(error);
    void disconnect();
    setProblem({ reason, ...PROBLEMS[reason] });
    setPhase('problem');
  }, [error, phase, disconnect]);

  // 4) Handoff transition
  const handoffTarget = navigatedDuetRoom ? 'duet' : navigatedSoloRecording ? 'solo' : null;
  useEffect(() => {
    if (!handoffTarget) return;
    const close = () => {
      const h = handoffRef.current;
      if (h.duet) hangUp({ destination: 'duet', room_id: h.duet });
      else if (h.solo) hangUp({ destination: 'solo', song_title: h.solo });
    };
    if (botTurnedOff) {
      close();
      return;
    }
    const fallback = window.setTimeout(close, HANDOFF_FALLBACK_MS);
    return () => window.clearTimeout(fallback);
  }, [handoffTarget, botTurnedOff, hangUp]);

  // 5) Clean shutdown when session ends naturally
  useEffect(() => {
    if (!botTurnedOff || handoffTarget) return;
    const t = window.setTimeout(() => {
      if (!handoffRef.current.duet && !handoffRef.current.solo) {
        hangUp({ destination: 'none', reason: 'ended' });
      }
    }, END_GRACE_MS);
    return () => window.clearTimeout(t);
  }, [botTurnedOff, handoffTarget, hangUp]);

  // 6) App background grace timer
  useEffect(() => {
    let timer: number | undefined;
    const away = () => {
      if (timer !== undefined) return;
      timer = window.setTimeout(() => hangUp({ destination: 'none', reason: 'timeout' }), BACKGROUND_GRACE_MS);
    };
    const back = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
        timer = undefined;
      }
    };
    const onVisibility = () => (document.hidden ? away() : back());
    document.addEventListener('visibilitychange', onVisibility);
    const offNative = onNativeMessage((m) => {
      if (m.type === 'app.background') away();
      else if (m.type === 'app.foreground') back();
    });
    const onPageHide = () => void disconnect();
    window.addEventListener('pagehide', onPageHide);
    return () => {
      back();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onPageHide);
      offNative();
    };
  }, [hangUp, disconnect]);

  // 7) Scroll live comments feed smoothly
  useEffect(() => {
    commentsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  // Slight random drift for live viewers to feel organic
  useEffect(() => {
    const interval = setInterval(() => {
      setViewersCount((prev) => Math.max(38, Math.min(65, prev + (Math.random() > 0.5 ? 1 : -1))));
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleSendComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    void sendTextTurn(inputText.trim());
    setInputText('');
  };

  const handleSendGift = () => {
    triggerCoinsPopup(50, 'Welcome Reward Claimed');
    setShowGiftToast(true);
    setTimeout(() => setShowGiftToast(false), 3500);
  };

  const isSimranSpeaking = simranState === 'speaking';
  const rippleScale = isSimranSpeaking ? 1 + Math.min(audioLevel * 0.9, 0.45) : 1;

  return (
    <div className="roxstar-room-container">
      {/* ── TOP ROOM HEADER (Exact RoxStar sing_room header) ── */}
      <header className="roxstar-room-header">
        <div className="header-room-info">
          <div className="header-level-badge">
            <span className="level-number">1</span>
          </div>
          <div className="header-room-meta">
            <span className="room-name">Simran&apos;s Party Room 🎤</span>
            <span className="room-id">ID: 990835</span>
          </div>
        </div>

        <div className="header-right-actions">
          {/* Star Count */}
          <div className="header-pill header-star-pill">
            <Star size={11} className="star-icon" />
            <span>12.5k</span>
          </div>

          {/* Viewers Count */}
          <div className="header-pill header-viewers-pill">
            <Eye size={12} className="eye-icon" />
            <span>{viewersCount}</span>
          </div>

          {/* Leave Button */}
          <button
            type="button"
            className="header-exit-btn"
            onClick={() => hangUp({ destination: 'none', reason: 'ended' })}
            aria-label="Exit Party Room"
          >
            ✕
          </button>
        </div>
      </header>

      {/* ── SUB-BAR: DAILY EXP PROGRESS ── */}
      <div className="roxstar-sub-bar">
        <div className="exp-meta">
          <span className="exp-label">Daily Room EXP</span>
          <span className="exp-value">650 / 1500</span>
        </div>
        <div className="exp-progress-track">
          <div className="exp-progress-fill" style={{ width: '43%' }} />
        </div>
      </div>

      {/* ── MAIN STAGE AREA: 8 SEATS CONCERT GRID ── */}
      <main className="roxstar-stage-grid">
        {/* ROW 1: Seat 1 (Simran Host), Seat 2 (You), Seat 3, Seat 4 */}
        <div className="stage-row stage-row--primary">
          {/* Seat 1: Simran (Host) */}
          <div className="stage-seat stage-seat--host">
            <div className="seat-avatar-wrapper">
              {/* Dynamic Ripple Indicator (RoxStar DuetSpeakingIndicatorView) */}
              <div
                className={`speaking-ripple-container ${isSimranSpeaking ? 'speaking-ripple-container--active' : ''}`}
                style={{ transform: `scale(${rippleScale})` }}
              >
                <div className="ripple-ring ring-1" />
                <div className="ripple-ring ring-2" />
                <div className="ripple-ring ring-3" />
              </div>

              {/* Host Avatar */}
              <div className="seat-avatar host-avatar">
                <img
                  src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&auto=format&fit=crop&q=80"
                  alt="Simran"
                  className="avatar-img"
                  onError={(e) => {
                    // Fallback to elegant gradient avatar if offline
                    (e.target as HTMLElement).style.display = 'none';
                  }}
                />
                <div className="avatar-fallback-initial">S</div>
              </div>

              {/* Green Active Mic Status Badge */}
              <div className="seat-mic-status seat-mic-status--active">
                <Volume2 size={10} />
              </div>
            </div>

            <div className="seat-info">
              <span className="seat-host-badge">Lv.5 🎤</span>
              <span className="seat-user-name">Simran</span>
              <span className="seat-stars">⭐ 3.8k</span>
            </div>
          </div>

          {/* Seat 2: You (Guest) */}
          <div className="stage-seat stage-seat--user">
            <div className="seat-avatar-wrapper">
              <div className="seat-avatar user-avatar">
                <div className="avatar-user-initial">
                  {userName.charAt(0).toUpperCase()}
                </div>
              </div>

              {/* User Mic Status Badge */}
              <div className={`seat-mic-status ${isMuted ? 'seat-mic-status--muted' : 'seat-mic-status--active'}`}>
                {isMuted ? <MicOff size={10} /> : <Mic size={10} />}
              </div>
            </div>

            <div className="seat-info">
              <span className="seat-user-badge">You</span>
              <span className="seat-user-name">{userName}</span>
              <span className="seat-stars">⭐ 50</span>
            </div>
          </div>

          {/* Seat 3: Empty Seat */}
          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 3</span>
          </div>

          {/* Seat 4: Empty Seat */}
          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 4</span>
          </div>
        </div>

        {/* ROW 2: Seats 5, 6, 7, 8 */}
        <div className="stage-row stage-row--secondary">
          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 5</span>
          </div>

          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 6</span>
          </div>

          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 7</span>
          </div>

          <div className="stage-seat stage-seat--empty">
            <div className="seat-avatar-wrapper empty-seat-circle">
              <Plus size={16} className="plus-icon" />
            </div>
            <span className="seat-empty-label">Seat 8</span>
          </div>
        </div>
      </main>

      {/* ── LIVE SINGING QUEUE BANNER ── */}
      <div className="roxstar-queue-banner">
        <div className="queue-banner-left">
          <div className="queue-music-icon">
            <Music2 size={15} />
          </div>
          <div className="queue-banner-meta">
            <span className="queue-banner-title">Live Queue (1 Song)</span>
            <span className="queue-banner-subtitle">
              {handoffRef.current.solo || 'Diljit Dosanjh - Lover'}
            </span>
          </div>
        </div>

        <button
          type="button"
          className="queue-sing-btn"
          onClick={() => {
            void sendTextTurn('Hey Simran! Lets sing a duet together!');
          }}
        >
          SING
        </button>
      </div>

      {/* ── FLOATING LIVE COMMENTS FEED (Auto-scrolling over stage) ── */}
      <section className="roxstar-comments-container">
        {/* System Announcements */}
        <div className="comment-bubble comment-bubble--system">
          <span className="system-pill-badge">Notice</span>
          <span>Welcome to Simran&apos;s Room! Feel free to talk and sing together.</span>
        </div>

        <div className="comment-bubble comment-bubble--reward">
          <Sparkles size={13} className="reward-sparkle" />
          <span>🎁 50 Welcome Coins added to your wallet!</span>
        </div>

        {/* Live Conversation Stream as Chat Messages */}
        {transcripts.map((item: TranscriptItem) => {
          const isSimran = item.speaker === 'Simran' || item.speaker === 'Saraah';
          if (item.speaker === 'System') return null;

          return (
            <div
              key={item.id}
              className={`comment-bubble ${isSimran ? 'comment-bubble--host' : 'comment-bubble--user'}`}
            >
              <span className={`comment-sender ${isSimran ? 'comment-sender--host' : 'comment-sender--user'}`}>
                {isSimran ? 'Simran' : userName}:
              </span>
              <span className="comment-text">{item.text}</span>
            </div>
          );
        })}

        <div ref={commentsEndRef} />
      </section>

      {/* ── GIFT REWARD CELEBRATION TOAST ── */}
      {showGiftToast && (
        <div className="gift-celebration-toast">
          <Gift size={20} className="gift-toast-icon" />
          <div className="gift-toast-text">
            <strong>Welcome Bonus!</strong>
            <span>Claimed 50 RoxStar coins for your party room singing.</span>
          </div>
        </div>
      )}

      {/* ── CONNECTING / PROBLEM OVERLAYS ── */}
      {phase === 'connecting' && (
        <div className="roxstar-connecting-banner">
          <div className="connecting-pulse" />
          <span>Joining Simran&apos;s Party Room…</span>
        </div>
      )}

      {phase === 'problem' && problem && (
        <div className="roxstar-modal-scrim">
          <div className="roxstar-modal-card">
            <h3>{problem.title}</h3>
            <p>{problem.message}</p>
            <button
              type="button"
              className="modal-action-btn"
              onClick={() => hangUp({ destination: 'none', reason: problem.reason })}
            >
              OK
            </button>
          </div>
        </div>
      )}

      {/* ── BOTTOM CONTROL BAR (Exact RoxStar Party Room Actions) ── */}
      <footer className="roxstar-bottom-bar">
        {/* Text Comment Input Form */}
        <form onSubmit={handleSendComment} className="bottom-input-pill">
          <input
            type="text"
            placeholder="Let's talk..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={!isConnected}
            className="bottom-text-input"
          />
          <button type="submit" className="bottom-send-btn" disabled={!inputText.trim()}>
            <Send size={15} />
          </button>
        </form>

        {/* Action Buttons: Mic, Song, Gift, Exit */}
        <div className="bottom-action-buttons">
          {/* Mic Toggle Button */}
          <button
            type="button"
            className={`action-circle-btn ${isMuted ? 'action-circle-btn--muted' : 'action-circle-btn--mic-on'}`}
            onClick={() => void toggleMute()}
            title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
          >
            {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          {/* Song Request Button */}
          <button
            type="button"
            className="action-circle-btn action-circle-btn--music"
            onClick={() => {
              void sendTextTurn('Simran, can we sing Diljit Dosanjh - Lover?');
            }}
            title="Request Song"
          >
            <Music2 size={18} />
          </button>

          {/* Gift Box Button */}
          <button
            type="button"
            className="action-circle-btn action-circle-btn--gift"
            onClick={handleSendGift}
            title="Claim or send 50 coins gift"
          >
            <Gift size={18} />
            <span className="gift-badge-coin">{coinBalance > 0 ? coinBalance : 50}</span>
          </button>

          {/* Leave Room Button */}
          <button
            type="button"
            className="action-circle-btn action-circle-btn--leave"
            onClick={() => hangUp({ destination: 'none', reason: 'ended' })}
            title="Leave party room"
          >
            <LogOut size={17} />
          </button>
        </div>
      </footer>
    </div>
  );
}
