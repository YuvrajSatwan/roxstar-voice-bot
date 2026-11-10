import React, { useState, useEffect, useRef } from 'react';
import {
  Check,
  Music,
  Play,
  RotateCcw,
  Sliders,
  Smile,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
  X,
  Zap,
} from 'lucide-react';

export interface LaughSample {
  id: string;
  title: string;
  category: 'chuckle' | 'giggle' | 'sarcastic' | 'cozy' | 'off';
  badge: string;
  text: string;
  description: string;
  laughPhonetics: string;
}

export const LAUGH_SAMPLES: LaughSample[] = [
  {
    id: 'sarojini',
    title: 'The Sarojini Bargain Chuckle',
    category: 'chuckle',
    badge: 'Warm Breathy Chuckle',
    text: 'Haha yaar! Sarojini mein paanch sau bola toh bhaiya ne dukaan se hi nikal diya! Sach mein, alag hi beizzati hui!',
    description: 'Spontaneous warm breathy chuckle when recalling funny Delhi experiences.',
    laughPhonetics: 'Haha yaar',
  },
  {
    id: 'bathroom_singer',
    title: 'The Bathroom Singer Giggle',
    category: 'giggle',
    badge: 'Cute Girly Giggle',
    text: 'Hehe, bathroom mein Kishore Kumar aur stage pe silent mode? Meri bhi same kahani hai yaar!',
    description: 'Lighthearted, cute giggle bonding over shared bathroom singer confessions.',
    laughPhonetics: 'Hehe',
  },
  {
    id: 'sarcastic_haaye',
    title: 'The Sarcastic Haaye Laugh',
    category: 'sarcastic',
    badge: 'Dramatic Teasing Laugh',
    text: 'Haha haaye! Sone ko hobby bana liya? Alag hi level ka talent hai yaar tumhara!',
    description: 'High-energy, teasing laugh expressing comic disbelief and affection.',
    laughPhonetics: 'Haha haaye!',
  },
  {
    id: 'chai_escape',
    title: 'The Late-Night Chai Giggler',
    category: 'cozy',
    badge: 'Relatable Story Chuckle',
    text: 'Arre haha, mummy ne theek tabhi chai maang li jab mic on kiya tha! Phir toh bhaagna hi pada!',
    description: 'Warm, cozy chuckle interwoven naturally inside a daily life story.',
    laughPhonetics: 'Arre haha',
  },
  {
    id: 'laugh_off_clean',
    title: 'Laughter Turned OFF (Clean & Composed)',
    category: 'off',
    badge: 'Pure Warmth / No Laugh',
    text: 'Sahi hai! Main freelance graphic design karti hoon Delhi se. Waise aap kya karte ho — job ya college?',
    description: 'Zero laughter sounds: calm, warm, smiling tone without any chuckles or giggles.',
    laughPhonetics: 'None (Suppressed)',
  },
];

export interface NaturalLaughDemoProps {
  isOpen: boolean;
  onClose: () => void;
  laughEnabled: boolean;
  onToggleLaugh: (enabled: boolean) => void;
  isConnected: boolean;
}

export const NaturalLaughDemo: React.FC<NaturalLaughDemoProps> = ({
  isOpen,
  onClose,
  laughEnabled,
  onToggleLaugh,
  isConnected,
}) => {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [customText, setCustomText] = useState(
    'Haha yaar, ye baat toh bilkul sahi boli tumne!'
  );
  const [customLaughPrefix, setCustomLaughPrefix] = useState<'haha' | 'hehe' | 'none'>('haha');
  const [isCustomPlaying, setIsCustomPlaying] = useState(false);

  const synthRef = useRef<SpeechSynthesis | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  const stopAllAudio = () => {
    if (synthRef.current) {
      synthRef.current.cancel();
    }
    setPlayingId(null);
    setIsCustomPlaying(false);
  };

  const playVoiceSample = (id: string, textToSpeak: string, isOffSample = false) => {
    if (!synthRef.current) return;
    stopAllAudio();

    setPlayingId(id);

    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = 'hi-IN';
    utterance.rate = 1.02;
    utterance.pitch = isOffSample ? 1.05 : 1.15; // Slightly brighter pitch for playful laughter

    // Pick best available natural female voice
    const voices = synthRef.current.getVoices();
    const naturalVoice = voices.find(
      (v) =>
        /hindi|india|google|natural|neural|female|zira|swara|kalpana/i.test(v.name) ||
        v.lang.startsWith('hi')
    );
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    utterance.onend = () => {
      setPlayingId(null);
    };

    utterance.onerror = () => {
      setPlayingId(null);
    };

    synthRef.current.speak(utterance);
  };

  const handlePlayCustom = () => {
    if (!synthRef.current) return;
    stopAllAudio();
    setIsCustomPlaying(true);

    let prefix = '';
    if (laughEnabled) {
      if (customLaughPrefix === 'haha') prefix = 'Haha yaar! ';
      else if (customLaughPrefix === 'hehe') prefix = 'Hehe, ';
    }
    const fullSpeech = prefix + customText;

    const utterance = new SpeechSynthesisUtterance(fullSpeech);
    utterance.lang = 'hi-IN';
    utterance.rate = 1.02;
    utterance.pitch = laughEnabled ? 1.15 : 1.05;

    const voices = synthRef.current.getVoices();
    const naturalVoice = voices.find(
      (v) =>
        /hindi|india|google|natural|neural|female|zira|swara|kalpana/i.test(v.name) ||
        v.lang.startsWith('hi')
    );
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    utterance.onend = () => {
      setIsCustomPlaying(false);
    };

    utterance.onerror = () => {
      setIsCustomPlaying(false);
    };

    synthRef.current.speak(utterance);
  };

  if (!isOpen) return null;

  return (
    <div className="laugh-modal-overlay" role="dialog" aria-modal="true">
      <div className="laugh-modal-card">
        {/* Modal Header */}
        <div className="laugh-modal-header">
          <div className="laugh-modal-header-left">
            <div className="laugh-modal-icon-badge">
              <Smile size={20} />
            </div>
            <div>
              <h2 className="laugh-modal-title">Simran Natural Laugh Lab</h2>
              <p className="laugh-modal-subtitle">
                Calibrate spontaneous giggles & chuckles, preview sample styles, or turn laughter off
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              stopAllAudio();
              onClose();
            }}
            className="laugh-modal-close-btn"
            title="Close Laugh Lab"
          >
            <X size={18} />
          </button>
        </div>

        {/* Master Laugh Control Banner */}
        <div className="laugh-master-box">
          <div className="laugh-master-info">
            <div className="laugh-master-headline">
              <span className={`laugh-live-dot ${laughEnabled ? 'laugh-live-dot--on' : 'laugh-live-dot--off'}`} />
              <span className="laugh-master-status">
                Current Mode: <strong>{laughEnabled ? 'Natural Laughter Active' : 'Laughter Turned OFF'}</strong>
              </span>
            </div>
            <p className="laugh-master-desc">
              {laughEnabled
                ? 'Simran will sprinkle natural chuckles ("haha yaar") and cute giggles ("hehe") when amused or teasing.'
                : 'Laughter tokens are completely suppressed. Simran will maintain a warm, polite, and calm conversational tone.'}
            </p>
          </div>

          <div className="laugh-master-toggle-group">
            <button
              type="button"
              onClick={() => {
                onToggleLaugh(true);
                stopAllAudio();
              }}
              className={`laugh-toggle-btn ${laughEnabled ? 'laugh-toggle-btn--active-on' : ''}`}
            >
              <Smile size={15} />
              <span>Natural Laugh ON</span>
            </button>
            <button
              type="button"
              onClick={() => {
                onToggleLaugh(false);
                stopAllAudio();
              }}
              className={`laugh-toggle-btn ${!laughEnabled ? 'laugh-toggle-btn--active-off' : ''}`}
            >
              <VolumeX size={15} />
              <span>Turned OFF</span>
            </button>
          </div>
        </div>

        {isConnected && (
          <div className="laugh-connected-pill">
            <Zap size={13} className="text-pink-500" />
            <span>Live Call Active: Setting syncs directly to Simran in real time!</span>
          </div>
        )}

        {/* 5 Curated Audio Sample Cards */}
        <div className="laugh-samples-section">
          <h3 className="laugh-section-title">
            <span>Curated Laughter & Tone Previews</span>
            <span className="laugh-section-badge">5 Styles</span>
          </h3>

          <div className="laugh-samples-grid">
            {LAUGH_SAMPLES.map((sample) => {
              const isPlaying = playingId === sample.id;
              const isOff = sample.category === 'off';

              return (
                <div
                  key={sample.id}
                  className={`laugh-sample-card ${isPlaying ? 'laugh-sample-card--playing' : ''} ${
                    isOff ? 'laugh-sample-card--off' : ''
                  }`}
                >
                  <div className="laugh-sample-top">
                    <span className="laugh-sample-badge">{sample.badge}</span>
                    <span className="laugh-sample-phonetic">Token: {sample.laughPhonetics}</span>
                  </div>

                  <h4 className="laugh-sample-name">{sample.title}</h4>
                  <p className="laugh-sample-quote">"{sample.text}"</p>
                  <p className="laugh-sample-desc">{sample.description}</p>

                  <div className="laugh-sample-action">
                    <button
                      type="button"
                      onClick={() => {
                        if (isPlaying) {
                          stopAllAudio();
                        } else {
                          playVoiceSample(sample.id, sample.text, isOff);
                        }
                      }}
                      className={`laugh-play-btn ${isPlaying ? 'laugh-play-btn--active' : ''}`}
                    >
                      {isPlaying ? (
                        <>
                          <Square size={13} />
                          <span>Stop Playing</span>
                        </>
                      ) : (
                        <>
                          <Play size={13} />
                          <span>Play Voice Sample</span>
                        </>
                      )}
                    </button>

                    {isPlaying && (
                      <div className="laugh-waveform-anim" aria-label="Speaking waveform">
                        <span className="wave-bar" />
                        <span className="wave-bar" />
                        <span className="wave-bar" />
                        <span className="wave-bar" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Custom Phrase Testing Playground */}
        <div className="laugh-custom-playground">
          <h3 className="laugh-section-title">
            <span>Test Your Own Phrase with Simran's Laugh</span>
          </h3>

          <div className="laugh-custom-controls">
            <div className="laugh-prefix-select">
              <span className="laugh-label">Prefix:</span>
              <button
                type="button"
                disabled={!laughEnabled}
                onClick={() => setCustomLaughPrefix('haha')}
                className={`laugh-prefix-pill ${customLaughPrefix === 'haha' && laughEnabled ? 'laugh-prefix-pill--active' : ''}`}
              >
                Haha yaar!
              </button>
              <button
                type="button"
                disabled={!laughEnabled}
                onClick={() => setCustomLaughPrefix('hehe')}
                className={`laugh-prefix-pill ${customLaughPrefix === 'hehe' && laughEnabled ? 'laugh-prefix-pill--active' : ''}`}
              >
                Hehe
              </button>
              <button
                type="button"
                onClick={() => setCustomLaughPrefix('none')}
                className={`laugh-prefix-pill ${customLaughPrefix === 'none' || !laughEnabled ? 'laugh-prefix-pill--active' : ''}`}
              >
                None (Pure)
              </button>
            </div>

            <div className="laugh-input-row">
              <input
                type="text"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                placeholder="Type any Hindi/English phrase here..."
                className="laugh-custom-input"
              />
              <button
                type="button"
                onClick={isCustomPlaying ? stopAllAudio : handlePlayCustom}
                className="laugh-test-btn"
              >
                {isCustomPlaying ? (
                  <>
                    <Square size={14} />
                    <span>Stop</span>
                  </>
                ) : (
                  <>
                    <Volume2 size={14} />
                    <span>Speak Line</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="laugh-modal-footer">
          <button
            type="button"
            onClick={() => {
              stopAllAudio();
              onClose();
            }}
            className="laugh-done-btn"
          >
            <Check size={14} />
            <span>Done & Keep {laughEnabled ? 'Natural Laugh ON' : 'Laugh OFF'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
