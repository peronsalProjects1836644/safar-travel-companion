import { List, Map as MapIcon, Search, SearchX, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useDestinations, useMeta, usePlaces } from "@/api/hooks";
import type { Place } from "@/api/types";
import AddToTrip from "@/components/AddToTrip";
import { PlaceImage } from "@/components/Art";
import { PlaceCard, PlaceCardSkeleton } from "@/components/Cards";
import MapView from "@/components/MapView";
import { Button, Chip, EmptyState, ErrorNote, PageTitle, inputClass } from "@/components/ui";
import { CATEGORY, categoryOf } from "@/lib/categories";
import { cn } from "@/lib/cn";

const PAGE = 24;

export default function Explore() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const destination = sp.get("destination") ?? "";
  const category = sp.get("category") ?? "";
  const urlQ = sp.get("q") ?? "";
  const [q, setQ] = useState(urlQ);
  const [limit, setLimit] = useState(PAGE);
  const [view, setView] = useState<"list" | "map">("list");
  const [adding, setAdding] = useState<Place | null>(null);
  const [picked, setPicked] = useState<Place | null>(null);

  const meta = useMeta();
  const dest = useDestinations();

  useEffect(() => {
    const t = setTimeout(() => {
      if (q !== urlQ) update({ q });
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setLimit(PAGE);
  }, [destination, category, urlQ]);

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    setSp(next, { replace: true });
  };

  const places = usePlaces({ destination, category, q: urlQ, limit: view === "map" ? 100 : limit, offset: 0 });
  const items = places.data?.items ?? [];
  const markers = useMemo(() => items.map((p) => ({ id: p.id, lat: p.lat, lng: p.lng, title: p.name, kind: picked?.id === p.id ? ("next" as const) : ("default" as const), onClick: () => setPicked(p) })), [items, picked]);
  const hasFilter = !!(destination || category || urlQ);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 md:px-8 md:py-10">
      <PageTitle
        title={destination ? destination : "Explore places"}
        sub={destination ? undefined : "Forts, lakes, valleys, food streets and more across Pakistan."}
        right={
          <div className="inline-flex rounded-full border border-mist-300 bg-white p-1" role="group" aria-label="View">
            {([["list", List, "List"], ["map", MapIcon, "Map"]] as const).map(([v, Icon, label]) => (
              <button key={v} onClick={() => { setView(v); setPicked(null); }} aria-pressed={view === v}
                className={cn("inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-sm font-semibold transition", view === v ? "bg-ink-900 text-white" : "text-ink-700")}>
                <Icon size={16} /> {label}
              </button>
            ))}
          </div>
        }
      />

      <div className="sticky top-16 z-30 -mx-4 space-y-3 border-b border-mist-200/70 bg-mist-50/90 px-4 pb-3 pt-2 backdrop-blur-xl md:-mx-8 md:px-8">
        <div className="flex gap-2.5">
          <div className="relative flex-1">
            <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-ink-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search forts, lakes, food, a city..." aria-label="Search places" className={cn(inputClass, "pl-11 pr-10")} />
            {q && <button onClick={() => { setQ(""); update({ q: "" }); }} aria-label="Clear search" className="absolute right-3 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-full text-ink-400 hover:bg-mist-100"><X size={16} /></button>}
          </div>
          <select value={destination} onChange={(e) => update({ destination: e.target.value })} aria-label="Destination" className={cn(inputClass.replace("w-full", ""), "w-[44%] shrink-0 cursor-pointer sm:w-60")}>
            <option value="">All destinations</option>
            {dest.data?.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </div>
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:px-0">
          <Chip active={!category} onClick={() => update({ category: "" })}>All</Chip>
          {(meta.data?.categories ?? (Object.keys(CATEGORY) as (keyof typeof CATEGORY)[])).map((c) => {
            const info = categoryOf(c);
            return <Chip key={c} active={category === c} onClick={() => update({ category: category === c ? "" : c })}><info.icon size={16} /> {info.label}</Chip>;
          })}
        </div>
      </div>

      <div className="mt-6">
        {places.isError && <ErrorNote message="Places could not be loaded. Check that the server is running." onRetry={() => places.refetch()} />}

        {view === "list" ? (
          <>
            {places.data && <p className="mb-4 text-sm text-ink-500" aria-live="polite">{places.data.total} {places.data.total === 1 ? "place" : "places"}</p>}
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {places.isLoading ? Array.from({ length: 6 }, (_, i) => <PlaceCardSkeleton key={i} />) : items.map((p) => <PlaceCard key={p.id} place={p} onAdd={() => setAdding(p)} />)}
            </div>
            {places.data && items.length === 0 && (
              <EmptyState icon={<SearchX size={28} />} title="Nothing matches" text="Try a different word or remove a filter." action={hasFilter ? <Button variant="soft" onClick={() => { setQ(""); nav("/explore"); }}>Clear filters</Button> : undefined} />
            )}
            {places.data && items.length < places.data.total && (
              <div className="mt-8 text-center"><Button variant="outline" loading={places.isFetching} onClick={() => setLimit((l) => l + PAGE)}>Show more</Button></div>
            )}
          </>
        ) : (
          <div className="relative h-[68dvh] overflow-hidden rounded-[1.75rem] border border-mist-200 shadow-soft">
            <MapView markers={markers} scroll />
            {picked && (
              <div className="sheet-in absolute inset-x-3 bottom-3 z-[500] flex items-center gap-3 rounded-2xl bg-white p-3 shadow-float sm:left-auto sm:w-96">
                <PlaceImage src={picked.image_url} name={picked.name} category={picked.category} className="size-16 shrink-0 rounded-xl" iconSize={22} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-display font-semibold">{picked.name}</div>
                  <div className="truncate text-sm text-ink-500">{picked.destination}</div>
                </div>
                <Button size="sm" onClick={() => nav(`/places/${picked.id}`)}>Open</Button>
                <button onClick={() => setPicked(null)} aria-label="Dismiss" className="grid size-8 shrink-0 place-items-center rounded-full text-ink-400 hover:bg-mist-100"><X size={16} /></button>
              </div>
            )}
          </div>
        )}
      </div>
      {adding && <AddToTrip place={adding} open onClose={() => setAdding(null)} />}
    </div>
  );
}
