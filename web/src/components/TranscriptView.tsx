import React, { useEffect, useRef, useState, useLayoutEffect } from 'react';
import { type TranscriptItem } from '../hooks/useStsRoom';
import { ArrowDown, Mic, Send, Music2, Sparkles, Mic2, Flame, Sliders } from 'lucide-react';
import { AiGlyph } from './AiGlyph';

interface TranscriptViewProps {
  transcripts: TranscriptItem[];
  simranState?: 'idle' | 'listening' | 'thinking' | 'speaking';
  saraahState?: 'idle' | 'listening' | 'thinking' | 'speaking';
  onSendMessage: (text: string) => void;
  disabled?: boolean;
}

const QUICK_SUGGESTIONS = [
  { icon: Music2, text: 'Suggest a song for my voice' },
  { icon: Mic2, text: '1-minute vocal warmup' },
  { icon: Flame, text: 'Hype me up before singing!' },
  { icon: Sliders, text: 'Which reverb preset to use?' },
];

export const TranscriptView: React.FC<TranscriptViewProps> = ({
  transcripts,
  simranState,
  saraahState,
  onSendMessage,
  disabled = false,
}) => {
  const currentState = simranState || saraahState || 'idle';
  const [inputText, setInputText] = useState('');
  const scrollerRef = useRef<HTMLDivElement>(null);
  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const atBottomRef = useRef(true);
  const [unseen, setUnseen] = useState(false);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    bottomAnchorRef.current?.scrollIntoView({ behavior, block: 'end' });
  };

  useEffect(() => {
    if (atBottomRef.current) {
      scrollToBottom('smooth');
    } else if (transcripts.length > 0) {
      setUnseen(true);
    }
  }, [transcripts, currentState]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const handleScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
      atBottomRef.current = nearBottom;
      if (nearBottom) setUnseen(false);
    };
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || disabled) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  return (
    <div className="conversation-panel">
      {/* Transcript Scroll Area */}
      <div ref={scrollerRef} className="conversation-body">
        {transcripts.length === 0 ? (
          <div className="conversation-empty">
            <div className="conversation-empty__glyph">
              <AiGlyph state={currentState} size="md" />
            </div>
            <h3 className="conversation-empty__title">Simran is here</h3>
            <p className="conversation-empty__body">
              Start speaking whenever you're ready, or tap a suggestion below to start jamming.
            </p>
          </div>
        ) : (
          <ol className="conversation-list" role="log" aria-live="polite">
            {transcripts
              .filter((t) => t.text && t.text.trim() !== '---' && t.text.trim() !== '--' && t.text.trim() !== '...' && t.text.trim() !== '-')
              .map((t) => {
                if (t.speaker === 'System') {
                return (
                  <li key={t.id} className="transcript-line transcript-line--system">
                    <Sparkles size={12} className="system-icon" />
                    <span>{t.text}</span>
                  </li>
                );
              }

              const isAi = t.speaker === 'Simran' || t.speaker === 'Saraah';
              return (
                <li
                  key={t.id}
                  className={`transcript-group ${
                    isAi ? 'transcript-group--ai' : 'transcript-group--user'
                  }`}
                >
                  <header className="transcript-group__head">
                    <span className="transcript-group__name">
                      {isAi ? 'Simran' : 'You'}
                    </span>
                    {isAi ? (
                      <span className="transcript-group__tag">Friend</span>
                    ) : (
                      <Mic
                        size={11}
                        className="transcript-group__channel"
                        aria-label="Spoken turn"
                      />
                    )}
                    <time className="transcript-group__time">{t.time}</time>
                  </header>

                  <p className="transcript-line__text">
                    {t.text}
                    {!t.isFinal && <span className="transcript-line__live">…</span>}
                  </p>
                </li>
              );
            })}

            {currentState === 'thinking' && (
              <li className="transcript-thinking">
                <AiGlyph state="thinking" size="xs" />
                <span>Simran is thinking…</span>
              </li>
            )}
          </ol>
        )}
        <div ref={bottomAnchorRef} style={{ height: 1 }} />
      </div>

      {/* Jump to bottom */}
      {unseen && (
        <button
          type="button"
          className="transcript-jump-btn"
          onClick={() => {
            scrollToBottom('smooth');
            setUnseen(false);
          }}
        >
          <ArrowDown size={13} />
          <span>New speech</span>
        </button>
      )}

      {/* Bottom Area: Quick suggestions + Composer */}
      <div className="conversation-bottom-area">
        {/* Sleek horizontal suggestions pills */}
        <div className="quick-chips-row">
          {QUICK_SUGGESTIONS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <button
                key={idx}
                type="button"
                disabled={disabled}
                onClick={() => onSendMessage(item.text)}
                className="quick-chip"
              >
                <Icon size={12} className="quick-chip__icon" />
                <span>{item.text}</span>
              </button>
            );
          })}
        </div>

        {/* Composer Bar */}
        <form onSubmit={handleSubmit} className="conversation-composer">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={disabled}
            placeholder={
              disabled
                ? 'Join call to chat with Simran…'
                : 'Type a message or song name (or just speak)…'
            }
            className="composer-input"
          />
          <button
            type="submit"
            disabled={disabled || !inputText.trim()}
            className="composer-send-btn"
            title="Send"
          >
            <Send size={14} />
          </button>
        </form>
      </div>
    </div>
  );
};
