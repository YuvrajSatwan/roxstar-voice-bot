import React from 'react';
import { AiGlyph } from './AiGlyph';
import { Coffee, Mic, MicOff, RotateCcw, Sparkles, User } from 'lucide-react';

interface SaraahPresenceProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking';
  audioLevel: number;
  isConnected: boolean;
  userName: string;
  onUserNameChange: (name: string) => void;
  isMuted: boolean;
  isSaaraAway?: boolean;
  saaraAwayReason?: string | null;
  onRejoinSaara?: () => void;
}

const STATE_LABELS: Record<'idle' | 'listening' | 'thinking' | 'speaking', string> = {
  idle: 'Ready to jam',
  listening: 'Listening to you',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
};

export const SaraahPresence: React.FC<SaraahPresenceProps> = ({
  state,
  audioLevel,
  isConnected,
  userName,
  onUserNameChange,
  isMuted,
  isSaaraAway = false,
  saaraAwayReason,
  onRejoinSaara,
}) => {
  const currentState = isConnected ? state : 'idle';
  const label = isConnected ? STATE_LABELS[currentState] : 'Offline';

  return (
    <div className={`stage-card ${isSaaraAway ? 'stage-card--away' : ''}`} data-state={currentState}>
      {isSaaraAway ? (
        /* Stepped-Away Mode when handing over stage */
        <div className="stage-away-view">
          <div className="stage-away-icon-ring">
            <Coffee size={28} className="stage-away-icon" />
          </div>
          <div className="stage-identity">
            <h2 className="stage-name">Saara Stepped Aside</h2>
            <p className="stage-away-quote">
              "{saaraAwayReason || 'Chai ke liye gayi hoon, tum stage pe rock karna!'}"
            </p>
            <div className="stage-status-pill stage-status-pill--spotlight">
              <span className="duet-live-dot" />
              <span>Stage Spotlight is 100% Yours</span>
            </div>
            {onRejoinSaara && (
              <button
                type="button"
                onClick={onRejoinSaara}
                className="stage-recall-btn"
                title="Call Saara back to mic"
              >
                <RotateCcw size={13} />
                <span>Call Saara Back to Mic</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* Central Living Presence Glyph */}
          <div className="stage-glyph-center">
            <AiGlyph state={currentState} audioLevel={audioLevel} size="lg" />
            {currentState === 'speaking' && (
              <div className="stage-glyph-halo" />
            )}
          </div>

          {/* Identity & Status */}
          <div className="stage-identity">
            <h2 className="stage-name">Saara</h2>
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
