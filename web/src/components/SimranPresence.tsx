import React from 'react';
import { SpeakingOrb } from './SpeakingOrb';
import { Coffee, Mic, MicOff, RotateCcw, Sparkles, User } from 'lucide-react';

export interface SimranPresenceProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking';
  audioLevel: number;
  isConnected: boolean;
  userName: string;
  onUserNameChange: (name: string) => void;
  isMuted: boolean;
  isSimranAway?: boolean;
  simranAwayReason?: string | null;
  onRejoinSimran?: () => void;
  isSaaraAway?: boolean;
  saaraAwayReason?: string | null;
  onRejoinSaara?: () => void;
  caption?: string | null;
}

const STATE_LABELS: Record<'idle' | 'listening' | 'thinking' | 'speaking', string> = {
  idle: 'Ready to jam',
  listening: 'Listening to you',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
};

export const SimranPresence: React.FC<SimranPresenceProps> = ({
  state,
  audioLevel,
  isConnected,
  userName,
  onUserNameChange,
  isMuted,
  isSimranAway,
  simranAwayReason,
  onRejoinSimran,
  isSaaraAway,
  saaraAwayReason,
  onRejoinSaara,
  caption,
}) => {
  const currentState = isConnected ? state : 'idle';
  const label = isConnected ? STATE_LABELS[currentState] : 'Offline';
  const away = isSimranAway !== undefined ? isSimranAway : (isSaaraAway || false);
  const awayReason = simranAwayReason || saaraAwayReason;
  const recallAction = onRejoinSimran || onRejoinSaara;

  return (
    <div className={`stage-card ${away ? 'stage-card--away' : ''}`} data-state={currentState}>
      {away ? (
        /* Stepped-Away Mode when handing over stage */
        <div className="stage-away-view">
          <div className="stage-away-icon-ring">
            <Coffee size={28} className="stage-away-icon" />
          </div>
          <div className="stage-identity">
            <h2 className="stage-name">Simran Stepped Aside</h2>
            <p className="stage-away-quote">
              "{awayReason || 'Chai ke liye gayi hoon, tum stage pe rock karna!'}"
            </p>
            <div className="stage-status-pill stage-status-pill--spotlight">
              <span className="duet-live-dot" />
              <span>Stage Spotlight is 100% Yours</span>
            </div>
            {recallAction && (
              <button
                type="button"
                onClick={recallAction}
                className="stage-recall-btn"
                title="Call Simran back to mic"
              >
                <RotateCcw size={13} />
                <span>Call Simran Back to Mic</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Central Living Presence Speaking Orb (StarMaker Pink-to-Purple 12,000 Particles) */}
          <div className="stage-glyph-center">
            <SpeakingOrb
              state={currentState}
              audioLevel={audioLevel}
              size="lg"
              caption={currentState === 'speaking' ? caption : undefined}
            />
          </div>

          {/* Identity & Status */}
          <div className="stage-identity">
            <h2 className="stage-name">Simran</h2>
            <p className="stage-role">Singing Buddy & Musical Friend</p>
            
            <div className="stage-status-pill" data-state={currentState}>
              <span className="stage-status-dot" />
              <span className="stage-status-label">{label}</span>
            </div>
          </div>
        </>
      )}

      {/* Intimate User Presence Strip */}
      <div className="stage-user-strip">
        <div className="stage-user-left">
          <div className="stage-user-avatar">
            <User size={13} />
          </div>
          {isConnected ? (
            <span className="stage-user-name">{userName || 'You'}</span>
          ) : (
            <input
              type="text"
              value={userName}
              onChange={(e) => onUserNameChange(e.target.value)}
              className="stage-user-input"
              placeholder="Your Name"
              title="Click to edit name"
            />
          )}
        </div>

        <div className="stage-user-right">
          {isConnected ? (
            <span className={`stage-mic-indicator ${isMuted ? 'stage-mic-indicator--muted' : 'stage-mic-indicator--live'}`}>
              {isMuted ? <MicOff size={11} /> : <Mic size={11} />}
              <span>{isMuted ? 'Muted' : 'Mic On'}</span>
            </span>
          ) : (
            <span className="stage-user-ready">Singer</span>
          )}
        </div>
      </div>
    </div>
  );
};

