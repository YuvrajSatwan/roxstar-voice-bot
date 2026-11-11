/**
 * Token Service for STS Lab.
 * Communicates with the dedicated STS token server on http://127.0.0.1:8001.
 */

const STS_TOKEN_URL =
  import.meta.env.VITE_STS_TOKEN_URL ||
  import.meta.env.VITE_TOKEN_URL ||
  (typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') &&
  window.location.port !== '8001'
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

export async function requestStsSession(name: string, room?: string): Promise<StsSession> {
  const res = await fetch(`${STS_TOKEN_URL}/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name.trim() || 'Guest', room: room || '' }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `Failed to connect to STS server (HTTP ${res.status})`);
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
    const res = await fetch(`${STS_TOKEN_URL}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
