import { useQueryClient } from "@tanstack/react-query";
import { Bot, Check, ChevronDown, ChevronUp, CircleAlert, CloudRain, Crosshair, FlaskConical, Navigation, PartyPopper, Plus, Radio, Share2, ShieldAlert, Sparkles, WifiOff } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { createShare, revokeShare, useAddStopTo, useStartTrip, useTrip, useTrips } from "@/api/hooks";
import type { LiveState } from "@/api/types";
import ChatPanel from "@/components/ChatPanel";
import MapView, { type MapMarker } from "@/components/MapView";
import { useToast } from "@/components/Toast";
import { Button, Chip, EmptyState, Sheet, Skeleton, Tag } from "@/components/ui";
import { categoryOf } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { duration } from "@/lib/format";
import { googleDirections } from "@/lib/geo";
import SosSheet from "@/components/SosSheet";
import { useLive, type Source } from "@/hooks/useLive";

function ShareSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [hours, setHours] = useState(6);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string | null>(() => { try { return sessionStorage.getItem("safar.share"); } catch { return null; } });
  const link = token ? `${window.location.origin}/s/${token}` : "";
  const save = (t: string | null) => { setToken(t); try { t ? sessionStorage.setItem("safar.share", t) : sessionStorage.removeItem("safar.share"); } catch { /* ignore */ } };
  return (
    <Sheet open={open} onClose={onClose} title="Share your live location">
      {!token ? (
        <div className="space-y-5">
          <p className="text-ink-500">Anyone with the link sees your first name, your trip name and your latest position on a map. They cannot see your email or anything else. The link stops working on its own.</p>
          <div className="flex flex-wrap gap-2">{[1, 3, 6, 12, 24].map((h) => <Chip key={h} active={hours === h} onClick={() => setHours(h)}>{h} {h === 1 ? "hour" : "hours"}</Chip>)}</div>
          <Button size="lg" className="w-full" loading={busy} onClick={async () => {
            setBusy(true);
            try { save((await createShare(hours)).token); } catch (e) { toast(e instanceof ApiError ? e.message : "Could not create the link.", "error"); }
            setBusy(false);
          }}><Share2 size={18} /> Create link</Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="break-all rounded-2xl bg-mist-100 p-4 text-sm font-medium">{link}</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Button variant="outline" onClick={async () => { try { await navigator.clipboard.writeText(link); toast("Link copied"); } catch { toast("Copy the link by hand.", "error"); } }}>Copy link</Button>
            <a href={`https://wa.me/?text=${encodeURIComponent(`Follow my trip live: ${link}`)}`} target="_blank" rel="noreferrer"><Button variant="accent" className="w-full">Send on WhatsApp</Button></a>
          </div>
          <Button variant="ghost" className="w-full text-sos-600" onClick={async () => { try { await revokeShare(token); } catch { /* already gone */ } save(null); toast("Sharing stopped"); }}>Stop sharing</Button>
        </div>
      )}
    </Sheet>
  );
}

export default function Live() {
  const qc = useQueryClient();
  const toast = useToast();
  const trips = useTrips();
  const active = trips.data?.find((t) => t.status === "active");
  const trip = useTrip(active?.id);
  const t = trip.data;
  const start = useStartTrip(active?.id ?? "");
  const addStop = useAddStopTo();

  const [tracking, setTracking] = useState(false);
  const [source, setSource] = useState<Source>("gps");
  const [open, setOpen] = useState(true);
  const [chat, setChat] = useState(false);
  const [share, setShare] = useState(false);
  const [sos, setSos] = useState(false);
  const [follow, setFollow] = useState(true);

  const day = t?.itinerary.find((d) => d.day === t.active_day) ?? t?.itinerary[0];
  const firstOpen = day?.stops.find((s) => !s.visited_at);
  const live2 = useLive({
    enabled: tracking && !!t,
    source,
    target: firstOpen ? { lat: firstOpen.lat, lng: firstOpen.lng } : null,
    onState: (s: LiveState) => { if (s.arrived.length || s.schedule_updated || s.day_complete) qc.invalidateQueries({ queryKey: ["trip", active?.id] }); },
  });
  const { pos, state, link, error } = live2;
  const wide = typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
  const nextStop = state?.next_stop ?? firstOpen;
  const frameTo = useMemo<[number, number][] | undefined>(
    () => (follow && tracking && pos ? [[pos.lat, pos.lng], ...(nextStop ? [[nextStop.lat, nextStop.lng] as [number, number]] : [])] : undefined),
    [follow, tracking, pos, nextStop?.lat, nextStop?.lng], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const markers: MapMarker[] = useMemo(() => {
    const out: MapMarker[] = (day?.stops ?? []).map((s, i) => ({
      id: s.place_id, lat: s.lat, lng: s.lng, label: String(i + 1), title: s.name,
      kind: s.visited_at ? "done" : state?.next_stop?.place_id === s.place_id ? "next" : "default",
    }));
    for (const s of state?.suggestions.slice(0, 4) ?? []) out.push({ id: `s-${s.place_id}`, lat: s.lat, lng: s.lng, label: "+", kind: "alt", title: s.name });
    return out;
  }, [day, state]);

  if (trips.isLoading || (active && trip.isLoading)) return <div className="mx-auto max-w-3xl space-y-4 p-6"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-80 rounded-card" /></div>;
  if (!active || !t || !day)
    return (
      <EmptyState icon={<Navigation size={28} />} title="No trip in progress" text="Start one of your planned trips to get live guidance, delay updates and nearby suggestions." action={<Link to="/trips"><Button size="lg">Choose a trip</Button></Link>} />
    );

  const delayed = (state?.delay_min ?? 0) >= 15;
  const done = day.stops.filter((s) => s.visited_at).length;
  const pct = day.stops.length ? Math.round((done / day.stops.length) * 100) : 0;
  const next = state?.next_stop ?? (firstOpen ? { name: firstOpen.name, lat: firstOpen.lat, lng: firstOpen.lng, eta_clock: firstOpen.start_time, eta_min: null as number | null, distance_km: null as number | null } : null);
  const freeDay = day.stops.length === 0;
  const dayDone = !freeDay && (state?.day_complete || done === day.stops.length);
  const lastDay = t.active_day >= t.days;

  const LinkTag = {
    off: null,
    connecting: <Tag tone="mist"><Radio size={12} /> Connecting</Tag>,
    live: <Tag tone="lake"><Radio size={12} /> Live</Tag>,
    fallback: <Tag tone="apricot"><WifiOff size={12} /> Backup connection</Tag>,
  }[link];

  const panel = (
    <div className="space-y-4">
      {error && <div className="flex gap-2.5 rounded-2xl bg-apricot-50 p-3.5 text-sm text-apricot-800" role="alert"><CircleAlert size={18} className="mt-0.5 shrink-0" />{error}</div>}

      {!tracking ? (
        <div className="space-y-3 rounded-2xl bg-mist-50 p-4">
          <p className="font-display text-lg font-semibold">Ready when you are</p>
          <p className="text-sm text-ink-500">Turn on tracking and Safar follows your progress through day {t.active_day}. Your position is only kept while you travel.</p>
          <Button size="lg" className="w-full" onClick={() => { setSource("gps"); setTracking(true); }}><Navigation size={18} /> Start tracking</Button>
          <button onClick={() => { setSource("demo"); setTracking(true); }} className="flex w-full items-center justify-center gap-2 py-1.5 text-sm font-semibold text-lake-700"><FlaskConical size={16} /> Try the demo walk instead</button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {LinkTag}{source === "demo" && <Tag tone="apricot"><FlaskConical size={12} /> Demo walk</Tag>}
          <button onClick={() => { setTracking(false); live2.reset(); }} className="ml-auto text-sm font-semibold text-ink-500 underline underline-offset-2">Stop tracking</button>
        </div>
      )}

      {freeDay ? (
        <div className="rounded-2xl bg-lake-50 p-5 text-center">
          <p className="font-display text-xl font-semibold">Free day</p>
          <p className="mt-1 text-sm text-ink-700">Nothing is planned for day {t.active_day}. Explore at your own pace. Ideas nearby show below while you are tracking.</p>
          {lastDay ? <Link to={`/trips/${t.id}`}><Button className="mt-3">View your trip</Button></Link>
            : <Button className="mt-3" loading={start.isPending} onClick={async () => { try { await start.mutateAsync(t.active_day + 1); live2.reset(); toast(`Day ${t.active_day + 1} started`); } catch (e) { toast(e instanceof ApiError ? e.message : "Could not start the next day.", "error"); } }}>Start day {t.active_day + 1}</Button>}
        </div>
      ) : dayDone ? (
        <div className="rounded-2xl bg-lake-50 p-5 text-center">
          <PartyPopper className="mx-auto mb-2 text-lake-600" />
          <p className="font-display text-xl font-semibold">{lastDay ? "Trip complete" : `Day ${t.active_day} complete`}</p>
          {lastDay ? <Link to={`/trips/${t.id}`}><Button className="mt-3">View your trip</Button></Link>
            : <Button className="mt-3" loading={start.isPending} onClick={async () => { try { await start.mutateAsync(t.active_day + 1); live2.reset(); toast(`Day ${t.active_day + 1} started`); } catch (e) { toast(e instanceof ApiError ? e.message : "Could not start the next day.", "error"); } }}>Start day {t.active_day + 1}</Button>}
        </div>
      ) : next && (
        <div className="rounded-2xl bg-ink-900 p-4 text-white">
          <div className="text-xs font-semibold text-lake-300">Next stop</div>
          <div className="mt-0.5 font-display text-xl font-semibold leading-snug">{next.name}</div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-white/80">
            {next.eta_min != null && <span>{next.eta_min} min away, about {next.distance_km} km</span>}
            <span>Planned {state?.next_stop?.planned_start ?? firstOpen?.start_time}{state?.next_stop && <>, arriving around {state.next_stop.eta_clock}</>}</span>
          </div>
          <a href={googleDirections(next.lat, next.lng)} target="_blank" rel="noreferrer" className="mt-3 inline-flex h-10 items-center gap-2 rounded-full bg-apricot-500 px-4 text-sm font-semibold text-ink-900"><Navigation size={16} /> Directions</a>
        </div>
      )}

      {delayed && state && (
        <div className="rounded-2xl bg-apricot-50 p-3.5 text-sm text-apricot-800" role="status">
          <p className="font-semibold">You are about {state.delay_min} minutes behind{state.schedule_updated ? ". The rest of today has been moved later." : "."}</p>
          {state.at_risk_stops.length > 0 && <p className="mt-1">May not fit today: {state.at_risk_stops.join(", ")}.</p>}
        </div>
      )}
      {state?.weather?.is_wet && <div className="flex items-center gap-2 rounded-2xl bg-lake-50 p-3.5 text-sm text-lake-700"><CloudRain size={18} /> {state.weather.label} now. Indoor ideas are ranked first below.</div>}

      {!freeDay && <div>
        <div className="mb-2 flex items-center justify-between text-sm"><span className="font-semibold">Today</span><span className="text-ink-500">{done} of {day.stops.length} visited</span></div>
        <div className="h-2.5 overflow-hidden rounded-full bg-mist-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Progress today"><div className="h-full rounded-full bg-lake-600 transition-all duration-700" style={{ width: `${pct}%` }} /></div>
        <ol className="mt-3 space-y-1.5">
          {day.stops.map((s, i) => (
            <li key={`${s.place_id}-${i}`} className="flex items-center gap-3 text-sm">
              <span className={cn("grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold", s.visited_at ? "bg-lake-600 text-white" : state?.next_stop?.place_id === s.place_id ? "bg-apricot-500 text-ink-900" : "bg-mist-200 text-ink-500")}>{s.visited_at ? <Check size={13} /> : i + 1}</span>
              <span className={cn("min-w-0 flex-1 truncate", s.visited_at && "text-ink-400 line-through")}>{s.name}</span>
              <span className="tabular-nums text-ink-400">{s.start_time}</span>
            </li>
          ))}
        </ol>
      </div>}

      {state && state.suggestions.length > 0 && !dayDone && (
        <div>
          <div className="mb-2 flex items-center gap-1.5 font-semibold"><Sparkles size={16} className="text-apricot-600" /> Close to you</div>
          <ul className="space-y-2">
            {state.suggestions.slice(0, 3).map((s) => {
              const c = categoryOf(s.category);
              return (
                <li key={s.place_id} className="flex items-center gap-3 rounded-2xl border border-mist-200 p-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-lake-50 text-lake-700"><c.icon size={18} /></span>
                  <div className="min-w-0 flex-1"><div className="truncate font-semibold">{s.name}</div><div className="truncate text-xs text-ink-500">{s.reason}, visit {duration(s.visit_min)}</div></div>
                  <button aria-label={`Add ${s.name} to today`} onClick={async () => { try { await addStop.mutateAsync({ id: t.id, day: t.active_day, place_id: s.place_id }); toast(`${s.name} added to today`); } catch (e) { toast(e instanceof ApiError ? e.message : "Could not add it.", "error"); } }} className="grid size-9 shrink-0 place-items-center rounded-full bg-lake-50 text-lake-700 transition hover:bg-lake-100"><Plus size={18} /></button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );

  return (
    <div className="relative h-[calc(100dvh-4rem-4.6rem)] md:h-[calc(100dvh-4rem)]">
      <MapView markers={markers} me={pos} frame={frameTo} fit={!frameTo} padLeft={wide ? 400 : 0} padBottom={wide ? 0 : open ? 340 : 110} scroll className="!min-h-0" />

      <div className="pointer-events-none absolute inset-x-3 top-3 z-[500] flex items-start justify-between gap-2 md:left-[26rem]">
        <div className="pointer-events-auto flex flex-wrap gap-2">
          {state?.weather && <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3.5 py-2 text-sm font-semibold shadow-soft">{Math.round(state.weather.temp_c)}° {state.weather.label}</span>}
        </div>
        <div className="pointer-events-auto flex flex-col gap-2">
          <button onClick={() => setSos(true)} aria-label="Get help" className="grid size-12 place-items-center rounded-full bg-sos-600 text-white shadow-lift transition hover:bg-sos-700"><ShieldAlert size={22} /></button>
          <button onClick={() => setShare(true)} aria-label="Share live location" className="grid size-12 place-items-center rounded-full bg-white text-ink-900 shadow-lift"><Share2 size={20} /></button>
          <button onClick={() => setChat(true)} aria-label="Ask the AI assistant" className="grid size-12 place-items-center rounded-full bg-white text-ink-900 shadow-lift"><Bot size={21} /></button>
          {pos && <button onClick={() => setFollow((f) => !f)} aria-pressed={follow} aria-label="Follow my position" className={cn("grid size-12 place-items-center rounded-full shadow-lift", follow ? "bg-lake-600 text-white" : "bg-white text-ink-900")}><Crosshair size={21} /></button>}
        </div>
      </div>

      {/* Phones: bottom sheet. Desktop: side panel. */}
      <section aria-label="Live trip" className={cn(
        "absolute inset-x-0 bottom-0 z-[600] rounded-t-[1.75rem] bg-white p-4 shadow-float md:inset-y-4 md:left-4 md:right-auto md:w-[24rem] md:rounded-[1.75rem] md:p-5",
        open ? "max-h-[62%] overflow-y-auto md:max-h-none" : "md:max-h-none md:overflow-y-auto",
      )}>
        <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={open ? "Collapse panel" : "Expand panel"} className="mx-auto -mt-1 mb-2 flex w-full items-center justify-center md:hidden">
          <span className="h-1.5 w-12 rounded-full bg-mist-300" />
        </button>
        {!open && (
          <button onClick={() => setOpen(true)} className="flex w-full items-center justify-between gap-3 pb-1 text-left md:hidden">
            <span className="min-w-0"><span className="block text-xs font-semibold text-lake-700">{dayDone ? "Day complete" : "Next stop"}</span><span className="block truncate font-display text-lg font-semibold">{dayDone ? "All stops visited" : next?.name}</span></span>
            <span className="flex shrink-0 items-center gap-1 text-sm font-semibold text-ink-500">{state?.next_stop ? `${state.next_stop.eta_min} min` : done + "/" + day.stops.length}<ChevronUp size={18} /></span>
          </button>
        )}
        <div className="mb-3 hidden md:block"><div className="font-display text-xl font-semibold">{t.title}</div><div className="text-sm text-ink-500">Day {t.active_day} of {t.days}</div></div>
        <div className={open ? "" : "hidden md:block"}>{panel}</div>
        {open && <button onClick={() => setOpen(false)} className="mx-auto mt-3 flex items-center gap-1 text-sm font-semibold text-ink-400 md:hidden"><ChevronDown size={16} /> Hide details</button>}
      </section>

      <ShareSheet open={share} onClose={() => setShare(false)} />
      <SosSheet open={sos} onClose={() => setSos(false)} pos={pos} />
      <Sheet open={chat} onClose={() => setChat(false)} title="Ask Safar" wide><ChatPanel tripId={t.id} suggestions={["What is worth seeing nearby?", "Is it a good time to eat?", "How do I make up lost time?"]} /></Sheet>
    </div>
  );
}
