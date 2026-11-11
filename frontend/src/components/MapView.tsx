import L from "leaflet";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";

export type MapMarker = {
  id: string; lat: number; lng: number; label?: string; kind?: "default" | "done" | "next" | "alt";
  title?: string; onClick?: () => void;
};
type Props = {
  markers?: MapMarker[];
  line?: [number, number][];
  me?: { lat: number; lng: number } | null;
  /** Points to keep in view (for example you and the next stop). Re-framed whenever they move. */
  frame?: [number, number][];
  fit?: boolean;
  /** Pixels covered by overlays, so pins are not hidden under a side panel or bottom sheet. */
  padLeft?: number;
  padBottom?: number;
  scroll?: boolean;
  className?: string;
  center?: [number, number];
  zoom?: number;
};

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>';

const pinIcon = (m: MapMarker) =>
  L.divIcon({
    className: "",
    html: `<div class="pin ${m.kind && m.kind !== "default" ? m.kind : ""}"><span>${m.label ?? ""}</span></div>`,
    iconSize: [32, 32],
    iconAnchor: [6, 32],
  });

export default function MapView({ markers = [], line, me, frame, fit = true, padLeft = 0, padBottom = 0, scroll = false, className, center, zoom }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const meMarker = useRef<L.Marker | null>(null);
  const fitted = useRef("");
  const framed = useRef("");
  const pad = useRef({ padLeft, padBottom });
  pad.current = { padLeft, padBottom };
  const fitTo = (m: L.Map, pts: [number, number][], maxZoom: number, animate: boolean) => {
    if (pts.length === 1) return m.setView(pts[0], maxZoom - 1, { animate });
    m.fitBounds(L.latLngBounds(pts), {
      paddingTopLeft: [48 + pad.current.padLeft, 72], paddingBottomRight: [48, 48 + pad.current.padBottom], maxZoom, animate,
    });
  };

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { scrollWheelZoom: scroll, zoomControl: false, attributionControl: true })
      .setView(center ?? [30.4, 69.4], zoom ?? 5);
    L.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 18, crossOrigin: true }).addTo(m);
    L.control.zoom({ position: "bottomright" }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    fitted.current = ""; // a fresh map always needs its first fit (matters when effects re-run in development)
    framed.current = "";
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      meMarker.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    if (line && line.length > 1) {
      L.polyline(line, { color: "#12282d", weight: 4, opacity: 0.85, dashArray: "1 9", lineCap: "round" }).addTo(g);
    }
    for (const mk of markers) {
      const marker = L.marker([mk.lat, mk.lng], { icon: pinIcon(mk), title: mk.title, keyboard: !!mk.onClick }).addTo(g);
      if (mk.onClick) marker.on("click", mk.onClick);
    }
    const key = markers.map((x) => x.id).join("|") + (line?.length ?? 0);
    if (fit && key !== fitted.current && markers.length) {
      fitted.current = key;
      m.invalidateSize();
      fitTo(m, markers.map((x) => [x.lat, x.lng] as [number, number]), 15, false);
    }
  }, [markers, line, fit]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = map.current;
    if (!m || !frame?.length) return;
    const sig = frame.map((p) => p[0].toFixed(4) + p[1].toFixed(4)).join("|");
    if (sig === framed.current) return;
    const first = framed.current === "";
    framed.current = sig;
    m.invalidateSize();
    fitTo(m, frame, 16, !first);
  }, [frame, padLeft, padBottom]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!me) {
      meMarker.current?.remove();
      meMarker.current = null;
      return;
    }
    const ll: L.LatLngExpression = [me.lat, me.lng];
    if (!meMarker.current) {
      meMarker.current = L.marker(ll, { icon: L.divIcon({ className: "", html: '<div class="me-dot"></div>', iconSize: [18, 18] }), zIndexOffset: 1000, interactive: false }).addTo(m);
    } else meMarker.current.setLatLng(ll);
  }, [me]);

  return <div ref={el} className={cn("z-0 h-full min-h-[200px] w-full", className)} role="application" aria-label="Map" />;
}
