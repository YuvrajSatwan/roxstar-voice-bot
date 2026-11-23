/**
 * Token Service for STS Lab.
 * Communicates with the dedicated STS token server on http://127.0.0.1:8001.
 */

import { getAuthToken } from '../bridge';

/** The server refused or could not start a session. `status` is the HTTP status (401, 429, 503...). */
export class StsRequestError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'StsRequestError';
    this.status = status;
  }
}

const STS_TOKEN_URL =
  import.meta.env.VITE_STS_TOKEN_URL ||
  import.meta.env.VITE_TOKEN_URL ||
  (typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') &&
  window.location.port === '5175'  // Vite dev server; otherwise the page is served by the backend itself (same origin)
    ? 'http://127.0.0.1:8001'
    : '');

/** Base URL of the backend (token server + admin API). */
export const API_BASE: string = STS_TOKEN_URL;

export interface StsSession {
  url: string;
  token: string;
  room: string;
  persona: string;
  model: string;
  voice: string;
}

/** Anonymous per-browser id, so two visitors who type the same name are stored as different users. */
function getVisitorId(): string {
  try {
    let id = localStorage.getItem('roxstar_visitor_id');
    if (!id) {
      id = Array.from(crypto.getRandomValues(new Uint8Array(6)), (b) => b.toString(16).padStart(2, '0')).join('');
      localStorage.setItem('roxstar_visitor_id', id);
    }
    return id;
  } catch {
    return '';
  }
}

export async function requestStsSession(name: string, room?: string): Promise<StsSession> {
  // Inside the RoxStar app the user's login token is attached. The server then decides the room itself
  // (a room sent from here is ignored). In the standalone lab there is no token and nothing changes.
  const authToken = getAuthToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  // Only a developer tunnel (ngrok) needs this header. Never send it in production.
  if (import.meta.env.DEV) headers['ngrok-skip-browser-warning'] = 'true';
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const res = await fetch(`${STS_TOKEN_URL}/token`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name: name.trim() || 'Guest', room: room || '', visitor_id: getVisitorId() }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    // Codes the server uses in RoxStar mode: unauthorized | busy | rate_limited
    throw new StsRequestError(errorData.error || `Failed to connect to STS server (HTTP ${res.status})`, res.status);
  }

  const data = await res.json();
  return {
    url: data.url,
    token: data.token,
    room: data.room,
    persona: data.persona || 'Simran',
    model: data.model || 'gemini-3.8-live',
    voice: data.voice || 'Leda',
  };
}

export async function checkStsHealth(): Promise<boolean> {
  try {
    const res = await fetch(
      `${STS_TOKEN_URL}/health`,
      import.meta.env.DEV ? { headers: { 'ngrok-skip-browser-warning': 'true' } } : undefined,
    );
    return res.ok;
  } catch {
    return false;
  }
}
