import { useCallback, useEffect, useState } from 'react';
import { Download, Moon, RefreshCw, Sun } from 'lucide-react';
import {
  AdminError,
  adminApi,
  adminKey,
  type Filters,
  type FunnelData,
  type Metrics,
  type Paged,
  type SessionRow,
  type UsersData,
} from './api';
import { SessionReplay } from './SessionReplay';
import { UserDrawer } from './UserDrawer';
import './admin.css';

const EXIT_LABELS: Record<string, string> = {
  duet_handoff: 'Duet handoff',
  solo_handoff: 'Solo handoff',
  two_decline_exit: '2-decline exit',
  user_disconnected: 'User disconnected',
  abandoned: 'Abandoned',
};

const fmtDuration = (s: number | null) => (s === null ? '–' : s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${Math.round(s)}s`);
const fmtMs = (v: number | null) => (v === null ? '–' : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`);
const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '–');

function KeyGate({ onSubmit, error }: { onSubmit: (key: string) => void; error: string }) {
  const [value, setValue] = useState('');
  return (
    <form
      className="gate"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSubmit(value.trim());
      }}
    >
      <h2>Simran admin</h2>
      <p className="muted">Enter the admin key (ADMIN_API_KEY). It is kept for this browser tab only.</p>
      <input type="password" autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder="Admin key" />
      {error && <p className="error">{error}</p>}
      <button className="btn" type="submit">
        Open dashboard
      </button>
    </form>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="kpi">
      <span className="kpi__label">{label}</span>
      <strong className="kpi__value">{value}</strong>
      {hint && <span className="kpi__hint">{hint}</span>}
    </div>
  );
}

function Overview({ days, refreshKey }: { days: number; refreshKey: number }) {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setError('');
    Promise.all([adminApi.metrics(days), adminApi.funnel(days)])
      .then(([m, f]) => {
        if (alive) {
          setMetrics(m);
          setFunnel(f);
        }
      })
      .catch((e: Error) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [days, refreshKey]);

  if (error) return <p className="error">{error}</p>;
  if (!metrics || !funnel) return <p className="muted">Loading metrics…</p>;

  return (
    <>
      <section className="kpis">
        <Kpi label="Total calls" value={String(metrics.total_conversations)} hint={`last ${days} ${days === 1 ? 'day' : 'days'}`} />
        <Kpi label="Unique users" value={String(metrics.unique_users)} hint="who talked to Simran" />
        <Kpi label="Reached duet pitch" value={`${metrics.onboarding_completion_rate}%`} hint="onboarding completion" />
        <Kpi label="Duet conversion" value={`${metrics.duet_conversion_rate}%`} hint={`solo ${metrics.solo_conversion_rate}%`} />
        <Kpi label="2-decline exits" value={`${metrics.two_decline_exit_rate}%`} hint={`abandoned ${metrics.abandoned_rate}%`} />
        <Kpi label="Avg call length" value={fmtDuration(metrics.avg_duration_seconds)} />
        <Kpi
          label="Response time p50 / p95"
          value={`${fmtMs(metrics.ttft_p50_ms)} / ${fmtMs(metrics.ttft_p95_ms)}`}
          hint={metrics.ttft_samples ? `${metrics.ttft_samples} turns, user stops to Simran starts` : 'no latency samples yet'}
        />
        <Kpi
          label="Profile completeness"
          value={metrics.profile_completeness_pct === null ? '–' : `${metrics.profile_completeness_pct}%`}
          hint="avg fields filled per user"
        />
      </section>

      <section className="card">
        <h3>Friction and drop-off funnel</h3>
        {funnel.total === 0 ? (
          <p className="muted">No conversations in this window yet.</p>
        ) : (
          <div className="funnel">
            {funnel.stages.map((s) => (
              <div className="funnel__row" key={s.stage}>
                <span className="funnel__label">{s.label}</span>
                <div className="funnel__bar">
                  <div className="funnel__fill" style={{ width: `${Math.max(s.pct_of_total, 1.5)}%` }} />
                </div>
                <span className="funnel__num">
                  {s.sessions} <em>({s.pct_of_total}%)</em>
                </span>
                <span className={`funnel__drop ${s.drop_off_pct >= 30 ? 'funnel__drop--high' : ''}`}>
                  {s.stage > 1 ? `-${s.drop_off_pct}%` : ''}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3>Exit reasons</h3>
        <div className="chips">
          {Object.entries(metrics.exit_reasons).map(([k, v]) => (
            <span className="chip" key={k}>
              {EXIT_LABELS[k] || k}: <strong>{v}</strong>
            </span>
          ))}
          <span className="chip chip--flag">
            Flagged turns: <strong>{metrics.flagged_turns}</strong>
          </span>
        </div>
      </section>

      <section className="card">
        <h3>Daily trend</h3>
        {funnel.daily.length === 0 ? (
          <p className="muted">No data yet.</p>
        ) : (
          <div className="scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Calls</th>
                  <th>Reached pitch</th>
                  <th>Handoffs</th>
                  <th>Conversion</th>
                  <th>Response p50</th>
                  <th>Response p95</th>
                </tr>
              </thead>
              <tbody>
                {funnel.daily.map((d) => (
                  <tr key={d.date}>
                    <td>{d.date}</td>
                    <td>{d.sessions}</td>
                    <td>{d.reached_pitch}</td>
                    <td>{d.handoffs}</td>
                    <td>{d.conversion_pct}%</td>
                    <td>{fmtMs(d.ttft_p50_ms)}</td>
                    <td>{fmtMs(d.ttft_p95_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pager">
      <button type="button" className="btn btn--small" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {pages} · {total} total
      </span>
      <button type="button" className="btn btn--small" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}

function Sessions({ onOpen, refreshKey }: { onOpen: (id: string) => void; refreshKey: number }) {
  const [filters, setFilters] = useState<Filters>({ exit_reason: '', role: '', q: '', date_from: '', date_to: '', flagged: false });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paged<SessionRow> | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setError('');
    adminApi.sessions({ ...filters, page, page_size: 20 }).then(setData).catch((e: Error) => setError(e.message));
  }, [filters, page, refreshKey]);

  useEffect(load, [load]);

  const set = (k: string, v: string | boolean) => {
    setPage(1);
    setFilters((f) => ({ ...f, [k]: v }));
  };

  return (
    <section className="card">
      <div className="filters">
        <input placeholder="Search name or room" value={String(filters.q)} onChange={(e) => set('q', e.target.value)} />
        <select value={String(filters.exit_reason)} onChange={(e) => set('exit_reason', e.target.value)}>
          <option value="">All exit reasons</option>
          {Object.entries(EXIT_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <input placeholder="Listener or singer" value={String(filters.role)} onChange={(e) => set('role', e.target.value)} />
        <input type="date" value={String(filters.date_from)} onChange={(e) => set('date_from', e.target.value)} aria-label="From date" />
        <input type="date" value={String(filters.date_to)} onChange={(e) => set('date_to', e.target.value)} aria-label="To date" />
        <label className="check">
          <input type="checkbox" checked={Boolean(filters.flagged)} onChange={(e) => set('flagged', e.target.checked)} /> Flagged only
        </label>
        <button type="button" className="btn btn--small" onClick={() => adminApi.exportData('csv', filters, false)}>
          <Download size={13} /> CSV
        </button>
        <button type="button" className="btn btn--small" onClick={() => adminApi.exportData('json', filters, false)}>
          <Download size={13} /> JSON
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">Loading sessions…</p>}
      {data && (
        <>
          <div className="scroll">
            <table className="table table--click">
              <thead>
                <tr>
                  <th>Started</th>
                  <th>User</th>
                  <th>Role</th>
                  <th>Exit</th>
                  <th>Phase</th>
                  <th>Turns</th>
                  <th>Length</th>
                  <th>Avg response</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={9} className="muted">
                      No sessions match these filters.
                    </td>
                  </tr>
                )}
                {data.items.map((s) => (
                  <tr key={s.session_id} onClick={() => onOpen(s.session_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpen(s.session_id)}>
                    <td>{fmtDate(s.started_at)}</td>
                    <td>
                      {s.user_name || '–'}
                      {s.user_location ? <span className="muted"> · {s.user_location}</span> : null}
                    </td>
                    <td>{s.musical_role || '–'}</td>
                    <td>
                      <span className={`tag tag--${s.exit_reason || 'live'}`}>{s.exit_reason ? EXIT_LABELS[s.exit_reason] || s.exit_reason : 'In progress'}</span>
                    </td>
                    <td>{s.final_stage} / 4</td>
                    <td>{s.total_turns}</td>
                    <td>{fmtDuration(s.duration_seconds)}</td>
                    <td>{fmtMs(s.avg_ttft_ms)}</td>
                    <td>{s.has_flagged_turns ? '🚩' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </section>
  );
}

function Users({ onOpenUser, refreshKey }: { onOpenUser: (id: string) => void; refreshKey: number }) {
  const [filters, setFilters] = useState({ city: '', role: '', song: '', q: '' });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<UsersData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    adminApi.users({ ...filters, page, page_size: 20 }).then(setData).catch((e: Error) => setError(e.message));
  }, [filters, page, refreshKey]);

  const set = (k: string, v: string) => {
    setPage(1);
    setFilters((f) => ({ ...f, [k]: v }));
  };

  const breakdown = data?.breakdown;
  return (
    <>
      {breakdown && (
        <section className="grid3">
          {(
            [
              ['Musical role', breakdown.roles, 'role'],
              ['Top cities', breakdown.top_cities, 'city'],
              ['Top songs', breakdown.top_songs, 'song'],
            ] as const
          ).map(([title, items, key]) => (
            <div className="card" key={title}>
              <h3>{title}</h3>
              {items.length === 0 && <p className="muted">No data yet.</p>}
              {items.map((i) => (
                <button type="button" className="count-row" key={i.name} onClick={() => set(key, i.name)}>
                  <span>{i.name}</span>
                  <strong>{i.count}</strong>
                </button>
              ))}
            </div>
          ))}
        </section>
      )}
      <section className="card">
        <div className="filters">
          <input placeholder="Search name" value={filters.q} onChange={(e) => set('q', e.target.value)} />
          <input placeholder="City" value={filters.city} onChange={(e) => set('city', e.target.value)} />
          <input placeholder="Role (listener, singer…)" value={filters.role} onChange={(e) => set('role', e.target.value)} />
          <input placeholder="Favourite song" value={filters.song} onChange={(e) => set('song', e.target.value)} />
          <button type="button" className="btn btn--small" onClick={() => setFilters({ city: '', role: '', song: '', q: '' })}>
            Clear filters
          </button>
          <button type="button" className="btn btn--small" onClick={() => adminApi.exportData('csv', {}, false, 'users')}>
            <Download size={13} /> Users CSV
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        {!data && !error && <p className="muted">Loading users…</p>}
        {data && (
          <>
            <div className="scroll">
              <table className="table table--click">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>City</th>
                    <th>Work</th>
                    <th>Role</th>
                    <th>Taste</th>
                    <th>Loop song</th>
                    <th>Found via</th>
                    <th>Calls</th>
                    <th>Last call</th>
                    <th>Profile</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.length === 0 && (
                    <tr>
                      <td colSpan={10} className="muted">
                        No users match these filters.
                      </td>
                    </tr>
                  )}
                  {data.items.map((u) => (
                    <tr key={u.user_id} onClick={() => onOpenUser(u.user_id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onOpenUser(u.user_id)}>
                      <td>
                        {u.name || u.identity}
                        {u.visitor ? <span className="muted"> · {u.visitor.slice(0, 6)}</span> : null}
                      </td>
                      <td>{u.location || '–'}</td>
                      <td>{u.occupation || '–'}</td>
                      <td>{u.musical_role || '–'}</td>
                      <td>{u.music_taste.join(', ') || '–'}</td>
                      <td>{u.favorite_song || '–'}</td>
                      <td>{u.referral_source || '–'}</td>
                      <td>{u.session_count}</td>
                      <td>{fmtDate(u.last_session_at)}</td>
                      <td>
                        <span className="meter" title={`${u.completeness}% of fields filled`}>
                          <span style={{ width: `${u.completeness}%` }} />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}

export function AdminApp() {
  const [authed, setAuthed] = useState(Boolean(adminKey.get()));
  const [gateError, setGateError] = useState('');
  const [tab, setTab] = useState<'overview' | 'sessions' | 'users'>('overview');
  const [days, setDays] = useState(30);
  const [openId, setOpenId] = useState<string | null>(null);
  const [openUserId, setOpenUserId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dark, setDark] = useState<boolean>(() => {
    try {
      return localStorage.getItem('roxstar_admin_theme') === 'dark';
    } catch {
      return false;
    }
  });

  // Development mode: when the server has no ADMIN_API_KEY it is open to this machine, so skip the key screen.
  useEffect(() => {
    adminApi
      .authMode()
      .then((m) => {
        if (!m.auth_required) setAuthed(true);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem('roxstar_admin_theme', dark ? 'dark' : 'light');
    } catch {}
  }, [dark]);

  const unlock = async (key: string) => {
    adminKey.set(key);
    try {
      await adminApi.metrics(1);
      setGateError('');
      setAuthed(true);
    } catch (e) {
      adminKey.clear();
      setGateError(e instanceof AdminError && e.status === 401 ? 'That key is not valid.' : (e as Error).message);
    }
  };

  return (
    <div className="admin-shell" data-theme={dark ? 'dark' : 'light'}>
      <header className="admin-top">
        <div className="admin-brand">
          <span className="dot" /> Roxstar <span className="muted">· Simran review</span>
        </div>
        {authed && (
          <nav className="tabs" aria-label="Sections">
            {(['overview', 'sessions', 'users'] as const).map((t) => (
              <button key={t} type="button" className={`tab ${tab === t ? 'tab--on' : ''}`} onClick={() => setTab(t)}>
                {t === 'overview' ? 'Overview' : t === 'sessions' ? 'Conversations' : 'Users'}
              </button>
            ))}
          </nav>
        )}
        <div className="admin-actions">
          {authed && tab === 'overview' && (
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Time window">
              {[1, 7, 30, 90].map((d) => (
                <option key={d} value={d}>
                  Last {d} {d === 1 ? 'day' : 'days'}
                </option>
              ))}
            </select>
          )}
          {authed && (
            <button type="button" className="btn btn--small" onClick={() => setRefreshKey((k) => k + 1)}>
              <RefreshCw size={13} /> Refresh
            </button>
          )}
          <button type="button" className="icon-btn" onClick={() => setDark((d) => !d)} aria-label="Toggle theme">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          {authed && adminKey.get() && (
            <button
              type="button"
              className="btn btn--small"
              onClick={() => {
                adminKey.clear();
                setAuthed(false);
              }}
            >
              Lock
            </button>
          )}
        </div>
      </header>
      <main className="admin-main">
        {!authed && <KeyGate onSubmit={unlock} error={gateError} />}
        {authed && tab === 'overview' && <Overview days={days} refreshKey={refreshKey} />}
        {authed && tab === 'sessions' && <Sessions onOpen={setOpenId} refreshKey={refreshKey} />}
        {authed && tab === 'users' && <Users onOpenUser={setOpenUserId} refreshKey={refreshKey} />}
      </main>
      {authed && openUserId && <UserDrawer userId={openUserId} onClose={() => setOpenUserId(null)} onOpenSession={setOpenId} />}
      {authed && openId && (
        <SessionReplay
          sessionId={openId}
          onClose={() => setOpenId(null)}
          onDeleted={() => {
            setOpenId(null);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </div>
  );
}
