import { ArrowLeft, Clock, CloudSun, ExternalLink, MapPin, Navigation, Plus, Sun, TriangleAlert, Wallet } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useNearbyPlaces, usePlace, useWeather } from "@/api/hooks";
import AddToTrip from "@/components/AddToTrip";
import { PlaceImage } from "@/components/Art";
import { PlaceCard } from "@/components/Cards";
import MapView from "@/components/MapView";
import { Button, Card, EmptyState, Skeleton, Tag } from "@/components/ui";
import { categoryOf } from "@/lib/categories";
import { cap, duration, priceLabel } from "@/lib/format";
import { googleDirections } from "@/lib/geo";

export default function PlaceDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const place = usePlace(id);
  const p = place.data;
  const weather = useWeather(p?.lat, p?.lng, 3);
  const near = useNearbyPlaces(p?.lat, p?.lng, 25, p?.id);
  const [adding, setAdding] = useState(false);

  if (place.isError)
    return <EmptyState icon={<MapPin size={28} />} title="Place not found" text="It may have been removed." action={<Link to="/explore"><Button>Back to explore</Button></Link>} />;

  const cat = p ? categoryOf(p.category) : null;
  return (
    <div className="mx-auto max-w-7xl px-4 py-4 md:px-8 md:py-8">
      <button onClick={() => (history.length > 1 ? nav(-1) : nav("/explore"))} className="mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-mist-100">
        <ArrowLeft size={18} /> Back
      </button>

      {!p ? (
        <div className="space-y-4"><Skeleton className="aspect-[16/8] w-full rounded-[2rem]" /><Skeleton className="h-10 w-1/2" /><Skeleton className="h-24" /></div>
      ) : (
        <>
          <div className="relative overflow-hidden rounded-[2rem] shadow-lift">
            <PlaceImage src={p.image_url} name={p.name} category={p.category} className="aspect-[4/3] sm:aspect-[16/8]" iconSize={56} />
            <div className="absolute inset-0 bg-gradient-to-t from-ink-950/75 via-transparent to-transparent" />
            <div className="absolute inset-x-0 bottom-0 p-5 text-white md:p-8">
              <Tag tone="mist" className="mb-3 bg-white/90">{cat && <cat.icon size={13} />} {cat?.label}</Tag>
              <h1 className="max-w-3xl font-display text-3xl font-semibold leading-tight text-balance md:text-5xl">{p.name}</h1>
              <p className="mt-1.5 flex items-center gap-1.5 text-white/85"><MapPin size={16} /> {p.destination}, {p.region}</p>
            </div>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-6">
              <div className="flex flex-wrap gap-3">
                <Button size="lg" variant="accent" onClick={() => setAdding(true)}><Plus size={20} /> Add to a trip</Button>
                <a href={googleDirections(p.lat, p.lng)} target="_blank" rel="noreferrer"><Button size="lg" variant="outline"><Navigation size={18} /> Directions</Button></a>
              </div>

              {p.description && <p className="max-w-prose text-lg leading-relaxed text-ink-700 text-pretty">{p.description}</p>}

              {p.advisory && (
                <div className="flex gap-3 rounded-2xl bg-apricot-50 p-4 text-apricot-800" role="note">
                  <TriangleAlert size={20} className="mt-0.5 shrink-0" />
                  <div><div className="font-semibold">Before you go</div><p className="text-sm">{p.advisory}</p></div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { icon: Clock, k: "Usual visit", v: duration(p.avg_visit_minutes) },
                  { icon: Wallet, k: "Cost", v: priceLabel(p.price_level) },
                  { icon: Sun, k: "Best time", v: p.best_season.length ? p.best_season.map(cap).join(", ") : "Any season" },
                  { icon: MapPin, k: "Setting", v: p.indoor ? "Indoors" : "Outdoors" },
                ].map((i) => (
                  <Card key={i.k} className="p-4">
                    <i.icon size={18} className="mb-2 text-lake-600" />
                    <div className="text-xs text-ink-500">{i.k}</div>
                    <div className="font-display font-semibold leading-snug">{i.v}</div>
                  </Card>
                ))}
              </div>

              {p.tags.length > 0 && <div className="flex flex-wrap gap-2">{p.tags.map((t) => <Tag key={t}>{t}</Tag>)}</div>}

              <p className="text-sm text-ink-400">
                {p.verified ? "Details checked by an administrator. " : "Details are estimates and have not been verified yet. "}
                {p.source_url && <a href={p.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-semibold text-lake-700 hover:underline">Photo: {p.image_credit ?? "Wikipedia"} <ExternalLink size={13} /></a>}
              </p>
            </div>

            <aside className="space-y-4">
              <div className="h-72 overflow-hidden rounded-card border border-mist-200 shadow-soft">
                <MapView markers={[{ id: p.id, lat: p.lat, lng: p.lng, label: "", title: p.name }]} />
              </div>
              <Card className="flex items-center gap-4 p-4">
                <span className="grid size-12 place-items-center rounded-2xl bg-apricot-100 text-apricot-800"><CloudSun size={24} /></span>
                {weather.isLoading ? <Skeleton className="h-10 flex-1" /> : weather.data ? (
                  <div className="min-w-0">
                    <div className="font-display text-lg font-semibold">{Math.round(weather.data.current.temp_c)}° {weather.data.current.label}</div>
                    <div className="text-sm text-ink-500">
                      Next days: {weather.data.daily.slice(1, 3).map((d) => `${Math.round(d.temp_max_c)}° ${d.label.toLowerCase()}`).join(", ") || "no forecast"}
                    </div>
                  </div>
                ) : <p className="text-sm text-ink-500">Weather is unavailable right now.</p>}
              </Card>
            </aside>
          </div>

          {near.data && near.data.length > 0 && (
            <section className="mt-12">
              <h2 className="mb-4 font-display text-2xl font-semibold">Nearby</h2>
              <div className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 md:-mx-8 md:px-8">
                {near.data.map((n) => <div key={n.id} className="w-64 shrink-0 snap-start sm:w-72"><PlaceCard place={n} compact /></div>)}
              </div>
            </section>
          )}
          <AddToTrip place={p} open={adding} onClose={() => setAdding(false)} />
        </>
      )}
    </div>
  );
}
