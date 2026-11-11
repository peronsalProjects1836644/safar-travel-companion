import { Loader2, Minus, Plus, X } from "lucide-react";
import { useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

// ---------- Button
type Variant = "primary" | "accent" | "soft" | "ghost" | "danger" | "outline";
const VARIANT: Record<Variant, string> = {
  primary: "bg-ink-900 text-white hover:bg-ink-700 shadow-soft",
  accent: "bg-apricot-500 text-ink-900 hover:bg-apricot-600 hover:text-white shadow-soft",
  soft: "bg-lake-50 text-lake-700 hover:bg-lake-100",
  ghost: "text-ink-700 hover:bg-mist-100",
  outline: "border border-mist-300 bg-white text-ink-900 hover:border-ink-400",
  danger: "bg-sos-600 text-white hover:bg-sos-700 shadow-soft",
};
const SIZE = { sm: "h-9 px-3.5 text-sm gap-1.5", md: "h-11 px-5 text-[15px] gap-2", lg: "h-14 px-7 text-base gap-2.5" };

export function Button({
  variant = "primary", size = "md", loading, className, children, disabled, ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: keyof typeof SIZE; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center rounded-full font-semibold transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100",
        VARIANT[variant], SIZE[size], className,
      )}
    >
      {loading && <Loader2 size={18} className="animate-spin" />}
      {children}
    </button>
  );
}

// ---------- Chip (toggle)
export function Chip({ active, onClick, children, className }: { active?: boolean; onClick?: () => void; children: ReactNode; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-all duration-200",
        active ? "border-ink-900 bg-ink-900 text-white shadow-soft" : "border-mist-300 bg-white text-ink-700 hover:border-ink-400",
        className,
      )}
    >
      {children}
    </button>
  );
}

export const Tag = ({ children, tone = "mist", className }: { children: ReactNode; tone?: "mist" | "lake" | "apricot" | "sos"; className?: string }) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold",
      tone === "mist" && "bg-mist-100 text-ink-700",
      tone === "lake" && "bg-lake-100 text-lake-700",
      tone === "apricot" && "bg-apricot-100 text-apricot-800",
      tone === "sos" && "bg-sos-100 text-sos-700",
      className,
    )}
  >
    {children}
  </span>
);

// ---------- Card
export const Card = ({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) => (
  <div {...rest} className={cn("rounded-card border border-mist-200/70 bg-white shadow-soft", className)}>
    {children}
  </div>
);

export const Skeleton = ({ className }: { className?: string }) => <div className={cn("skeleton", className)} aria-hidden />;

// ---------- Fields
export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold text-ink-700">{label}</label>
      {children(id)}
      {error ? <p className="mt-1.5 text-sm text-sos-600" role="alert">{error}</p> : hint ? <p className="mt-1.5 text-sm text-ink-500">{hint}</p> : null}
    </div>
  );
}
export const inputClass =
  "h-12 w-full rounded-2xl border border-mist-300 bg-white px-4 text-base text-ink-900 placeholder:text-ink-300 transition-colors focus:border-lake-500 focus:outline-none focus:ring-4 focus:ring-lake-100";
export const Input = ({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) => <input {...rest} className={cn(inputClass, className)} />;

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: string; sub?: string }[] }) {
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }} role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-2xl border px-3 py-3 text-left transition-all duration-200",
            value === o.value ? "border-ink-900 bg-ink-900 text-white shadow-soft" : "border-mist-300 bg-white text-ink-900 hover:border-ink-400",
          )}
        >
          <div className="text-sm font-semibold">{o.label}</div>
          {o.sub && <div className={cn("mt-0.5 text-xs", value === o.value ? "text-mist-200" : "text-ink-500")}>{o.sub}</div>}
        </button>
      ))}
    </div>
  );
}

export function Stepper({ value, onChange, min, max, label }: { value: number; onChange: (n: number) => void; min: number; max: number; label: string }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-mist-300 bg-white p-1" role="group" aria-label={label}>
      <button type="button" aria-label={`Fewer ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)} className="grid size-10 place-items-center rounded-full text-ink-700 transition hover:bg-mist-100 disabled:opacity-30">
        <Minus size={18} />
      </button>
      <span className="w-10 text-center font-display text-lg font-semibold tabular-nums" aria-live="polite">{value}</span>
      <button type="button" aria-label={`More ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)} className="grid size-10 place-items-center rounded-full text-ink-700 transition hover:bg-mist-100 disabled:opacity-30">
        <Plus size={18} />
      </button>
    </div>
  );
}

// ---------- Sheet (modal on desktop, bottom sheet on phones)
export function Sheet({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1000] flex items-end justify-center md:items-center">
      <div className="fade-in absolute inset-0 bg-ink-950/45 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "sheet-in relative max-h-[88dvh] w-full overflow-y-auto rounded-t-[var(--radius-sheet)] bg-white p-5 pb-8 shadow-float outline-none md:rounded-[var(--radius-sheet)] md:p-7",
          wide ? "md:max-w-2xl" : "md:max-w-lg",
        )}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-mist-300 md:hidden" />
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="font-display text-2xl font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="grid size-9 shrink-0 place-items-center rounded-full text-ink-500 hover:bg-mist-100">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-4 py-14 text-center">
      <div className="mb-4 grid size-16 place-items-center rounded-3xl bg-lake-50 text-lake-600">{icon}</div>
      <h3 className="font-display text-xl font-semibold">{title}</h3>
      <p className="mt-1.5 text-ink-500">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-apricot-50 px-4 py-3 text-sm text-apricot-800" role="alert">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="font-semibold underline underline-offset-2">Try again</button>}
    </div>
  );
}

export const PageTitle = ({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
    <div>
      <h1 className="font-display text-3xl font-semibold md:text-4xl">{title}</h1>
      {sub && <p className="mt-1 max-w-xl text-ink-500">{sub}</p>}
    </div>
    {right}
  </div>
);
