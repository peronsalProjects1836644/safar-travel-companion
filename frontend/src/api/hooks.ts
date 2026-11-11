import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Destination, EmergencyContact, GeocodeHit, Meta, NearbyHelp, Place, PlaceList, PlanRequest, Preferences, ShareView,
  Sos, Stats, Trip, TripSummary, User, Weather,
} from "./types";

const DAY = 24 * 3600_000;
const qs = (o: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

// ---- reference data (changes rarely, so it is cached for a long time)
export const useMeta = () => useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta", { auth: false }), staleTime: DAY });
export const useDestinations = () =>
  useQuery({ queryKey: ["destinations"], queryFn: () => api<Destination[]>("/destinations", { auth: false }), staleTime: 30 * 60_000 });

export type PlaceFilters = { destination?: string; category?: string; q?: string; limit?: number; offset?: number };
export const usePlaces = (f: PlaceFilters) =>
  useQuery({
    queryKey: ["places", f],
    queryFn: () => api<PlaceList>(`/places${qs(f)}`, { auth: false }),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
  });
export const usePlace = (id?: string) =>
  useQuery({ queryKey: ["place", id], queryFn: () => api<Place>(`/places/${id}`, { auth: false }), enabled: !!id, staleTime: 10 * 60_000 });
export const useNearbyPlaces = (lat?: number, lng?: number, radius_km = 20, exclude?: string) =>
  useQuery({
    queryKey: ["nearby-places", lat, lng, radius_km],
    queryFn: async () => (await api<Place[]>(`/places/nearby${qs({ lat, lng, radius_km, limit: 8 })}`, { auth: false })).filter((p) => p.id !== exclude),
    enabled: lat !== undefined && lng !== undefined,
    staleTime: 10 * 60_000,
  });
export const useSuggest = (q: string) =>
  useQuery({
    queryKey: ["suggest", q],
    queryFn: () => api<Place[]>(`/places/suggest${qs({ q })}`, { auth: false }),
    enabled: q.trim().length >= 1,
    staleTime: 5 * 60_000,
  });

// ---- trips
export const useTrips = (enabled = true) =>
  useQuery({ queryKey: ["trips"], queryFn: () => api<TripSummary[]>("/trips"), enabled, staleTime: 30_000 });
export const useTrip = (id?: string) => useQuery({ queryKey: ["trip", id], queryFn: () => api<Trip>(`/trips/${id}`), enabled: !!id, staleTime: 30_000 });

function useTripMutation<V>(fn: (v: V) => Promise<Trip>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (trip) => {
      qc.setQueryData(["trip", trip.id], trip);
      qc.invalidateQueries({ queryKey: ["trips"] });
    },
  });
}
export const usePlanTrip = () => useTripMutation((body: PlanRequest) => api<Trip>("/trips/plan", { method: "POST", body }));
export const useRenameTrip = (id: string) => useTripMutation((title: string) => api<Trip>(`/trips/${id}`, { method: "PATCH", body: { title } }));
export const useAddStop = (id: string) =>
  useTripMutation((v: { day: number; place_id: string }) => api<Trip>(`/trips/${id}/stops`, { method: "POST", body: v }));
export const useRemoveStop = (id: string) =>
  useTripMutation((v: { day: number; index: number }) => api<Trip>(`/trips/${id}/days/${v.day}/stops/${v.index}`, { method: "DELETE" }));
export const useStartTrip = (id: string) => useTripMutation((day: number) => api<Trip>(`/trips/${id}/start`, { method: "POST", body: { day } }));
export const useCompleteTrip = (id: string) => useTripMutation(() => api<Trip>(`/trips/${id}/complete`, { method: "POST" }));
export const useDeleteTrip = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/trips/${id}`, { method: "DELETE" }),
    onSuccess: (_d, id) => {
      qc.removeQueries({ queryKey: ["trip", id] });
      qc.invalidateQueries({ queryKey: ["trips"] });
    },
  });
};

// ---- info
export const useWeather = (lat?: number, lng?: number, days = 5) =>
  useQuery({
    queryKey: ["weather", lat?.toFixed(2), lng?.toFixed(2), days],
    queryFn: () => api<Weather>(`/weather${qs({ lat, lng, days })}`, { auth: false }),
    enabled: lat !== undefined && lng !== undefined,
    staleTime: 20 * 60_000,
    retry: 0,
  });
export const useNearbyHelp = (lat?: number, lng?: number, kind = "hospital") =>
  useQuery({
    queryKey: ["help", lat?.toFixed(3), lng?.toFixed(3), kind],
    queryFn: () => api<NearbyHelp>(`/safety/nearby${qs({ lat, lng, kind })}`, { auth: false }),
    enabled: lat !== undefined && lng !== undefined,
    staleTime: 10 * 60_000,
  });
export const useAiStatus = (enabled = true) =>
  useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api<{ available: boolean; model: string | null; remaining_today: number }>("/ai/status"),
    enabled,
    staleTime: 30_000,
  });
export const geocode = (q: string) => api<GeocodeHit[]>(`/geocode/search${qs({ q })}`);
export const sendSos = (v: { lat: number; lng: number; note?: string }) => api<Sos>("/safety/sos", { method: "POST", body: v });

// ---- sharing
export const createShare = (hours: number) => api<{ token: string; expires_at: string }>("/share", { method: "POST", body: { hours } });
export const revokeShare = (token: string) => api<void>(`/share/${token}`, { method: "DELETE" });
export const useShareView = (token?: string) =>
  useQuery({
    queryKey: ["share", token],
    queryFn: () => api<ShareView>(`/share/${token}`, { auth: false }),
    enabled: !!token,
    refetchInterval: 15_000,
    retry: false,
  });

// ---- profile
export const useUpdateProfile = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; preferences?: Preferences; emergency_contacts?: EmergencyContact[] }) =>
      api<User>("/auth/me", { method: "PATCH", body }),
    onSuccess: (u) => qc.setQueryData(["me"], u),
  });
};

// ---- admin
export const useStats = () => useQuery({ queryKey: ["admin", "stats"], queryFn: () => api<Stats>("/admin/stats") });
export const useAdminUsers = () =>
  useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api<{ id: string; email: string; name: string; role: string; disabled: boolean; created_at: string }[]>("/admin/users?limit=100"),
  });
export const useSetDisabled = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; disabled: boolean }) => api(`/admin/users/${v.id}`, { method: "PATCH", body: { disabled: v.disabled } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
};
export const savePlace = (id: string, body: Omit<Place, "id" | "distance_km">) => api<Place>(`/admin/places/${id}`, { method: "PUT", body });
export const deletePlace = (id: string) => api<void>(`/admin/places/${id}`, { method: "DELETE" });

export const useAddStopTo = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; day: number; place_id: string }) =>
      api<Trip>(`/trips/${v.id}/stops`, { method: "POST", body: { day: v.day, place_id: v.place_id } }),
    onSuccess: (trip) => {
      qc.setQueryData(["trip", trip.id], trip);
      qc.invalidateQueries({ queryKey: ["trips"] });
    },
  });
};
