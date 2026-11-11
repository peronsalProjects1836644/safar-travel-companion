import { Clock, MapPinOff } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useShareView } from "@/api/hooks";
import { Logo } from "@/components/Layout";
import MapView from "@/components/MapView";
import { Button, EmptyState, Skeleton } from "@/components/ui";
import { timeAgo } from "@/lib/format";

export default function SharePage() {
  const { token } = useParams();
  const q = useShareView(token);
  const s = q.data;
  const gone = q.error instanceof ApiError && q.error.status === 404;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex h-16 items-center justify-between border-b border-mist-200 bg-white px-4 md:px-8"><Logo /><Link to="/" className="text-sm font-semibold text-lake-700">Plan your own trip</Link></header>
      {q.isLoading ? <div className="p-6"><Skeleton className="h-8 w-64" /><Skeleton className="mt-4 h-[60dvh] rounded-card" /></div>
        : gone || q.isError ? <EmptyState icon={<MapPinOff size={28} />} title={gone ? "This link has expired" : "Could not load this link"} text={gone ? "Live sharing links stop working after the time the traveler chose, or when they stop sharing." : "Check your connection and try again."} action={<Button onClick={() => q.refetch()}>Try again</Button>} />
        : s && (
          <>
            <div className="px-4 py-4 md:px-8">
              <h1 className="font-display text-2xl font-semibold">{s.name} is travelling{s.trip_title ? `: ${s.trip_title}` : ""}</h1>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-500"><Clock size={15} /> {s.location ? `Last position ${timeAgo(s.location.updated_at)}. This page updates by itself.` : "Waiting for the first location."}</p>
            </div>
            <div className="relative mx-4 mb-4 flex-1 overflow-hidden rounded-[1.75rem] border border-mist-200 shadow-soft md:mx-8 md:mb-8" style={{ minHeight: "55dvh" }}>
              <MapView me={s.location} frame={s.location ? [[s.location.lat, s.location.lng]] : undefined} scroll className="absolute inset-0 !h-full" />
            </div>
          </>
        )}
    </div>
  );
}
