import { ArrowLeft, ArrowRight, Check, Loader2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useAiStatus, useDestinations, useMeta, usePlanTrip } from "@/api/hooks";
import type { BudgetLevel, Category, Pace } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { ContourArt } from "@/components/Art";
import { Button, Chip, ErrorNote, Field, Input, Segmented, Stepper, inputClass } from "@/components/ui";
import { CATEGORY, categoryOf } from "@/lib/categories";
import { addDaysIso, isoToday } from "@/lib/format";
import { cn } from "@/lib/cn";

const STEPS = ["Where and when", "Who and budget", "What you enjoy"];
const WAIT_MESSAGES = ["Choosing places that fit your interests", "Ordering stops to keep travel short", "Fitting visits into each day", "Estimating your budget"];

export default function Plan() {
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const { user } = useAuth();
  const meta = useMeta();
  const dest = useDestinations();
  const plan = usePlanTrip();
  const aiOn = useAiStatus(!!user).data?.available === true;
  const limits = meta.data?.limits ?? { max_days: 7, max_travelers: 20, max_interests: 6, max_emergency_contacts: 5 };

  const [step, setStep] = useState(0);
  const [destination, setDestination] = useState(sp.get("destination") ?? "");
  const [start, setStart] = useState(addDaysIso(isoToday(), 7));
  const [days, setDays] = useState(3);
  const [travelers, setTravelers] = useState(2);
  const [budgetLevel, setBudgetLevel] = useState<BudgetLevel>(user?.preferences.budget_level ?? "mid");
  const [total, setTotal] = useState("");
  const [interests, setInterests] = useState<Category[]>(user?.preferences.interests ?? []);
  const [pace, setPace] = useState<Pace>(user?.preferences.pace ?? "balanced");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!plan.isPending) return;
    const t = setInterval(() => setMsg((m) => (m + 1) % WAIT_MESSAGES.length), 2600);
    return () => clearInterval(t);
  }, [plan.isPending]);

  const totalNum = total ? Number(total.replace(/[^\d]/g, "")) : undefined;
  const stepError = useMemo(() => {
    if (step === 0) {
      if (!destination) return "Choose a destination.";
      if (!start || start < addDaysIso(isoToday(), -1)) return "Pick a start date that is not in the past.";
    }
    if (step === 1 && totalNum !== undefined && totalNum < 1000) return "Enter a budget of at least Rs 1,000, or leave it empty.";
    if (step === 2 && interests.length === 0) return "Pick at least one interest.";
    return null;
  }, [step, destination, start, totalNum, interests]);

  const toggle = (c: Category) =>
    setInterests((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : cur.length >= limits.max_interests ? cur : [...cur, c]));

  const next = () => (stepError ? setError(stepError) : (setError(null), setStep((s) => s + 1)));
  const submit = async () => {
    if (stepError) return setError(stepError);
    setError(null);
    try {
      const trip = await plan.mutateAsync({
        destination, start_date: start, days, travelers, budget_level: budgetLevel, interests, pace,
        notes: notes.trim() || null, budget_total_pkr: totalNum ?? null,
      });
      nav(`/trips/${trip.id}`, { state: { notice: trip.notice ?? null, fresh: true } });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the plan. Please try again.");
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-8 md:py-12">
      <div className="mb-8">
        <h1 className="font-display text-3xl font-semibold md:text-4xl">Plan a trip</h1>
        <ol className="mt-5 flex items-center gap-2" aria-label="Progress">
          {STEPS.map((s, i) => (
            <li key={s} className="flex flex-1 items-center gap-2" aria-current={i === step ? "step" : undefined}>
              <span className={cn("grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold", i < step ? "bg-lake-600 text-white" : i === step ? "bg-ink-900 text-white" : "bg-mist-200 text-ink-500")}>
                {i < step ? <Check size={14} /> : i + 1}
              </span>
              <span className={cn("hidden text-sm font-semibold sm:block", i === step ? "text-ink-900" : "text-ink-400")}>{s}</span>
              {i < STEPS.length - 1 && <span className={cn("h-0.5 flex-1 rounded", i < step ? "bg-lake-600" : "bg-mist-200")} />}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-sm font-semibold text-ink-500 sm:hidden">{STEPS[step]}</p>
      </div>

      <div className="rounded-[1.75rem] border border-mist-200/70 bg-white p-5 shadow-soft md:p-8">
        {step === 0 && (
          <div className="space-y-7">
            <fieldset>
              <legend className="mb-3 text-sm font-semibold text-ink-700">Destination</legend>
              <div className="flex flex-wrap gap-2">
                {dest.isLoading && <span className="text-ink-500">Loading destinations...</span>}
                {dest.data?.map((d) => <Chip key={d.name} active={destination === d.name} onClick={() => setDestination(d.name)}>{d.name}<span className={cn("text-xs", destination === d.name ? "text-mist-200" : "text-ink-400")}>{d.count}</span></Chip>)}
              </div>
              {dest.isError && <ErrorNote message="Destinations could not be loaded. Check that the server is running." onRetry={() => dest.refetch()} />}
            </fieldset>
            <div className="grid gap-6 sm:grid-cols-2">
              <Field label="Start date">{(id) => <Input id={id} type="date" value={start} min={addDaysIso(isoToday(), -1)} onChange={(e) => setStart(e.target.value)} />}</Field>
              <div>
                <div className="mb-1.5 text-sm font-semibold text-ink-700">Days</div>
                <Stepper label="days" value={days} onChange={setDays} min={1} max={limits.max_days} />
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-7">
            <div>
              <div className="mb-1.5 text-sm font-semibold text-ink-700">Travelers</div>
              <Stepper label="travelers" value={travelers} onChange={setTravelers} min={1} max={limits.max_travelers} />
            </div>
            <div>
              <div className="mb-2 text-sm font-semibold text-ink-700">Comfort level</div>
              <Segmented value={budgetLevel} onChange={setBudgetLevel} options={[
                { value: "budget", label: "Lean", sub: "Hostels, local food" },
                { value: "mid", label: "Comfortable", sub: "Mid-range hotels" },
                { value: "premium", label: "Treat yourself", sub: "Best stays and meals" },
              ]} />
            </div>
            <Field label="Total budget in rupees (optional)" hint="If you add one, the plan tells you whether the estimate fits.">
              {(id) => <Input id={id} inputMode="numeric" placeholder="For example 150000" value={total} onChange={(e) => setTotal(e.target.value.replace(/[^\d,]/g, ""))} />}
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-7">
            <fieldset>
              <legend className="mb-1 text-sm font-semibold text-ink-700">Interests</legend>
              <p className="mb-3 text-sm text-ink-500">Pick up to {limits.max_interests}. {interests.length}/{limits.max_interests} chosen.</p>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(CATEGORY) as Category[]).map((c) => {
                  const info = categoryOf(c);
                  return <Chip key={c} active={interests.includes(c)} onClick={() => toggle(c)}><info.icon size={16} /> {info.label}</Chip>;
                })}
              </div>
            </fieldset>
            <div>
              <div className="mb-2 text-sm font-semibold text-ink-700">Pace</div>
              <Segmented value={pace} onChange={setPace} options={[
                { value: "relaxed", label: "Relaxed", sub: "Fewer stops, more time" },
                { value: "balanced", label: "Balanced", sub: "A steady day" },
                { value: "packed", label: "Packed", sub: "See as much as possible" },
              ]} />
            </div>
            <Field label="Describe your trip (optional)" hint={aiOn ? "Safar's AI reads this and shapes your plan around it. For example: travelling with young children, or no long hikes." : "For example: travelling with young children, or no long hikes. This is used when AI planning is switched on, and the standard planner ignores it."}>
              {(id) => <textarea id={id} value={notes} maxLength={200} onChange={(e) => setNotes(e.target.value)} rows={2} className={cn(inputClass, "h-auto py-3")} />}
            </Field>
          </div>
        )}

        {error && <div className="mt-6"><ErrorNote message={error} /></div>}

        <div className="mt-8 flex items-center justify-between gap-3">
          <Button variant="ghost" onClick={() => { setError(null); setStep((s) => s - 1); }} className={step === 0 ? "invisible" : ""}><ArrowLeft size={18} /> Back</Button>
          {step < STEPS.length - 1 ? (
            <Button size="lg" onClick={next}>Continue <ArrowRight size={18} /></Button>
          ) : (
            <Button size="lg" variant="accent" onClick={submit} loading={plan.isPending}><Sparkles size={18} /> Create my plan</Button>
          )}
        </div>
      </div>

      {plan.isPending && (
        <div className="fixed inset-0 z-[95] grid place-items-center bg-ink-900 px-6 text-center text-white">
          <div className="absolute inset-0 opacity-50"><ContourArt seed="loading" category="lakes" lines={14} className="mix-blend-soft-light" /></div>
          <div className="relative">
            <Loader2 size={44} className="mx-auto mb-6 animate-spin text-apricot-500" />
            <h2 className="font-display text-3xl font-semibold">Building your {destination} plan</h2>
            <p className="mt-3 min-h-6 text-lake-300" aria-live="polite">{WAIT_MESSAGES[msg]}...</p>
            <p className="mt-8 text-sm text-white/60">This can take up to half a minute.</p>
          </div>
        </div>
      )}
    </div>
  );
}
