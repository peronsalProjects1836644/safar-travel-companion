import { Building2, ExternalLink, LocateFixed, MapPin, Phone, Pill, ShieldAlert, Siren } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useDestinations, useMeta, useNearbyHelp } from "@/api/hooks";
import { useAuth } from "@/auth/AuthProvider";
import SosSheet from "@/components/SosSheet";
import { Button, Card, Chip, ErrorNote, PageTitle, Skeleton, inputClass } from "@/components/ui";
import { cn } from "@/lib/cn";
import { googleDirections } from "@/lib/geo";

const FALLBACK = [{ label: "Police", number: "15" }, { label: "Rescue 1122", number: "1122" }, { label: "Edhi Ambulance", number: "115" }, { label: "Fire Brigade", number: "16" }, { label: "Motorway Police", number: "130" }];
const KINDS = [{ v: "hospital", label: "Hospitals", icon: Building2 }, { v: "police", label: "Police", icon: Siren }, { v: "pharmacy", label: "Pharmacies", icon: Pill }] as const;

export default function Safety() {
  const { user } = useAuth();
  const meta = useMeta();
  const dest = useDestinations();
  const [kind, setKind] = useState<(typeof KINDS)[number]["v"]>("hospital");
  const [where, setWhere] = useState<{ lat: number; lng: number; label: string } | null>(null);
  const [locError, setLocError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [sos, setSos] = useState(false);
  const help = useNearbyHelp(where?.lat, where?.lng, kind);
  const numbers = meta.data?.emergency_numbers ?? FALLBACK;

  const locate = () => {
    setLocError(null);
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (g) => { setWhere({ lat: g.coords.latitude, lng: g.coords.longitude, label: "Your location" }); setLocating(false); },
      () => { setLocError("Location is blocked or unavailable. Choose a destination below instead."); setLocating(false); },
      { timeout: 12_000, enableHighAccuracy: true },
    );
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-8 md:py-10">
      <PageTitle title="Safety" sub="Numbers you can call right now, and help close to where you are." />

      <section aria-label="Emergency numbers" className="mb-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {numbers.map((n, i) => (
          <a key={n.number} href={`tel:${n.number}`} className={cn("group flex flex-col justify-between rounded-card p-4 transition active:scale-[0.98]", i === 1 ? "bg-sos-600 text-white shadow-lift" : "bg-white shadow-soft hover:shadow-lift")}>
            <Phone size={18} className={i === 1 ? "text-white/80" : "text-sos-600"} />
            <div className="mt-6 font-display text-4xl font-semibold tabular-nums">{n.number}</div>
            <div className={cn("text-sm font-medium", i === 1 ? "text-white/85" : "text-ink-500")}>{n.label}</div>
          </a>
        ))}
      </section>

      <section className="mb-10 grid gap-4 md:grid-cols-[1fr_auto] md:items-center rounded-[1.75rem] bg-sos-100 p-6">
        <div>
          <h2 className="font-display text-xl font-semibold text-sos-700">Need to alert someone?</h2>
          <p className="mt-1 max-w-xl text-ink-700">Safar prepares a WhatsApp message with your location for each emergency contact. You tap send.</p>
          {user && <Link to="/profile" className="mt-2 inline-block text-sm font-semibold text-sos-700 underline">Manage emergency contacts</Link>}
        </div>
        {user ? <Button variant="danger" size="lg" onClick={() => setSos(true)}><ShieldAlert size={18} /> Prepare SOS message</Button> : <Link to="/login?next=/safety"><Button variant="danger" size="lg">Sign in to use SOS</Button></Link>}
      </section>

      <section aria-label="Nearby help">
        <h2 className="mb-4 font-display text-2xl font-semibold">Help nearby</h2>
        <div className="mb-4 flex flex-wrap gap-2">{KINDS.map((k) => <Chip key={k.v} active={kind === k.v} onClick={() => setKind(k.v)}><k.icon size={16} /> {k.label}</Chip>)}</div>
        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <Button variant="soft" size="lg" loading={locating} onClick={locate}><LocateFixed size={18} /> Use my location</Button>
          <select aria-label="Or choose a destination" className={cn(inputClass, "sm:max-w-xs")} value="" onChange={(e) => { const d = dest.data?.find((x) => x.name === e.target.value); if (d) { setLocError(null); setWhere({ lat: d.lat, lng: d.lng, label: d.name }); } }}>
            <option value="">Or choose a destination</option>
            {dest.data?.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
          </select>
        </div>
        {locError && <ErrorNote message={locError} />}
        {!where && !locError && <p className="rounded-2xl bg-white p-6 text-ink-500 shadow-soft">Share your location or pick a destination to see the closest {KINDS.find((k) => k.v === kind)?.label.toLowerCase()}.</p>}
        {where && (
          <>
            <p className="mb-3 flex items-center gap-1.5 text-sm text-ink-500"><MapPin size={15} /> Around {where.label}</p>
            {help.isLoading && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 rounded-card" />)}</div>}
            {help.isError && <ErrorNote message="Nearby help could not be loaded. Use the numbers above." onRetry={() => help.refetch()} />}
            {help.data && help.data.items.length === 0 && <p className="mb-3 rounded-2xl bg-white p-5 text-ink-700 shadow-soft">{help.data.source === "unavailable" ? "Live map data is not answering right now. Use the options below, or call a number above." : "Nothing found within 5 km on the live map. Use the options below, or call a number above."}</p>}
            <div className="space-y-3">
              {help.data?.items.map((i) => (
                <Card key={`${i.name}-${i.lat}`} className="flex items-center gap-4 p-4">
                  <div className="min-w-0 flex-1"><div className="truncate font-display text-lg font-semibold">{i.name}</div><div className="text-sm text-ink-500">{i.distance_km} km away</div></div>
                  {i.phone && <a href={`tel:${i.phone.replace(/[^\d+]/g, "")}`} aria-label={`Call ${i.name}`} className="grid size-11 place-items-center rounded-full bg-lake-50 text-lake-700 hover:bg-lake-100"><Phone size={18} /></a>}
                  <a href={googleDirections(i.lat, i.lng)} target="_blank" rel="noreferrer" aria-label={`Directions to ${i.name}`} className="grid size-11 place-items-center rounded-full bg-ink-900 text-white"><ExternalLink size={18} /></a>
                </Card>
              ))}
            </div>
            {help.data && (
              <div className="mt-6 space-y-3">
                {help.data.fallback.named.length > 0 && (
                  <>
                    <h3 className="font-display text-lg font-semibold">Large hospitals around {help.data.fallback.destination}</h3>
                    {help.data.fallback.named.map((h) => (
                      <Card key={h.name} className="flex items-center gap-4 p-4">
                        <div className="min-w-0 flex-1 truncate font-display text-lg font-semibold">{h.name}</div>
                        <a href={h.maps_url} target="_blank" rel="noreferrer" aria-label={`Find ${h.name} on the map`} className="grid size-11 place-items-center rounded-full bg-ink-900 text-white"><ExternalLink size={18} /></a>
                      </Card>
                    ))}
                  </>
                )}
                <a href={help.data.fallback.search_url} target="_blank" rel="noreferrer" className="inline-flex h-11 items-center gap-2 rounded-full bg-lake-50 px-5 font-semibold text-lake-700 hover:bg-lake-100"><MapPin size={17} /> Search {KINDS.find((k) => k.v === kind)?.label.toLowerCase()} on the map</a>
                <p className="text-xs text-ink-400">Live results come from OpenStreetMap volunteers and the named list is a general guide. Both may be incomplete or out of date. In an emergency, call a number above.</p>
              </div>
            )}
          </>
        )}
      </section>
      <SosSheet open={sos} onClose={() => setSos(false)} pos={where && where.label === "Your location" ? where : null} />
    </div>
  );
}
