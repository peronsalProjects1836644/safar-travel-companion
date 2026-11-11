export const pkr = (n: number) => "Rs " + Math.round(n).toLocaleString("en-PK");

/** 95 -> "1 h 35 min", 45 -> "45 min" */
export function duration(min: number): string {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  if (h && m) return `${h} h ${m} min`;
  return h ? `${h} h` : `${m} min`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}
export function dateRange(startIso: string, days: number): string {
  const s = new Date(startIso + "T00:00:00");
  const e = new Date(s);
  e.setDate(e.getDate() + days - 1);
  const a = `${s.getDate()} ${MONTHS[s.getMonth()]}`;
  const b = `${e.getDate()} ${MONTHS[e.getMonth()]}`;
  return days === 1 ? a : `${a} to ${b}`;
}
export function weekday(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short" });
}
export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}
export const isoToday = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
};
export const addDaysIso = (iso: string, n: number) => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
};
/** "09:00" + 90 -> "10:30" */
export function endTime(start: string, minutes: number): string {
  const [h, m] = start.split(":").map(Number);
  const t = (h * 60 + m + minutes) % (24 * 60);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}
export const priceLabel = (level: number) => ["Free", "Low cost", "Moderate", "Premium"][level] ?? "";
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
