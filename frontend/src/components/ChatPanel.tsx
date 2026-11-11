import { Bot, Send, Sparkles } from "lucide-react";
import { Fragment, useEffect, useRef, useState } from "react";
import { ApiError, streamChat } from "@/api/client";
import { useAiStatus } from "@/api/hooks";
import { cn } from "@/lib/cn";
import { Button, ErrorNote } from "./ui";

type Msg = { role: "user" | "assistant"; content: string };

// Minimal, safe formatting: **bold**, "- " bullets, paragraphs. No HTML is ever injected.
function Rich({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) => (part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>));
  const lines = text.split("\n");
  const out: JSX.Element[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) out.push(<ul key={`l${out.length}`} className="my-1 list-disc space-y-0.5 pl-5">{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>);
    list = [];
  };
  lines.forEach((ln) => {
    const m = ln.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
    if (m) list.push(m[1]);
    else {
      flush();
      if (ln.trim()) out.push(<p key={`p${out.length}`}>{inline(ln)}</p>);
    }
  });
  flush();
  return <div className="space-y-1.5">{out}</div>;
}

export default function ChatPanel({ tripId, suggestions }: { tripId?: string; suggestions?: string[] }) {
  const status = useAiStatus();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs]);

  const send = async (content: string) => {
    content = content.trim();
    if (!content || busy) return;
    const history: Msg[] = [...msgs, { role: "user", content }];
    setMsgs([...history, { role: "assistant", content: "" }]);
    setText("");
    setError(null);
    setBusy(true);
    abort.current = new AbortController();
    try {
      await streamChat({ messages: history.slice(-10), trip_id: tripId ?? null }, (d) =>
        setMsgs((cur) => cur.map((m, i) => (i === cur.length - 1 ? { ...m, content: m.content + d } : m))), abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError(e instanceof ApiError ? e.message : "The assistant could not answer. Please try again.");
      setMsgs((cur) => (cur[cur.length - 1]?.content ? cur : cur.slice(0, -1)));
    } finally {
      setBusy(false);
      status.refetch();
    }
  };

  if (status.data && !status.data.available)
    return (
      <div className="rounded-2xl bg-mist-100 p-5 text-ink-700">
        <Bot className="mb-2 text-ink-400" />
        <p className="font-semibold">The assistant is switched off</p>
        <p className="mt-1 text-sm text-ink-500">It needs an OpenAI key on the server. Trip planning, maps and the live companion still work.</p>
      </div>
    );

  return (
    <div className="flex h-[min(60dvh,520px)] flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto pr-1" aria-live="polite">
        {msgs.length === 0 && (
          <div className="py-4 text-center">
            <span className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl bg-apricot-100 text-apricot-800"><Sparkles /></span>
            <p className="font-display text-lg font-semibold">Ask about your trip</p>
            <p className="mx-auto mt-1 max-w-xs text-sm text-ink-500">Answers use the places in Safar{tripId ? " and this itinerary" : ""}.</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {(suggestions ?? []).map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border border-mist-300 px-3.5 py-2 text-sm font-medium text-ink-700 transition hover:border-ink-400">{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={cn("max-w-[88%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed", m.role === "user" ? "ml-auto bg-ink-900 text-white" : "bg-mist-100 text-ink-900")}>
            {m.content ? (m.role === "assistant" ? <Rich text={m.content} /> : m.content) : <span className="inline-flex gap-1" aria-label="Typing"><i className="size-2 animate-bounce rounded-full bg-ink-300" /><i className="size-2 animate-bounce rounded-full bg-ink-300 [animation-delay:120ms]" /><i className="size-2 animate-bounce rounded-full bg-ink-300 [animation-delay:240ms]" /></span>}
          </div>
        ))}
        <div ref={end} />
      </div>
      {error && <div className="mt-2"><ErrorNote message={error} /></div>}
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Type your question" aria-label="Your question"
          className="h-12 min-w-0 flex-1 rounded-full border border-mist-300 px-5 focus:border-lake-500 focus:outline-none focus:ring-4 focus:ring-lake-100" />
        <Button type="submit" disabled={!text.trim() || busy} aria-label="Send" className="size-12 shrink-0 !px-0"><Send size={18} /></Button>
      </form>
      {status.data && <p className="mt-2 text-center text-xs text-ink-400">{status.data.remaining_today} AI requests left today</p>}
    </div>
  );
}
