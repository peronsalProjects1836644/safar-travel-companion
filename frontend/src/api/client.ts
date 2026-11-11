// Small fetch wrapper: JSON in and out, bearer token, one automatic refresh on an expired token,
// and errors that always carry the backend's {code, message}.

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const API = `${BASE}/api/v1`;

const ACCESS = "safar.access";
const REFRESH = "safar.refresh";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode): the session just will not survive a reload */
  }
}

let memoryAccess: string | null = null;
export const tokens = {
  get access() {
    return memoryAccess ?? read(ACCESS);
  },
  get refresh() {
    return read(REFRESH);
  },
  set(access: string, refresh: string) {
    memoryAccess = access;
    write(ACCESS, access);
    write(REFRESH, refresh);
  },
  clear() {
    memoryAccess = null;
    write(ACCESS, null);
    write(REFRESH, null);
  },
};

const listeners = new Set<() => void>();
export const onSessionEnd = (fn: () => void) => {
  listeners.add(fn);
  return () => void listeners.delete(fn);
};

let refreshing: Promise<boolean> | null = null;
async function refreshTokens(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${API}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!r.ok) return false;
      const t = await r.json();
      tokens.set(t.access_token, t.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

type Options = { method?: string; body?: unknown; auth?: boolean; signal?: AbortSignal };

async function parseError(r: Response): Promise<ApiError> {
  try {
    const j = await r.json();
    if (j?.error) return new ApiError(r.status, j.error.code, j.error.message);
    if (Array.isArray(j?.detail)) return new ApiError(r.status, "validation_error", j.detail[0]?.msg ?? "Invalid input.");
  } catch {
    /* not JSON */
  }
  return new ApiError(r.status, "http_error", "Something went wrong. Please try again.");
}

export async function api<T>(path: string, opts: Options = {}, retried = false): Promise<T> {
  const { method = "GET", body, auth = true, signal } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let r: Response;
  try {
    r = await fetch(`${API}${path}`, { method, headers, signal, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network", "Cannot reach the server. Check your connection and try again.");
  }
  if (r.status === 401 && auth && !retried && tokens.refresh) {
    if (await refreshTokens()) return api<T>(path, opts, true);
    tokens.clear();
    listeners.forEach((fn) => fn());
  }
  if (!r.ok) throw await parseError(r);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

/** Streams the assistant's answer. Calls onDelta for each piece of text. */
export async function streamChat(
  body: { messages: { role: "user" | "assistant"; content: string }[]; trip_id?: string | null },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const send = () =>
    fetch(`${API}/ai/chat`, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokens.access ?? ""}` },
      body: JSON.stringify(body),
    });
  let r = await send().catch(() => {
    throw new ApiError(0, "network", "Cannot reach the server. Check your connection and try again.");
  });
  if (r.status === 401 && (await refreshTokens())) r = await send();
  if (!r.ok || !r.body) throw await parseError(r);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data || data === "[DONE]") continue;
      const parsed = JSON.parse(data);
      if (event === "error") throw new ApiError(502, "stream_error", parsed.message ?? "The assistant stopped unexpectedly.");
      if (parsed.delta) onDelta(parsed.delta);
    }
  }
}

export function wsUrl(path: string): string {
  const base = BASE || window.location.origin;
  return base.replace(/^http/, "ws") + `/api/v1${path}`;
}
