import { CalendarDays, Luggage, Navigation, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useTrips } from "@/api/hooks";
import { ContourArt } from "@/components/Art";
import { Button, EmptyState, ErrorNote, PageTitle, Skeleton, Tag } from "@/components/ui";
import { dateRange } from "@/lib/format";

const statusTag = { active: <Tag tone="apricot"><Navigation size={12} /> In progress</Tag>, planned: <Tag tone="lake">Planned</Tag>, completed: <Tag>Completed</Tag> } as const;

export default function Trips() {
  const trips = useTrips();
  const order = { active: 0, planned: 1, completed: 2 } as Record<string, number>;
  const list = [...(trips.data ?? [])].sort((a, b) => order[a.status] - order[b.status] || b.created_at.localeCompare(a.created_at));
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-8 md:py-10">
      <PageTitle title="My trips" right={<Link to="/plan"><Button variant="accent">New trip</Button></Link>} />
      {trips.isError && <ErrorNote message="Your trips could not be loaded." onRetry={() => trips.refetch()} />}
      {trips.isLoading && <div className="space-y-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-32 rounded-card" />)}</div>}
      {trips.data && list.length === 0 && (
        <EmptyState icon={<Luggage size={28} />} title="No trips yet" text="Plan your first trip and it will show up here." action={<Link to="/plan"><Button size="lg">Plan a trip</Button></Link>} />
      )}
      <div className="space-y-4">
        {list.map((t) => (
          <Link key={t.id} to={`/trips/${t.id}`} className="group flex overflow-hidden rounded-card border border-mist-200/70 bg-white shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-lift">
            <div className="hidden w-44 shrink-0 sm:block"><ContourArt seed={t.destination} category="mountains" /></div>
            <div className="min-w-0 flex-1 p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2">{statusTag[t.status as keyof typeof statusTag]}{t.source === "ai" && <Tag tone="mist">Planned with AI</Tag>}</div>
              <h2 className="truncate font-display text-xl font-semibold">{t.title}</h2>
              <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-500">
                <span className="inline-flex items-center gap-1.5"><CalendarDays size={15} /> {dateRange(t.start_date, t.days)}</span>
                <span className="inline-flex items-center gap-1.5"><Users size={15} /> {t.stop_count} stops, {t.days} {t.days === 1 ? "day" : "days"}</span>
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
