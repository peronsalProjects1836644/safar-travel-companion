import { ArrowLeft, Bot, CalendarDays, Check, Clock, CloudRain, Navigation, Pencil, Plus, Sparkles, Trash2, TriangleAlert, Users, Wallet, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useAddStop, useCompleteTrip, useDeleteTrip, usePlaces, useRemoveStop, useRenameTrip, useStartTrip, useTrip, useWeather } from "@/api/hooks";
import type { Trip } from "@/api/types";
import ChatPanel from "@/components/ChatPanel";
import MapView, { type MapMarker } from "@/components/MapView";
import { useToast } from "@/components/Toast";
import { Button, Card, Chip, EmptyState, ErrorNote, Input, Sheet, Skeleton, Tag } from "@/components/ui";
import { categoryOf } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { cap, dateRange, duration, endTime, pkr, priceLabel, shortDate, weekday } from "@/lib/format";

const BAR = ["#1f8a88", "#f0a35e", "#12282d", "#8fd3cf", "#d9822f", "#587176"];
const BUDGET_LABEL: Record<string, string> = { budget: "Lean", mid: "Comfortable", premium: "Treat yourself" };
const humanize = (k: string) => cap(k.replace(/_/g, " "));

function AddPlaceSheet({ trip, day, open, onClose }: { trip: Trip; day: number; open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const toast = useToast();
  const add = useAddStop(trip.id);
  const places = usePlaces({ destination: trip.destination, q, limit: 12 });
  const used = new Set(trip.itinerary.flatMap((d) => d.stops.map((s) => s.place_id)));
  const pick = async (id: string, name: string) => {
    try {
      await add.mutateAsync({ day, place_id: id });
      toast(`${name} added to day ${day}`);
      onClose();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not add the place.", "error");
    }
  };
  return (
    <Sheet open={open} onClose={onClose} title={`Add a place to day ${day}`}>
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search in ${trip.destination}`} aria-label="Search places" className="mb-4" />
      <ul className="space-y-2">
        {places.isLoading && <Skeleton className="h-16" />}
        {places.data?.items.filter((p) => !used.has(p.id)).map((p) => {
          const c = categoryOf(p.category);
          return (
            <li key={p.id} className="flex items-center gap-3 rounded-2xl border border-mist-200 p-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-lake-50 text-lake-700"><c.icon size={20} /></span>
              <div className="min-w-0 flex-1"><div className="truncate font-semibold">{p.name}</div><div className="text-sm text-ink-500">{c.label}, {duration(p.avg_visit_minutes)}</div></div>
              <Button size="sm" variant="soft" disabled={add.isPending} onClick={() => pick(p.id, p.name)}>Add</Button>
            </li>
          );
        })}
        {places.data && places.data.items.filter((p) => !used.has(p.id)).length === 0 && <p className="py-6 text-center text-ink-500">No more places match.</p>}
      </ul>
    </Sheet>
  );
}

export default function TripDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const toast = useToast();
  const trip = useTrip(id);
  const t = trip.data;
  const [day, setDay] = useState(1);
  const [chat, setChat] = useState(false);
  const [adding, setAdding] = useState(false);
  const [starting, setStarting] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [title, setTitle] = useState("");
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [startDay, setStartDay] = useState(1);
  const [notice, setNotice] = useState<string | null>((loc.state as { notice?: string | null } | null)?.notice ?? null);

  const rename = useRenameTrip(id ?? "");
  const remove = useRemoveStop(id ?? "");
  const start = useStartTrip(id ?? "");
  const complete = useCompleteTrip(id ?? "");
  const del = useDeleteTrip();

  const current = t?.itinerary.find((d) => d.day === day) ?? t?.itinerary[0];
  const first = t?.itinerary[0]?.stops[0];
  const weather = useWeather(first?.lat, first?.lng, 7);
  const dayWeather = weather.data?.daily.find((w) => w.date === current?.date);

  const markers: MapMarker[] = useMemo(
    () => (current?.stops ?? []).map((s, i) => ({ id: s.place_id, lat: s.lat, lng: s.lng, label: String(i + 1), title: s.name, kind: s.visited_at ? "done" : "default" })),
    [current],
  );
  const line = useMemo(() => (current?.stops ?? []).map((s) => [s.lat, s.lng] as [number, number]), [current]);

  if (trip.isError)
    return <EmptyState icon={<TriangleAlert size={28} />} title="Trip not found" text={(trip.error as ApiError).message} action={<Link to="/trips"><Button>My trips</Button></Link>} />;
  if (!t || !current)
    return <div className="mx-auto max-w-7xl space-y-4 px-4 py-8 md:px-8"><Skeleton className="h-12 w-2/3" /><Skeleton className="h-64 rounded-card" /><Skeleton className="h-96 rounded-card" /></div>;

  const editable = t.status !== "completed";
  const run = async <T,>(fn: () => Promise<T>, ok?: string) => {
    try {
      const r = await fn();
      if (ok) toast(ok);
      return r;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong. Please try again.", "error");
    }
  };
  const b = t.budget;
  const parts = Object.entries(b.breakdown).filter(([, v]) => v > 0);
  const sum = parts.reduce((a, [, v]) => a + v, 0) || 1;
  const fit = { within: ["lake", "Within your budget"], borderline: ["apricot", "Close to your budget"], over: ["sos", "Over your budget"] }[b.fit ?? ""] as ["lake" | "apricot" | "sos", string] | undefined;

  return (
    <div className="mx-auto max-w-7xl px-4 py-4 md:px-8 md:py-8">
      <Link to="/trips" className="mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-mist-100"><ArrowLeft size={18} /> My trips</Link>

      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap gap-2">
            {t.status === "active" && <Tag tone="apricot"><Navigation size={12} /> In progress</Tag>}
            {t.status === "completed" && <Tag>Completed</Tag>}
            <Tag tone={t.source === "ai" ? "lake" : "mist"}>{t.source === "ai" ? <><Sparkles size={12} /> Planned with AI</> : "Standard planner"}</Tag>
          </div>
          <h1 className="font-display text-3xl font-semibold text-balance md:text-4xl">{t.title}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-ink-500">
            <span className="inline-flex items-center gap-1.5"><CalendarDays size={16} /> {dateRange(t.start_date, t.days)}</span>
            <span className="inline-flex items-center gap-1.5"><Users size={16} /> {t.travelers} {t.travelers === 1 ? "traveler" : "travelers"}</span>
            <span className="inline-flex items-center gap-1.5"><Wallet size={16} /> {BUDGET_LABEL[t.budget_level] ?? cap(t.budget_level)}</span>
          </p>
          {t.summary && <p className="mt-3 max-w-2xl text-ink-700 text-pretty">{t.summary}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {t.status === "active" ? <Link to="/live"><Button variant="accent" size="lg"><Navigation size={18} /> Open live trip</Button></Link>
            : t.status === "planned" && <Button variant="accent" size="lg" onClick={() => { setStartDay(t.active_day || 1); setStarting(true); }}><Navigation size={18} /> Start trip</Button>}
          <Button variant="outline" size="lg" onClick={() => setChat(true)}><Bot size={18} /> Ask AI</Button>
          <Button variant="ghost" size="lg" aria-label="Rename trip" onClick={() => { setTitle(t.title); setRenaming(true); }}><Pencil size={18} /></Button>
          <Button variant="ghost" size="lg" aria-label="Delete trip" onClick={() => setDeleting(true)}><Trash2 size={18} /></Button>
        </div>
      </header>

      {notice && (
        <div className="mb-6 flex items-start justify-between gap-3 rounded-2xl bg-apricot-50 p-4 text-sm text-apricot-800" role="status">
          <p>{notice}</p>
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="shrink-0"><X size={18} /></button>
        </div>
      )}

      {!notice && t.recommended_days != null && t.days > t.recommended_days && (
        <p className="mb-6 rounded-2xl bg-mist-100 p-4 text-sm text-ink-700">
          Recommended stay is about {t.recommended_days} day{t.recommended_days === 1 ? "" : "s"} with the places we have. You can stay longer, and the extra days are open for you to rest or explore.
        </p>
      )}

      <div className="no-scrollbar -mx-4 mb-6 flex gap-2 overflow-x-auto px-4 md:mx-0 md:px-0" role="tablist" aria-label="Days">
        {t.itinerary.map((d) => (
          <button key={d.day} role="tab" aria-selected={d.day === current.day} onClick={() => setDay(d.day)}
            className={cn("shrink-0 rounded-2xl border px-4 py-2.5 text-left transition-all", d.day === current.day ? "border-ink-900 bg-ink-900 text-white shadow-soft" : "border-mist-300 bg-white hover:border-ink-400")}>
            <div className="text-sm font-semibold">Day {d.day}</div>
            <div className={cn("text-xs", d.day === current.day ? "text-mist-200" : "text-ink-500")}>{weekday(d.date)} {shortDate(d.date)}</div>
          </button>
        ))}
      </div>

      <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr]">
        <section aria-label={`Day ${current.day} stops`}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-2xl font-semibold">{current.theme}</h2>
              <p className="text-sm text-ink-500">{current.stops.length === 0 ? "No stops planned" : `${current.stops.length} stops${current.distance_km ? `, about ${current.distance_km} km between them` : ""}`}</p>
            </div>
            {dayWeather && (
              <Tag tone={dayWeather.is_wet ? "sos" : "lake"} className="!px-3 !py-1.5 !text-sm">
                {dayWeather.is_wet ? <CloudRain size={15} /> : null} {Math.round(dayWeather.temp_min_c)} to {Math.round(dayWeather.temp_max_c)}°, {dayWeather.label.toLowerCase()}
              </Tag>
            )}
          </div>

          {current.stops.length === 0 && (
            <Card className="p-5 text-ink-700">
              <p className="font-display text-lg font-semibold text-ink-900">A free day</p>
              <p className="mt-1 text-[15px]">Nothing is planned here. Rest, repeat a favourite stop or wander. While you travel, the live companion suggests places nearby.{editable ? " You can also add a place below." : ""}</p>
            </Card>
          )}
          <ol className="relative space-y-4 pl-0">
            {current.stops.map((s, i) => {
              const c = categoryOf(s.category);
              const key = `${current.day}-${i}`;
              return (
                <li key={key} className="relative flex gap-4">
                  <div className="flex flex-col items-center">
                    <span className={cn("grid size-9 shrink-0 place-items-center rounded-full text-sm font-bold", s.visited_at ? "bg-lake-600 text-white" : "bg-ink-900 text-white")}>{s.visited_at ? <Check size={16} /> : i + 1}</span>
                    {i < current.stops.length - 1 && <span className="mt-1 w-0.5 flex-1 bg-mist-300" />}
                  </div>
                  <Card className="mb-1 flex-1 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-lake-700"><Clock size={14} /> {s.start_time} to {endTime(s.start_time, s.duration_min)}<span className="font-normal text-ink-400">({duration(s.duration_min)})</span></div>
                        <Link to={`/places/${s.place_id}`} className="font-display text-lg font-semibold leading-snug hover:text-lake-700">{s.name}</Link>
                      </div>
                      {editable && !s.visited_at && (
                        confirmRemove === key ? (
                          <div className="flex shrink-0 gap-1.5">
                            <Button size="sm" variant="danger" loading={remove.isPending} onClick={async () => { await run(() => remove.mutateAsync({ day: current.day, index: i }), "Stop removed"); setConfirmRemove(null); }}>Remove</Button>
                            <Button size="sm" variant="ghost" onClick={() => setConfirmRemove(null)}>Keep</Button>
                          </div>
                        ) : (
                          <button onClick={() => setConfirmRemove(key)} aria-label={`Remove ${s.name}`} className="grid size-9 shrink-0 place-items-center rounded-full text-ink-400 transition hover:bg-sos-100 hover:text-sos-600"><Trash2 size={17} /></button>
                        )
                      )}
                    </div>
                    {s.tip && <p className="mt-2 text-[15px] text-ink-700">{s.tip}</p>}
                    <div className="mt-3 flex flex-wrap gap-1.5"><Tag tone="lake"><c.icon size={12} /> {c.label}</Tag><Tag>{priceLabel(s.price_level)}</Tag><Tag>{s.indoor ? "Indoors" : "Outdoors"}</Tag></div>
                  </Card>
                </li>
              );
            })}
          </ol>
          {editable && <Button variant="outline" className="mt-2 w-full" onClick={() => setAdding(true)}><Plus size={18} /> Add a place to day {current.day}</Button>}
        </section>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <div className="h-72 overflow-hidden rounded-card border border-mist-200 shadow-soft md:h-96">
            <MapView markers={markers} line={line} />
          </div>
          <p className="-mt-2 text-xs text-ink-400">Dotted lines connect stops in order. They are not driving routes.</p>

          <Card className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg font-semibold">Estimated budget</h3>
                <p className="mt-1 font-display text-3xl font-semibold">{pkr(b.total)}</p>
                <p className="text-sm text-ink-500">{pkr(b.per_person)} per person, range {pkr(b.low)} to {pkr(b.high)}</p>
              </div>
              {fit && <Tag tone={fit[0]}>{fit[1]}</Tag>}
            </div>
            <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-mist-100" role="img" aria-label="Budget breakdown">
              {parts.map(([k, v], i) => <span key={k} style={{ width: `${(v / sum) * 100}%`, background: BAR[i % BAR.length] }} />)}
            </div>
            <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
              {parts.map(([k, v], i) => <li key={k} className="flex items-center justify-between gap-2"><span className="flex items-center gap-2"><i className="size-2.5 rounded-full" style={{ background: BAR[i % BAR.length] }} />{humanize(k)}</span><span className="whitespace-nowrap font-semibold tabular-nums">{pkr(v)}</span></li>)}
            </ul>
            <p className="mt-3 text-xs text-ink-400">{b.note}</p>
          </Card>

          {t.tips.length > 0 && (
            <Card className="p-5">
              <h3 className="mb-2 font-display text-lg font-semibold">Good to know</h3>
              <ul className="space-y-2 text-[15px] text-ink-700">{t.tips.map((tip, i) => <li key={i} className="flex gap-2"><Check size={17} className="mt-1 shrink-0 text-lake-600" />{tip}</li>)}</ul>
            </Card>
          )}
          {editable && t.status === "active" && (
            <Button variant="soft" className="w-full" loading={complete.isPending} onClick={() => run(() => complete.mutateAsync(undefined as never), "Trip marked as completed")}>Mark trip as completed</Button>
          )}
        </aside>
      </div>

      <Sheet open={chat} onClose={() => setChat(false)} title="Ask about this trip" wide>
        <ChatPanel tripId={t.id} suggestions={["What should I pack?", `Is day ${current.day} too busy?`, "Where should I eat?"]} />
      </Sheet>
      <AddPlaceSheet trip={t} day={current.day} open={adding} onClose={() => setAdding(false)} />

      <Sheet open={starting} onClose={() => setStarting(false)} title="Start your trip">
        <p className="mb-4 text-ink-500">Safar will follow your progress through the day you choose. You can switch days later.</p>
        <div className="mb-6 flex flex-wrap gap-2">{t.itinerary.map((d) => <Chip key={d.day} active={startDay === d.day} onClick={() => setStartDay(d.day)}>Day {d.day}</Chip>)}</div>
        <Button size="lg" className="w-full" loading={start.isPending} onClick={async () => { if (await run(() => start.mutateAsync(startDay))) nav("/live"); }}><Navigation size={18} /> Start day {startDay}</Button>
      </Sheet>

      <Sheet open={renaming} onClose={() => setRenaming(false)} title="Rename trip">
        <form onSubmit={async (e) => { e.preventDefault(); if (title.trim() && (await run(() => rename.mutateAsync(title.trim()), "Trip renamed"))) setRenaming(false); }} className="space-y-4">
          <Input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} aria-label="Trip name" autoFocus />
          <Button size="lg" className="w-full" loading={rename.isPending} disabled={!title.trim()}>Save name</Button>
        </form>
      </Sheet>

      <Sheet open={deleting} onClose={() => setDeleting(false)} title="Delete this trip?">
        <p className="mb-5 text-ink-500">This removes the plan and cannot be undone.</p>
        <div className="flex gap-3">
          <Button variant="outline" className="flex-1" onClick={() => setDeleting(false)}>Keep trip</Button>
          <Button variant="danger" className="flex-1" loading={del.isPending} onClick={async () => { if (await run(() => del.mutateAsync(t.id), "Trip deleted")) nav("/trips", { replace: true }); }}>Delete</Button>
        </div>
      </Sheet>
      {weather.isError && <div className="mt-6"><ErrorNote message="The weather forecast is unavailable right now." /></div>}
    </div>
  );
}
