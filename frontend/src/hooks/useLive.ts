import { useCallback, useEffect, useRef, useState } from "react";
import { api, tokens, wsUrl } from "@/api/client";
import type { LiveState } from "@/api/types";
import { haversineKm } from "@/lib/geo";

export type Pos = { lat: number; lng: number; accuracy?: number };
export type Link = "off" | "connecting" | "live" | "fallback";
export type Source = "gps" | "demo";

const SEND_EVERY_MS = 6200; // the server ignores pings closer than 5 s
const HEARTBEAT_MS = 25_000;

/**
 * Keeps the live companion running: reads a position (real GPS, or a simulated walk for testing indoors),
 * sends it over a WebSocket and falls back to plain HTTP when WebSockets are blocked.
 */
export function useLive(opts: { enabled: boolean; source: Source; target: { lat: number; lng: number } | null; onState?: (s: LiveState) => void }) {
  const { enabled, source, target } = opts;
  const [pos, setPos] = useState<Pos | null>(null);
  const [state, setState] = useState<LiveState | null>(null);
  const [link, setLink] = useState<Link>("off");
  const [error, setError] = useState<string | null>(null);

  const ws = useRef<WebSocket | null>(null);
  const ready = useRef(false);
  const latest = useRef<Pos | null>(null);
  const lastSent = useRef(0);
  const failures = useRef(0);
  const onState = useRef(opts.onState);
  onState.current = opts.onState;
  const targetRef = useRef(target);
  targetRef.current = target;
  const stateRef = useRef<LiveState | null>(null);

  const handleState = useCallback((s: LiveState) => {
    if (s.throttled) return;
    stateRef.current = s;
    setState(s);
    setError(null);
    onState.current?.(s);
  }, []);

  const post = useCallback(async (p: Pos) => {
    try {
      handleState(await api<LiveState>("/companion/location", { method: "POST", body: { lat: p.lat, lng: p.lng, accuracy_m: p.accuracy ?? null } }));
      setLink((l) => (l === "live" ? l : "fallback"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [handleState]);

  const send = useCallback((p: Pos, force = false) => {
    const now = Date.now();
    if (!force && now - lastSent.current < SEND_EVERY_MS) return;
    lastSent.current = now;
    if (ws.current && ready.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "location", lat: p.lat, lng: p.lng, accuracy_m: p.accuracy ?? null }));
    } else void post(p);
  }, [post]);

  // ---- connection
  useEffect(() => {
    if (!enabled) return;
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;
    let beat: ReturnType<typeof setInterval>;

    const connect = () => {
      if (closed) return;
      setLink((l) => (l === "fallback" ? l : "connecting"));
      let sock: WebSocket;
      try {
        sock = new WebSocket(wsUrl("/ws/companion"));
      } catch {
        failures.current++;
        setLink("fallback");
        return;
      }
      ws.current = sock;
      ready.current = false;
      sock.onopen = () => sock.send(JSON.stringify({ type: "auth", token: tokens.access }));
      sock.onmessage = async (ev) => {
        let m: { type?: string; code?: string; message?: string };
        try { m = JSON.parse(ev.data); } catch { return; }
        if (m.type === "ready") {
          ready.current = true;
          failures.current = 0;
          setLink("live");
          if (latest.current) send(latest.current, true);
        } else if (m.type === "state") handleState(m as unknown as LiveState);
        else if (m.type === "error") {
          if (m.code === "invalid_token") await api("/auth/me").catch(() => {}); // refreshes the token, then we reconnect
          else if (m.code === "no_active_trip") setError("No trip is in progress. Start one from your trip page.");
          else if (m.code !== "bad_location") setError(m.message ?? "Live tracking hit a problem.");
        }
      };
      sock.onclose = () => {
        ready.current = false;
        if (closed) return;
        failures.current++;
        if (failures.current >= 2) setLink("fallback");
        else setLink("connecting");
        retry = setTimeout(connect, Math.min(15_000, 1000 * 2 ** failures.current));
      };
      sock.onerror = () => sock.close();
    };
    connect();
    beat = setInterval(() => ws.current?.readyState === WebSocket.OPEN && ws.current.send(JSON.stringify({ type: "ping" })), HEARTBEAT_MS);
    return () => {
      closed = true;
      clearTimeout(retry);
      clearInterval(beat);
      ws.current?.close();
      ws.current = null;
      ready.current = false;
      setLink("off");
    };
  }, [enabled, send, handleState]);

  // ---- real GPS
  useEffect(() => {
    if (!enabled || source !== "gps") return;
    if (!("geolocation" in navigator)) { setError("This browser cannot share a location."); return; }
    const id = navigator.geolocation.watchPosition(
      (g) => {
        const p = { lat: g.coords.latitude, lng: g.coords.longitude, accuracy: g.coords.accuracy };
        latest.current = p;
        setPos(p);
        setError((e) => (e?.startsWith("Location") ? null : e));
        send(p);
      },
      (err) => setError(err.code === 1 ? "Location is blocked. Allow location for this site in your browser settings, or use the demo walk." : "Location is unavailable right now. Check that GPS is on."),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 25_000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [enabled, source, send]);

  // ---- demo walk: starts about 1.5 km from the next stop and closes in a little at every ping
  useEffect(() => {
    if (!enabled || source !== "demo") return;
    const tick = () => {
      const t = stateRef.current?.next_stop ?? targetRef.current; // the server's next stop wins
      if (!t) return;
      const cur = latest.current ?? { lat: t.lat + 0.014, lng: t.lng - 0.008 };
      const d = haversineKm([cur.lat, cur.lng], [t.lat, t.lng]);
      const f = d < 0.06 ? 1 : Math.max(0.55, 0.08 / Math.max(d, 0.01));
      const p = { lat: cur.lat + (t.lat - cur.lat) * f, lng: cur.lng + (t.lng - cur.lng) * f, accuracy: 12 };
      latest.current = p;
      setPos(p);
      send(p, true);
    };
    tick();
    const id = setInterval(tick, SEND_EVERY_MS);
    return () => { clearInterval(id); latest.current = null; };
  }, [enabled, source, send]);

  const reset = useCallback(() => { setPos(null); setState(null); stateRef.current = null; latest.current = null; setError(null); }, []);
  return { pos, state, link, error, reset, sendNow: () => latest.current && send(latest.current, true) };
}
