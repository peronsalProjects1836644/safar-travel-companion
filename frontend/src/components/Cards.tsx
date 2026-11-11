import { Clock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import type { Destination, Place } from "@/api/types";
import { categoryOf } from "@/lib/categories";
import { duration, priceLabel } from "@/lib/format";
import { PlaceImage } from "./Art";
import { Skeleton, Tag } from "./ui";

export function PlaceCard({ place, onAdd, compact }: { place: Place; onAdd?: () => void; compact?: boolean }) {
  const cat = categoryOf(place.category);
  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-card border border-mist-200/70 bg-white shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift">
      <Link to={`/places/${place.id}`} className="block flex-1 focus-visible:outline-offset-[-3px]">
        <div className="overflow-hidden">
          <PlaceImage src={place.image_url} name={place.name} category={place.category} className={compact ? "aspect-[16/9]" : "aspect-[4/3]"} />
        </div>
        <div className="space-y-2.5 p-4">
          <h3 className="font-display text-lg font-semibold leading-snug text-balance">{place.name}</h3>
          <p className="flex items-center gap-1.5 text-sm text-ink-500">
            <MapPin size={14} className="shrink-0" /> {place.destination}, {place.region}
            {place.distance_km != null && <span className="ml-auto shrink-0 font-semibold text-ink-700">{place.distance_km} km</span>}
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <Tag tone="lake"><cat.icon size={13} /> {cat.label}</Tag>
            <Tag><Clock size={12} /> {duration(place.avg_visit_minutes)}</Tag>
            <Tag>{priceLabel(place.price_level)}</Tag>
          </div>
        </div>
      </Link>
      {place.advisory && <div className="mx-4 mb-4 rounded-xl bg-apricot-50 px-3 py-2 text-xs text-apricot-800">{place.advisory}</div>}
      {onAdd && (
        <div className="mt-auto px-4 pb-4">
          <button onClick={onAdd} className="h-10 w-full rounded-full bg-lake-50 text-sm font-semibold text-lake-700 transition hover:bg-lake-100">Add to trip</button>
        </div>
      )}
    </article>
  );
}

export function PlaceCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-card border border-mist-200/70 bg-white" aria-hidden>
      <Skeleton className="aspect-[4/3] rounded-none" />
      <div className="space-y-3 p-4">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <div className="flex gap-2"><Skeleton className="h-6 w-20" /><Skeleton className="h-6 w-16" /></div>
      </div>
    </div>
  );
}

export function DestinationCard({ d, className = "" }: { d: Destination; className?: string }) {
  return (
    <Link to={`/explore?destination=${encodeURIComponent(d.name)}`} className={`group relative block overflow-hidden rounded-card shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift ${className}`}>
      <PlaceImage src={d.image_url} name={d.name} category="mountains" className="absolute inset-0 size-full transition-transform duration-700 group-hover:scale-105" iconSize={40} />
      <div className="absolute inset-0 bg-gradient-to-t from-ink-950/80 via-ink-950/15 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 p-4 text-white">
        <h3 className="font-display text-xl font-semibold leading-tight">{d.name}</h3>
        <p className="mt-0.5 text-sm text-white/80">{d.region}, {d.count} {d.count === 1 ? "place" : "places"}</p>
      </div>
    </Link>
  );
}
