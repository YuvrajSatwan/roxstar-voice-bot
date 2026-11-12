/** Typed client for the /api/admin/* endpoints (auth via X-Admin-Key). */
import { API_BASE } from '../services/tokenService';

const KEY_STORAGE = 'roxstar_admin_key';

export const adminKey = {
  get(): string {
    try {
      return sessionStorage.getItem(KEY_STORAGE) || '';
    } catch {
      return '';
    }
  },
  set(value: string) {
    try {
      sessionStorage.setItem(KEY_STORAGE, value);
    } catch {}
  },
  clear() {
    try {
      sessionStorage.removeItem(KEY_STORAGE);
    } catch {}
  },
};

export class AdminError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export interface Metrics {
  window_days: number;
  unique_users: number;
  profile_completeness_pct: number | null;
  total_conversations: number;
  onboarding_completion_rate: number;
  duet_conversion_rate: number;
  solo_conversion_rate: number;
  two_decline_exit_rate: number;
  abandoned_rate: number;
  avg_duration_seconds: number | null;
  ttft_p50_ms: number | null;
  ttft_p95_ms: number | null;
  ttft_samples: number;
  flagged_turns: number;
  exit_reasons: Record<string, number>;
}

export interface FunnelStage {
  stage: number;
  label: string;
  sessions: number;
  pct_of_total: number;
  drop_off_pct: number;
}

export interface FunnelDay {
  date: string;
  sessions: number;
  reached_pitch: number;
  handoffs: number;
  conversion_pct: number;
  ttft_p50_ms: number | null;
  ttft_p95_ms: number | null;
}

export interface FunnelData {
  window_days: number;
  total: number;
  stages: FunnelStage[];
  daily: FunnelDay[];
}

export interface SessionRow {
  session_id: string;
  room_name: string;
  user_id: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  exit_reason: string | null;
  final_stage: number;
  avg_ttft_ms: number | null;
  total_turns: number;
  model: string | null;
  voice: string | null;
  feedback_rating: number | null;
  admin_notes: string | null;
  user_name?: string | null;
  user_location?: string | null;
  musical_role?: string | null;
  has_flagged_turns?: boolean;
}

export interface Paged<T> {
  page: number;
  page_size: number;
  total: number;
  items: T[];
}

export interface MessageRow {
  id: string;
  session_id: string;
  turn_index: number;
  speaker: 'Simran' | 'User';
  transcript: string;
  timestamp: string | null;
  ttft_ms: number | null;
  tokens_per_second: number | null;
  audio_duration_seconds: number | null;
  profile_fields_captured: Record<string, string>;
  flagged_issue: boolean;
  admin_tag: string | null;
  flag_note: string | null;
}

export interface UserRow {
  user_id: string;
  identity: string;
  name: string | null;
  location: string | null;
  occupation: string | null;
  hobbies: string[];
  music_taste: string[];
  favorite_song: string | null;
  musical_role: string | null;
  singing_comfort: string | null;
  referral_source: string | null;
  expectations: string | null;
  coin_balance: number;
  is_onboarded: boolean;
  created_at: string | null;
  updated_at: string | null;
  session_count: number;
  last_session_at: string | null;
  completeness: number;
  visitor: string | null;
}

export interface UserDetail {
  user: UserRow;
  sessions: SessionRow[];
}

export interface SessionDetail {
  session: SessionRow;
  user: UserRow | null;
  messages: MessageRow[];
}

export interface CountItem {
  name: string;
  count: number;
}

export interface UsersData extends Paged<UserRow> {
  breakdown: { roles: CountItem[]; top_cities: CountItem[]; top_songs: CountItem[] };
}

export type Filters = Record<string, string | number | boolean | undefined>;

function qs(params: Filters): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '' && v !== false) sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey.get(), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new AdminError(res.status, data.error || `Request failed (HTTP ${res.status})`);
  }
  return res;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await request(path, init)).json() as Promise<T>;
}

export const adminApi = {
  authMode: () => json<{ auth_required: boolean }>('/api/admin/auth-mode'),
  metrics: (days: number) => json<Metrics>(`/api/admin/metrics${qs({ days })}`),
  funnel: (days: number) => json<FunnelData>(`/api/admin/funnel${qs({ days })}`),
  sessions: (params: Filters) => json<Paged<SessionRow>>(`/api/admin/sessions${qs(params)}`),
  session: (id: string) => json<SessionDetail>(`/api/admin/sessions/${id}`),
  users: (params: Filters) => json<UsersData>(`/api/admin/users${qs(params)}`),
  user: (id: string) => json<UserDetail>(`/api/admin/users/${id}`),
  deleteSession: (id: string) => json<{ ok: boolean }>(`/api/admin/sessions/${id}/delete`, { method: 'POST', body: '{}' }),
  flagReasons: () => json<{ reasons: string[] }>('/api/admin/flag-reasons'),
  flag: (id: string, reason: string, flagged: boolean, note?: string) =>
    json<MessageRow>(`/api/admin/messages/${id}/flag`, {
      method: 'POST',
      body: JSON.stringify({ reason, flagged, note }),
    }),
  review: (id: string, notes: string, rating: number | null) =>
    json<{ ok: boolean }>(`/api/admin/sessions/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ notes, rating }),
    }),
  async exportData(format: 'csv' | 'json', filters: Filters, flaggedOnly: boolean, kind: 'conversations' | 'users' = 'conversations') {
    const res = await request('/api/admin/export', {
      method: 'POST',
      body: JSON.stringify({ format, kind, flagged_only: flaggedOnly, ...filters }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simran_${kind}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
