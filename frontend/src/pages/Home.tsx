import { ArrowRight, CloudSun, Navigation, ShieldAlert, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { useDestinations, usePlaces, useTrips } from "@/api/hooks";
import { useAuth } from "@/auth/AuthProvider";
import { ContourArt } from "@/components/Art";
import { DestinationCard, PlaceCard, PlaceCardSkeleton } from "@/components/Cards";
import { Skeleton } from "@/components/ui";
import { dateRange } from "@/lib/format";

function HeroRoute() {
  // The one animated moment on the page: a route draws itself across terrain, then the stops appear.
  const stops = [
    { x: 54, y: 250, t: "09:00", n: "Badshahi Mosque", d: 1.2 },
    { x: 150, y: 150, t: "10:45", n: "Lahore Fort", d: 1.7 },
    { x: 262, y: 188, t: "12:30", n: "Fort Road Food Street", d: 2.2 },
    { x: 330, y: 70, t: "15:00", n: "Jahangir's Tomb", d: 2.7 },
  ];
  const path = "M54 250 C 90 190, 110 190, 150 150 S 230 215, 262 188 S 320 120, 330 70";
  return (
    <div className="relative isolate aspect-[4/4.2] w-full overflow-hidden rounded-[2rem] bg-ink-900 shadow-float sm:aspect-[4/3] lg:aspect-[4/4.4]">
      <div className="absolute inset-0 opacity-90"><ContourArt seed="hero-karakoram" category="lakes" lines={13} className="mix-blend-soft-light" /></div>
      <div className="absolute inset-0 bg-gradient-to-br from-ink-900/85 via-ink-900/70 to-lake-700/60" />
      <svg viewBox="0 0 400 320" className="absolute inset-0 size-full" aria-hidden>
        <path d={path} fill="none" stroke="#F0A35E" strokeWidth="4" strokeLinecap="round" className="route-draw" pathLength={1} style={{ ["--len" as string]: 1 }} />
        {stops.map((s, i) => (
          <g key={i} className="stop-pop" style={{ animationDelay: `${s.d}s` }}>
            <circle cx={s.x} cy={s.y} r="9" fill="#12282D" stroke="#F0A35E" strokeWidth="3" />
            <circle cx={s.x} cy={s.y} r="3" fill="#F0A35E" />
          </g>
        ))}
      </svg>
      {stops.map((s, i) => (
        <div key={i} className="absolute" style={{ left: `${(s.x / 400) * 100}%`, top: `${(s.y / 320) * 100}%`, transform: `translate(${s.x > 200 ? "calc(-100% - 14px)" : "14px"}, ${i % 2 ? "-125%" : "-30%"})` }}>
          <div className="stop-pop rounded-2xl bg-white/95 px-3 py-2 text-ink-900 shadow-lift backdrop-blur" style={{ animationDelay: `${s.d + 0.15}s` }}>
            <div className="text-[11px] font-semibold text-lake-600">{s.t}</div>
            <div className="whitespace-nowrap text-[13px] font-semibold leading-tight">{s.n}</div>
          </div>
        </div>
      ))}
      <div className="stop-pop absolute bottom-4 left-4 right-4 flex items-center justify-between rounded-2xl bg-ink-950/60 px-4 py-3 text-white backdrop-blur-md" style={{ animationDelay: "3s" }}>
        <div>
          <div className="text-xs text-lake-300">Next stop</div>
          <div className="font-display font-semibold">Fort Road Food Street</div>
        </div>
        <div className="flex items-center gap-2 text-sm"><CloudSun size={18} className="text-apricot-500" /> 24° Mainly clear</div>
      </div>
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const dest = useDestinations();
  const places = usePlaces({ limit: 6 });
  const trips = useTrips(!!user);
  const active = trips.data?.find((t) => t.status === "active");
  const next = !active ? trips.data?.find((t) => t.status === "planned") : undefined;
  const resume = active ?? next;

  return (
    <>
      <section className="mx-auto grid max-w-7xl items-center grid-cols-[minmax(0,1fr)] gap-10 px-4 pb-10 pt-8 md:px-8 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:pt-14">
        <div className="min-w-0">
          {resume && (
            <Link to={active ? "/live" : `/trips/${resume.id}`} className="mb-6 inline-flex max-w-full items-center gap-3 rounded-full border border-mist-200 bg-white py-1.5 pl-2 pr-4 shadow-soft transition hover:shadow-lift">
              <span className={`grid size-8 shrink-0 place-items-center rounded-full ${active ? "bg-apricot-500" : "bg-lake-100 text-lake-700"}`}><Navigation size={16} /></span>
              <span className="truncate text-sm font-semibold">{active ? "Trip in progress: " : "Up next: "}{resume.title}<span className="font-normal text-ink-500"> ({dateRange(resume.start_date, resume.days)})</span></span>
              <ArrowRight size={16} className="shrink-0 text-ink-500" />
            </Link>
          )}
          <h1 className="font-display text-[2.6rem] font-semibold leading-[1.02] text-balance sm:text-6xl lg:text-[4.25rem]">
            Pakistan, planned around you and guided as you go.
          </h1>
          <p className="mt-5 max-w-lg text-lg text-ink-500 text-pretty">
            Tell Safar where you are headed, how long you have and what you enjoy. You get a day-by-day plan with a budget, then a live companion that adjusts to delays, weather and where you are.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/plan" className="inline-flex h-14 items-center gap-2 rounded-full bg-apricot-500 px-7 text-base font-semibold text-ink-900 shadow-soft transition hover:bg-apricot-600 hover:text-white">
              Plan a trip <ArrowRight size={18} />
            </Link>
            <Link to="/explore" className="inline-flex h-14 items-center rounded-full border border-mist-300 bg-white px-7 text-base font-semibold transition hover:border-ink-400">
              Browse places
            </Link>
          </div>
        </div>
        <HeroRoute />
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <div className="mb-5 flex items-end justify-between">
          <h2 className="font-display text-2xl font-semibold md:text-3xl">Where to?</h2>
          <Link to="/explore" className="text-sm font-semibold text-lake-700 hover:underline">All places</Link>
        </div>
        <div className="no-scrollbar -mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 md:-mx-8 md:px-8">
          {dest.isLoading
            ? Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-64 w-52 shrink-0 rounded-card" />)
            : dest.data?.map((d) => <DestinationCard key={d.name} d={d} className="h-64 w-52 shrink-0 snap-start sm:w-60" />)}
          {dest.isError && <p className="py-6 text-ink-500">Destinations could not be loaded. Check that the server is running.</p>}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-10 md:px-8">
        <div className="grid gap-5 overflow-hidden rounded-[2rem] bg-mist-100 p-6 md:grid-cols-3 md:p-10">
          {[
            { icon: Wallet, t: "A plan that fits your budget", d: "Every itinerary comes with an estimate in rupees, split into stay, food, transport and entry, so you know before you go." },
            { icon: Navigation, t: "Guidance while you travel", d: "Share your location and Safar tracks your progress, shifts the schedule when you run late, and suggests what is close by." },
            { icon: ShieldAlert, t: "Help in one tap", d: "Emergency numbers, nearby hospitals and police, and an SOS message with your live location for the people you trust." },
          ].map((f) => (
            <div key={f.t} className="rounded-3xl bg-white/70 p-6 backdrop-blur">
              <span className="mb-4 grid size-11 place-items-center rounded-2xl bg-lake-600 text-white"><f.icon size={22} /></span>
              <h3 className="font-display text-xl font-semibold">{f.t}</h3>
              <p className="mt-2 text-ink-500">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <h2 className="mb-5 font-display text-2xl font-semibold md:text-3xl">Start with these</h2>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {places.isLoading ? Array.from({ length: 3 }, (_, i) => <PlaceCardSkeleton key={i} />) : places.data?.items.map((p) => <PlaceCard key={p.id} place={p} />)}
        </div>
        {places.data && places.data.items.length === 0 && (
          <p className="rounded-2xl bg-white p-6 text-ink-500 shadow-soft">No places yet. Load them with the seed script.</p>
        )}
      </section>

      <section className="mx-auto max-w-7xl px-4 py-10 md:px-8">
        <div className="relative isolate overflow-hidden rounded-[2rem] bg-ink-900 px-6 py-12 text-white md:px-14">
          <div className="absolute inset-0 -z-10 opacity-60"><ContourArt seed="cta-band" category="lakes" lines={14} className="mix-blend-soft-light" /></div>
          <h2 className="max-w-xl font-display text-3xl font-semibold text-balance md:text-4xl">Pick a destination and have a plan in under a minute.</h2>
          <Link to="/plan" className="mt-6 inline-flex h-14 items-center gap-2 rounded-full bg-apricot-500 px-7 font-semibold text-ink-900 transition hover:bg-white">Plan a trip <ArrowRight size={18} /></Link>
        </div>
      </section>
    </>
  );
}
