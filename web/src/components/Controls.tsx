import React from 'react';
import { Mic, MicOff, PhoneCall, PhoneOff, Radio } from 'lucide-react';

interface ControlsProps {
  isConnected: boolean;
  isConnecting: boolean;
  isMuted: boolean;
  onToggleMute: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
  audioLevel?: number;
}

export const Controls: React.FC<ControlsProps> = ({
  isConnected,
  isConnecting,
  isMuted,
  onToggleMute,
  onConnect,
  onDisconnect,
  audioLevel = 0,
}) => {
  return (
    <div className="stage-controls">
      {isConnected ? (
        <div className="controls-connected-group">
          {/* Tactile Mic Button with Live Halo */}
          <div className="mic-btn-wrap">
            {!isMuted && audioLevel > 0.04 && (
              <div
                className="mic-btn-halo"
                style={{
                  transform: `scale(${1 + Math.min(0.5, audioLevel * 2)})`,
                  opacity: Math.min(0.7, audioLevel * 2.5),
                }}
              />
            )}
            <button
              type="button"
              onClick={onToggleMute}
              className={`mic-toggle-btn ${
                isMuted ? 'mic-toggle-btn--muted' : 'mic-toggle-btn--live'
              }`}
              title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
              aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
            >
              {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
          </div>

          {/* End Call Button */}
          <button
            type="button"
            onClick={onDisconnect}
            className="leave-btn"
            title="End call"
            aria-label="End call"
          >
            <PhoneOff size={16} />
            <span>End Call</span>
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={isConnecting}
          onClick={onConnect}
          className="start-call-btn"
        >
          {isConnecting ? (
            <>
              <Radio size={16} className="spin-icon" />
              <span>Connecting to Saraah…</span>
            </>
          ) : (
            <>
              <PhoneCall size={16} />
              <span>Start Voice Call</span>
            </>
          )}
        </button>
      )}
    </div>
  );
};
