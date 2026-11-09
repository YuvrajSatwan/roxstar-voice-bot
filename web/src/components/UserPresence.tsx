import React from 'react';
import { Mic, MicOff, User } from 'lucide-react';

interface UserPresenceProps {
  name: string;
  onNameChange: (newName: string) => void;
  isMuted: boolean;
  isConnected: boolean;
}

export const UserPresence: React.FC<UserPresenceProps> = ({
  name,
  onNameChange,
  isMuted,
  isConnected,
}) => {
  return (
    <div className="user-presence-card">
      <div className="user-presence__avatar">
        <User size={18} className="user-presence__icon" />
      </div>

      <div className="user-presence__info">
        <div className="user-presence__name-row">
          {isConnected ? (
            <span className="user-presence__name">{name || 'You'}</span>
          ) : (
            <input
              type="text"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              className="user-presence__input"
              placeholder="Your Name (e.g. Rahul)"
              title="Click to edit your name"
            />
          )}
          <span className="user-presence__tag">Singer</span>
        </div>
        <p className="user-presence__meta">
          {isConnected
            ? isMuted
              ? 'Microphone muted'
              : 'Microphone active · Speaking live'
            : 'Join room to sing & chat'}
        </p>
      </div>

      <div className="user-presence__status">
        {isConnected ? (
          <span
            className={`user-mic-pill ${
              isMuted ? 'user-mic-pill--muted' : 'user-mic-pill--live'
            }`}
          >
            {isMuted ? <MicOff size={13} /> : <Mic size={13} />}
            <span>{isMuted ? 'Muted' : 'Mic Live'}</span>
          </span>
        ) : (
          <span className="user-mic-pill user-mic-pill--idle">Ready</span>
        )}
      </div>
    </div>
  );
};
