import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { adminApi, type UserDetail } from './api';

const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '–');
const fmtDuration = (s: number | null) => (s === null ? '–' : s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.round(s)}s`);

const EXIT_LABELS: Record<string, string> = {
  duet_handoff: 'Duet handoff',
  solo_handoff: 'Solo handoff',
  two_decline_exit: '2-decline exit',
  user_disconnected: 'User disconnected',
  abandoned: 'Abandoned',
};

export function ProfileGrid({ user }: { user: UserDetail['user'] }) {
  const rows: [string, string][] = [
    ['Name', user.name || '–'],
    ['City', user.location || '–'],
    ['Work', user.occupation || '–'],
    ['Free time', user.hobbies.join(', ') || '–'],
    ['Found Roxstar via', user.referral_source || '–'],
    ['Listener or singer', user.musical_role || '–'],
    ['Singing comfort', user.singing_comfort || '–'],
    ['Music taste', user.music_taste.join(', ') || '–'],
    ['Loop song', user.favorite_song || '–'],
    ['Here for', user.expectations || '–'],
    ['Welcome coins', String(user.coin_balance)],
    ['Onboarded', user.is_onboarded ? 'Yes' : 'Not yet'],
  ];
  return (
    <div className="profile">
      <div className="profile__bar" title={`${user.completeness}% of profile fields filled`}>
        <div className="profile__fill" style={{ width: `${user.completeness}%` }} />
        <span>{user.completeness}% profile complete</span>
      </div>
      <dl className="profile__grid">
        {rows.map(([k, v]) => (
          <div key={k} className={v === '–' ? 'profile__item profile__item--empty' : 'profile__item'}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function UserDrawer({ userId, onClose, onOpenSession }: { userId: string; onClose: () => void; onOpenSession: (id: string) => void }) {
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setDetail(null);
    adminApi
      .user(userId)
      .then((d) => alive && setDetail(d))
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [userId]);

  return (
    <aside className="drawer" aria-label="User profile">
      <header className="drawer__head">
        <div>
          <h3>{detail ? detail.user.name || detail.user.identity : 'User'}</h3>
          {detail && (
            <p className="muted">
              {detail.user.session_count} {detail.user.session_count === 1 ? 'conversation' : 'conversations'} · first seen {fmtDate(detail.user.created_at)}
              {detail.user.visitor ? ` · visitor ${detail.user.visitor}` : ''}
            </p>
          )}
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close user">
          <X size={18} />
        </button>
      </header>
      {error && <p className="error pad">{error}</p>}
      {!detail && !error && <p className="muted pad">Loading user…</p>}
      {detail && (
        <div className="timeline">
          <ProfileGrid user={detail.user} />
          <h4 className="subhead">Conversations</h4>
          {detail.sessions.length === 0 && <p className="muted">No conversations yet.</p>}
          {detail.sessions.map((s) => (
            <button type="button" key={s.session_id} className="session-card" onClick={() => onOpenSession(s.session_id)}>
              <span>
                <strong>{fmtDate(s.started_at)}</strong>
                <span className="muted"> · {fmtDuration(s.duration_seconds)} · {s.total_turns} turns · Phase {s.final_stage}</span>
              </span>
              <span className={`tag tag--${s.exit_reason || 'live'}`}>{s.exit_reason ? EXIT_LABELS[s.exit_reason] || s.exit_reason : 'In progress'}</span>
              {s.has_flagged_turns && <span title="Has flagged turns">🚩</span>}
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
