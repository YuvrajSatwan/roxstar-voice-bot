/**
 * Bridge between this web page and the RoxStar mobile app that shows it inside a WebView.
 *
 * In simple words:
 *   - The page runs inside the app. It cannot open duet rooms or close itself.
 *   - So it sends the app short JSON messages ("close me and open duet room 123").
 *   - The app can also send messages to the page ("here is the user's login", "you went to the background").
 *
 * How a message gets out, depending on where the page is running:
 *   Android WebView : window.SimranBridge.postMessage(jsonString)           (addJavascriptInterface)
 *   iOS WKWebView   : window.webkit.messageHandlers.simran.postMessage(obj) (WKScriptMessageHandler)
 *   Normal browser  : just a console line (so developers can test without the app)
 *
 * How a message gets in (the app calls one of these):
 *   window.__simranReceive(jsonStringOrObject)
 *   window.postMessage(jsonStringOrObject, '*')
 *
 * HOW THE LOGIN TOKEN ARRIVES IS NOT DECIDED YET (open item L1). This file supports every option
 * on the table, so choosing later is a small change:
 *   (a) app injects  window.__ROXSTAR_AUTH__ = { accessToken, name }  before the page loads
 *   (b) app sends a message  { type: 'auth', token, name }  after the page loads
 *   (c) developers only: ?dev_token=...  (this branch is removed from production builds)
 * The token is kept in memory only: never in localStorage, never in a URL in production.
 */

export type CloseDestination = 'duet' | 'solo' | 'none';

export interface CloseMessage {
  type: 'simran.close';
  destination: CloseDestination;
  room_id?: string;
  song_title?: string;
  /** Why we are closing without a destination: declined | ended | busy | rate_limited | error | mic_denied | timeout | unauthorized */
  reason?: string;
}

type OutgoingMessage = { type: 'simran.ready' } | CloseMessage;

export interface NativeMessage {
  type: string;
  token?: string;
  name?: string;
}

interface AuthState {
  token: string | null;
  name: string | null;
}

declare global {
  interface Window {
    SimranBridge?: { postMessage: (json: string) => void };
    webkit?: { messageHandlers?: { simran?: { postMessage: (msg: unknown) => void } } };
    __ROXSTAR_AUTH__?: { accessToken?: string; name?: string };
    __simranReceive?: (message: unknown) => void;
  }
}

const auth: AuthState = { token: null, name: null };
const listeners = new Set<(msg: NativeMessage) => void>();
let closeSent = false;

/** Send one message to the app. Never throws: a missing app must not break the page. */
export function sendToNative(message: OutgoingMessage): void {
  try {
    const json = JSON.stringify(message);
    if (window.SimranBridge?.postMessage) {
      window.SimranBridge.postMessage(json);
    } else if (window.webkit?.messageHandlers?.simran) {
      window.webkit.messageHandlers.simran.postMessage(message);
    } else {
      console.info('[simran-bridge] (no app attached)', json);
    }
  } catch (err) {
    console.warn('[simran-bridge] could not reach the app:', err);
  }
}

/** Ask the app to close this page. Only the FIRST call counts, so a double-fire can never open two screens. */
export function closeSimran(message: Omit<CloseMessage, 'type'>): void {
  if (closeSent) return;
  closeSent = true;
  sendToNative({ type: 'simran.close', ...message });
}

/** Tell the app the page has loaded and is ready for the login token. */
export function announceReady(): void {
  sendToNative({ type: 'simran.ready' });
}

/** The user's RoxStar access token, or null if the app has not provided one yet. */
export function getAuthToken(): string | null {
  if (auth.token) return auth.token;
  const injected = window.__ROXSTAR_AUTH__?.accessToken;
  if (typeof injected === 'string' && injected) {
    auth.token = injected;
    auth.name = window.__ROXSTAR_AUTH__?.name ?? auth.name;
    return auth.token;
  }
  try {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token') || params.get('dev_token') || params.get('accessToken');
    const urlName = params.get('name') || params.get('user_name');
    if (urlToken) {
      auth.token = urlToken;
      if (urlName) auth.name = urlName;
      return urlToken;
    }
  } catch {}
  return null;
}

/** Display name from the app, if it sent one. Display only: never used to decide who the user is. */
export function getNativeName(): string {
  if (auth.name) return auth.name;
  if (window.__ROXSTAR_AUTH__?.name) return window.__ROXSTAR_AUTH__.name;
  try {
    const params = new URLSearchParams(window.location.search);
    const urlName = params.get('name') || params.get('user_name');
    if (urlName) {
      auth.name = urlName;
      return urlName;
    }
  } catch {}
  return '';
}

/** Wait (up to timeoutMs) for the app to hand over the login token. Resolves null if it never does. */
export function waitForAuthToken(timeoutMs: number): Promise<string | null> {
  const now = getAuthToken();
  if (now) return Promise.resolve(now);
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      listeners.delete(onMessage);
      resolve(getAuthToken());
    }, timeoutMs);
    const onMessage = (msg: NativeMessage) => {
      if (msg.type === 'auth' && getAuthToken()) {
        window.clearTimeout(timer);
        listeners.delete(onMessage);
        resolve(getAuthToken());
      }
    };
    listeners.add(onMessage);
  });
}

/** Listen for app messages such as app.background / app.foreground. Returns an "unsubscribe" function. */
export function onNativeMessage(handler: (msg: NativeMessage) => void): () => void {
  listeners.add(handler);
  return () => listeners.delete(handler);
}

function receive(raw: unknown): void {
  let msg: unknown = raw;
  if (typeof raw === 'string') {
    try {
      msg = JSON.parse(raw);
    } catch {
      return; // not for us
    }
  }
  if (!msg || typeof msg !== 'object' || typeof (msg as NativeMessage).type !== 'string') return;
  const m = msg as NativeMessage;
  if (m.type === 'auth' && typeof m.token === 'string' && m.token) {
    auth.token = m.token;
    if (typeof m.name === 'string') auth.name = m.name.slice(0, 40);
  }
  listeners.forEach((l) => {
    try {
      l(m);
    } catch (err) {
      console.warn('[simran-bridge] listener error:', err);
    }
  });
}

let wired = false;
/** Hook up the two ways the app can reach the page. Safe to call more than once. */
export function initBridge(): void {
  closeSent = false;
  if (wired) return;
  wired = true;
  window.__simranReceive = receive;
  window.addEventListener('message', (ev) => receive(ev.data));
}

/** Reset bridge state (useful when opening Simran again in dev/simulator). */
export function resetBridgeState(): void {
  auth.token = null;
  auth.name = null;
  closeSent = false;
}

/** For tests only: forget everything. */
export function _resetBridgeForTests(): void {
  auth.token = null;
  auth.name = null;
  listeners.clear();
  closeSent = false;
}
