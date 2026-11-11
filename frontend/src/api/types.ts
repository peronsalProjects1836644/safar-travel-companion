import type { components } from "./schema";

type S = components["schemas"];
export type Place = S["PlaceOut"];
export type PlaceList = S["PlaceList"];
export type Destination = S["DestinationOut"];
export type Trip = S["TripOut"];
export type TripSummary = S["TripSummary"];
export type TripStop = S["TripStop"];
export type DayPlan = S["DayPlan"];
export type User = S["UserOut"];
export type AuthResponse = S["AuthResponse"];
export type PlanRequest = S["PlanRequest"];
export type EmergencyContact = S["EmergencyContact"];
export type Preferences = S["Preferences"];
export type Category = PlanRequest["interests"][number];
export type BudgetLevel = NonNullable<PlanRequest["budget_level"]>;
export type Pace = NonNullable<PlanRequest["pace"]>;

// Endpoints without a response model are typed by hand to match the backend.
export type Meta = {
  categories: Category[];
  budget_levels: BudgetLevel[];
  paces: Pace[];
  seasons: string[];
  limits: { max_days: number; max_travelers: number; max_interests: number; max_emergency_contacts: number };
  emergency_numbers: { label: string; number: string }[];
};

export type Weather = {
  current: { temp_c: number; code: number; label: string; wind_kmh: number; precipitation_mm: number; is_wet: boolean };
  daily: { date: string; code: number; label: string; temp_max_c: number; temp_min_c: number; precip_probability: number; is_wet: boolean }[];
  stale: boolean;
};

export type NearbyHelp = {
  source: "live" | "cache" | "stale" | "unavailable";
  items: { name: string; lat: number; lng: number; phone?: string | null; distance_km: number }[];
  emergency_numbers: { label: string; number: string }[];
  fallback: { destination: string | null; search_url: string; named: { name: string; area: string; maps_url: string }[] };
};

export type Sos = {
  message: string;
  map_url: string;
  contacts: { name: string; phone: string; whatsapp_url: string }[];
  emergency_numbers: { label: string; number: string }[];
};

export type GeocodeHit = { name: string; display_name: string; lat: number; lng: number; type: string | null };

export type Suggestion = {
  place_id: string; name: string; category: string; lat: number; lng: number;
  distance_km: number; eta_min: number; visit_min: number; score: number; reason: string;
};

export type LiveState = {
  type: "state";
  day: number;
  next_stop: {
    index: number; place_id: string; name: string; lat: number; lng: number;
    distance_km: number; eta_min: number; eta_clock: string; planned_start: string;
  } | null;
  arrived: string[];
  delay_min: number | null;
  schedule_updated: boolean;
  at_risk_stops: string[];
  progress: { done: number; total: number };
  day_complete: boolean;
  trip_complete?: boolean;
  throttled?: boolean;
  weather: { label: string; temp_c: number; is_wet: boolean } | null;
  suggestions: Suggestion[];
};

export type ShareView = {
  name: string;
  trip_title: string | null;
  location: { lat: number; lng: number; accuracy_m: number | null; updated_at: string } | null;
  expires_at: string;
};

export type Stats = {
  users: number; trips: number; places: number; active_shares: number; ai_calls_today: number;
  trips_by_source: { ai: number; rules: number };
};
