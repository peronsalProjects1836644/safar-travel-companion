import { Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAddStopTo, useTrips } from "@/api/hooks";
import { ApiError } from "@/api/client";
import type { Place } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { dateRange } from "@/lib/format";
import { cn } from "@/lib/cn";
import { useToast } from "./Toast";
import { Button, Chip, EmptyState, Sheet, Skeleton } from "./ui";

export default function AddToTrip({ place, open, onClose }: { place: Place; open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const toast = useToast();
  const trips = useTrips(open && !!user);
  const add = useAddStopTo();
  const [tripId, setTripId] = useState<string | null>(null);
  const [day, setDay] = useState(1);

  const matching = trips.data?.filter((t) => t.destination.toLowerCase() === place.destination.toLowerCase() && t.status !== "completed") ?? [];
  const chosen = matching.find((t) => t.id === tripId) ?? matching[0];

  const submit = async () => {
    if (!chosen) return;
    try {
      await add.mutateAsync({ id: chosen.id, day, place_id: place.id });
      toast(`${place.name} added to day ${day}`);
      onClose();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not add the place.", "error");
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Add to a trip">
      {!user ? (
        <EmptyState icon={<Plus />} title="Sign in to add places" text="Your trips are saved to your account." action={<Link to="/login"><Button>Sign in</Button></Link>} />
      ) : trips.isLoading ? (
        <Skeleton className="h-24" />
      ) : matching.length === 0 ? (
        <EmptyState icon={<Plus />} title={`No ${place.destination} trip yet`} text={`Plan a trip to ${place.destination} first, then you can add ${place.name} to it.`} action={<Link to="/plan"><Button>Plan a trip</Button></Link>} />
      ) : (
        <div className="space-y-5">
          <div className="space-y-2">
            {matching.map((t) => (
              <button key={t.id} onClick={() => { setTripId(t.id); setDay(1); }}
                className={cn("w-full rounded-2xl border p-4 text-left transition", chosen?.id === t.id ? "border-ink-900 bg-mist-50" : "border-mist-200 hover:border-ink-300")}>
                <div className="font-semibold">{t.title}</div>
                <div className="text-sm text-ink-500">{dateRange(t.start_date, t.days)}, {t.stop_count} stops</div>
              </button>
            ))}
          </div>
          {chosen && (
            <div>
              <div className="mb-2 text-sm font-semibold text-ink-700">Which day?</div>
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: chosen.days }, (_, i) => <Chip key={i} active={day === i + 1} onClick={() => setDay(i + 1)}>Day {i + 1}</Chip>)}
              </div>
            </div>
          )}
          <Button size="lg" className="w-full" loading={add.isPending} onClick={submit}>Add {place.name}</Button>
        </div>
      )}
    </Sheet>
  );
}
