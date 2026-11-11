import { Compass, LogOut, Map as MapIcon, Navigation, ShieldAlert, Sparkles, Luggage, UserRound, Settings2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useTrips } from "@/api/hooks";
import { useAuth } from "@/auth/AuthProvider";
import { cn } from "@/lib/cn";

export function Logo({ light }: { light?: boolean }) {
  return (
    <Link to="/" className="inline-flex items-center gap-2.5" aria-label="Safar home">
      <svg width="34" height="34" viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="18" fill={light ? "#fff" : "#12282D"} />
        <path d="M10 46c8-2 10-20 20-20s10 12 16 12 6-8 8-8" fill="none" stroke="#F0A35E" strokeWidth="5" strokeLinecap="round" />
        <circle cx="48" cy="22" r="5" fill={light ? "#1F8A88" : "#8FD3CF"} />
      </svg>
      <span className={cn("font-display text-[22px] font-bold tracking-tight", light ? "text-white" : "text-ink-900")}>Safar</span>
    </Link>
  );
}

const NAV = [
  { to: "/explore", label: "Explore", icon: Compass },
  { to: "/plan", label: "Plan", icon: Sparkles },
  { to: "/trips", label: "My trips", icon: Luggage },
  { to: "/live", label: "Live", icon: Navigation },
  { to: "/safety", label: "Safety", icon: ShieldAlert },
];

function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  if (!user)
    return (
      <Link to="/login" className="inline-flex h-10 items-center rounded-full bg-ink-900 px-5 text-sm font-semibold text-white transition hover:bg-ink-700">
        Sign in
      </Link>
    );
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu"
        className="grid size-10 place-items-center rounded-full bg-lake-100 font-display text-base font-bold text-lake-700 transition hover:bg-lake-300/60">
        {user.name.charAt(0).toUpperCase()}
      </button>
      {open && (
        <div role="menu" className="sheet-in absolute right-0 top-12 z-50 w-60 overflow-hidden rounded-2xl border border-mist-200 bg-white p-1.5 shadow-lift">
          <div className="px-3 py-2.5">
            <div className="truncate font-semibold">{user.name}</div>
            <div className="truncate text-sm text-ink-500">{user.email}</div>
          </div>
          <div className="my-1 h-px bg-mist-200" />
          <Link role="menuitem" to="/profile" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium hover:bg-mist-100"><UserRound size={18} /> Profile and contacts</Link>
          {user.role === "admin" && (
            <Link role="menuitem" to="/admin" onClick={() => setOpen(false)} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium hover:bg-mist-100"><Settings2 size={18} /> Admin</Link>
          )}
          <button role="menuitem" onClick={() => { setOpen(false); logout(); }} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium text-sos-600 hover:bg-sos-100"><LogOut size={18} /> Sign out</button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const trips = useTrips(!!user);
  const live = !!trips.data?.some((t) => t.status === "active");
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  const immersive = pathname === "/live";

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-40 border-b border-mist-200/70 bg-mist-50/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 md:px-8">
          <Logo />
          <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => cn("relative rounded-full px-4 py-2 text-[15px] font-semibold transition-colors", isActive ? "bg-ink-900 text-white" : "text-ink-700 hover:bg-mist-100")}>
                {n.label}
                {n.to === "/live" && live && <span className="absolute right-2 top-1.5 size-2 rounded-full bg-apricot-500 ring-2 ring-mist-50" />}
              </NavLink>
            ))}
          </nav>
          <ProfileMenu />
        </div>
      </header>

      <main className={cn("flex-1", !immersive && "pb-28 md:pb-12")}>
        <Outlet />
      </main>

      <nav className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-mist-200 bg-white/92 backdrop-blur-xl md:hidden" aria-label="Main">
        <ul className="mx-auto flex max-w-lg items-stretch justify-around px-2 pt-1.5 pb-1.5">
          {NAV.map((n) => (
            <li key={n.to} className="flex-1">
              <NavLink to={n.to} className={({ isActive }) => cn("relative flex flex-col items-center gap-0.5 rounded-2xl py-1.5 text-[11px] font-semibold transition-colors", isActive ? "text-ink-900" : "text-ink-400")}>
                {({ isActive }) => (
                  <>
                    <span className={cn("grid h-8 w-14 place-items-center rounded-full transition-colors", isActive && (n.to === "/plan" ? "bg-apricot-500" : "bg-lake-100"))}>
                      <n.icon size={21} strokeWidth={isActive ? 2.4 : 1.9} />
                    </span>
                    {n.label}
                    {n.to === "/live" && live && <span className="absolute right-4 top-1 size-2 rounded-full bg-apricot-500" />}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {!immersive && (
        <footer className="hidden border-t border-mist-200 py-6 text-center text-sm text-ink-400 md:block">
          <MapIcon size={14} className="mr-1.5 inline" /> Maps by OpenStreetMap contributors. Weather by Open-Meteo.
        </footer>
      )}
    </div>
  );
}
