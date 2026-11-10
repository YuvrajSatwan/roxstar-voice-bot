import React from 'react';
import { Music2, Mic2, Sparkles, Flame, Sliders } from 'lucide-react';

interface QuickPromptsProps {
  onSelectPrompt: (prompt: string) => void;
  disabled?: boolean;
}

const KARAOKE_PROMPTS = [
  {
    icon: Music2,
    text: 'Meri voice ke liye ek mast Bollywood gaana suggest karo na?',
    category: 'Song Pick',
  },
  {
    icon: Mic2,
    text: 'Singing se pehle ek quick 1-minute vocal warmup batao!',
    category: 'Vocal Warmup',
  },
  {
    icon: Flame,
    text: 'Thoda stage fright ho raha hai, mujhe thoda hype up karo na!',
    category: 'Confidence Boost',
  },
  {
    icon: Sliders,
    text: 'Romantic gaane ke liye Studio preset aur reverb settings kya rakhun?',
    category: 'Studio FX',
  },
  {
    icon: Sparkles,
    text: 'Tumhara all-time favourite Hindi song kaunsa hai jam karne ke liye?',
    category: 'Jam Session',
  },
];

export const QuickPrompts: React.FC<QuickPromptsProps> = ({ onSelectPrompt, disabled }) => {
  return (
    <div className="quick-prompts-container">
      <div className="quick-prompts-label">
        <Sparkles size={14} className="quick-prompts-icon" />
        <span>Vibe with Simran (Click to ask or just speak naturally):</span>
      </div>

      <div className="quick-prompts-grid">
        {KARAOKE_PROMPTS.map((p, idx) => {
          const Icon = p.icon;
          return (
            <button
              key={idx}
              type="button"
              disabled={disabled}
              onClick={() => onSelectPrompt(p.text)}
              className="prompt-pill"
              title={p.text}
            >
              <Icon size={13} className="prompt-pill__icon" />
              <span className="prompt-pill__text">"{p.text}"</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
