import { useEffect, useState } from 'react';
import { Flag, X, Zap } from 'lucide-react';
import { adminApi, type MessageRow, type SessionDetail } from './api';

const REASON_LABELS: Record<string, string> = {
  latency_spike: 'Latency spike',
  hallucination: 'Hallucination',
  persona_break: 'Persona break',
  missed_turn: 'Missed turn',
  too_long: 'Simran spoke too long',
  interrupted: 'User interrupted',
  other: 'Other',
};

function latencyClass(ms: number | null): string {
  if (ms === null) return '';
  if (ms > 1500) return 'badge--bad';
  if (ms > 800) return 'badge--warn';
  return 'badge--ok';
}

function Bubble({ m, reasons, onChange }: { m: MessageRow; reasons: string[]; onChange: (m: MessageRow) => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(reasons[0] || 'other');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const fields = Object.entries(m.profile_fields_captured || {});

  const submit = async (flagged: boolean) => {
    setBusy(true);
    try {
      onChange(await adminApi.flag(m.id, reason, flagged, note));
      setOpen(false);
      setNote('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`bubble-row bubble-row--${m.speaker === 'Simran' ? 'bot' : 'user'}`}>
      <div className={`bubble ${m.flagged_issue ? 'bubble--flagged' : ''}`}>
        <div className="bubble__meta">
          <strong>{m.speaker}</strong>
          <span>#{m.turn_index + 1}</span>
          {m.ttft_ms !== null && (
            <span className={`badge ${latencyClass(m.ttft_ms)}`} title="Time to first audio">
              <Zap size={11} /> {Math.round(m.ttft_ms)}ms TTFT
            </span>
          )}
          {m.tokens_per_second !== null && <span className="badge">{m.tokens_per_second} tok/s</span>}
          {m.audio_duration_seconds !== null && <span className="badge">{m.audio_duration_seconds}s</span>}
        </div>
        <p>{m.transcript}</p>
        {fields.length > 0 && (
          <div className="pills">
            {fields.map(([k, v]) => (
              <span className="pill" key={k} title="Captured by save_profile on this turn">
                {k}: {v}
              </span>
            ))}
          </div>
        )}
        {m.flagged_issue && (
          <div className="flag-note">
            <Flag size={12} /> {REASON_LABELS[m.admin_tag || 'other'] || m.admin_tag}
            {m.flag_note ? `: ${m.flag_note}` : ''}
            <button type="button" className="link" disabled={busy} onClick={() => submit(false)}>
              Clear
            </button>
          </div>
        )}
        {!m.flagged_issue && !open && (
          <button type="button" className="link link--flag" onClick={() => setOpen(true)}>
            <Flag size={12} /> Flag
          </button>
        )}
        {open && (
          <div className="flag-form">
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {reasons.map((r) => (
                <option key={r} value={r}>
                  {REASON_LABELS[r] || r}
                </option>
              ))}
            </select>
            <input placeholder="Optional note" value={note} onChange={(e) => setNote(e.target.value)} />
            <button type="button" className="btn btn--small" disabled={busy} onClick={() => submit(true)}>
              Save flag
            </button>
            <button type="button" className="link" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function SessionReplay({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [reasons, setReasons] = useState<string[]>(['other']);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState('');
  const [rating, setRating] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let alive = true;
    setDetail(null);
    adminApi
      .session(sessionId)
      .then((d) => {
        if (!alive) return;
        setDetail(d);
        setNotes(d.session.admin_notes || '');
        setRating(d.session.feedback_rating);
      })
      .catch((e: Error) => alive && setError(e.message));
    adminApi.flagReasons().then((r) => alive && setReasons(r.reasons)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [sessionId]);

  const updateMessage = (m: MessageRow) =>
    setDetail((d) => (d ? { ...d, messages: d.messages.map((x) => (x.id === m.id ? m : x)) } : d));

  const saveReview = async () => {
    await adminApi.review(sessionId, notes, rating);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <aside className="drawer" aria-label="Conversation replay">
      <header className="drawer__head">
        <div>
          <h3>Conversation replay</h3>
          {detail && (
            <p className="muted">
              {detail.user?.name || detail.user?.identity || 'Unknown user'}
              {detail.user?.location ? ` · ${detail.user.location}` : ''} · {detail.session.exit_reason || 'in progress'} ·
              reached Phase {detail.session.final_stage}
            </p>
          )}
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close replay">
          <X size={18} />
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {!detail && !error && <p className="muted">Loading conversation…</p>}
      {detail && (
        <>
          <p className="muted note">
            User lines are Gemini's automatic transcription of the call audio. It can differ from what was actually said
            (especially Hinglish). Simran hears the audio directly, so her replies can be right even when a user line looks wrong.
          </p>
          <div className="timeline">
            {detail.messages.length === 0 && <p className="muted">No turns were recorded for this session.</p>}
            {detail.messages.map((m) => (
              <Bubble key={m.id} m={m} reasons={reasons} onChange={updateMessage} />
            ))}
          </div>
          <footer className="drawer__foot">
            <label>
              Reviewer notes
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} placeholder="What should change in the prompt?" />
            </label>
            <div className="row">
              <label>
                Quality rating
                <select value={rating ?? ''} onChange={(e) => setRating(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Not rated</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n} / 5
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="btn" onClick={saveReview}>
                {saved ? 'Saved' : 'Save review'}
              </button>
            </div>
          </footer>
        </>
      )}
    </aside>
  );
}
