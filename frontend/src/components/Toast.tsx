import { CheckCircle2, CircleAlert } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; text: string; kind: "ok" | "error" };
const ToastContext = createContext<(text: string, kind?: Toast["kind"]) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-2), { id, text, kind }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4200);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-24 z-[100] flex flex-col items-center gap-2 px-4 md:bottom-6" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="sheet-in pointer-events-auto flex max-w-md items-center gap-2.5 rounded-2xl bg-ink-900 px-4 py-3 text-sm text-white shadow-float">
            {t.kind === "ok" ? <CheckCircle2 size={18} className="shrink-0 text-lake-300" /> : <CircleAlert size={18} className="shrink-0 text-apricot-500" />}
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
