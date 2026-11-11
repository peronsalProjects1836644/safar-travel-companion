import { Plus, Trash2, UserRound } from "lucide-react";
import { useState } from "react";
import { ApiError } from "@/api/client";
import { useAiStatus, useMeta, useUpdateProfile } from "@/api/hooks";
import type { BudgetLevel, Category, EmergencyContact, Pace } from "@/api/types";
import { useAuth } from "@/auth/AuthProvider";
import { useToast } from "@/components/Toast";
import { Button, Card, Chip, ErrorNote, Field, Input, PageTitle, Segmented } from "@/components/ui";
import { CATEGORY, categoryOf } from "@/lib/categories";

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const toast = useToast();
  const meta = useMeta();
  const ai = useAiStatus();
  const update = useUpdateProfile();
  const maxContacts = meta.data?.limits.max_emergency_contacts ?? 5;

  const [name, setName] = useState(user?.name ?? "");
  const [interests, setInterests] = useState<Category[]>(user?.preferences.interests ?? []);
  const [budget, setBudget] = useState<BudgetLevel>(user?.preferences.budget_level ?? "mid");
  const [pace, setPace] = useState<Pace>(user?.preferences.pace ?? "balanced");
  const [contacts, setContacts] = useState<EmergencyContact[]>(user?.emergency_contacts ?? []);
  const [cName, setCName] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;

  const save = async (body: Parameters<typeof update.mutateAsync>[0], ok: string) => {
    setError(null);
    try {
      setUser(await update.mutateAsync(body));
      toast(ok);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save. Please try again.");
      return false;
    }
  };
  const addContact = async () => {
    if (!cName.trim() || !cPhone.trim()) return setError("Enter a name and a phone number.");
    if (await save({ emergency_contacts: [...contacts, { name: cName.trim(), phone: cPhone.trim() }] }, "Contact saved")) {
      setCName(""); setCPhone("");
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 py-6 md:px-8 md:py-10">
      <PageTitle title="Profile" sub={user.email} />
      {error && <ErrorNote message={error} />}

      <Card className="space-y-5 p-6">
        <h2 className="font-display text-xl font-semibold">About you</h2>
        <Field label="Name">{(id) => <Input id={id} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />}</Field>
        <div>
          <div className="mb-2 text-sm font-semibold text-ink-700">Default interests</div>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(CATEGORY) as Category[]).map((c) => {
              const i = categoryOf(c);
              return <Chip key={c} active={interests.includes(c)} onClick={() => setInterests((cur) => (cur.includes(c) ? cur.filter((x) => x !== c) : cur.length >= 6 ? cur : [...cur, c]))}><i.icon size={16} /> {i.label}</Chip>;
            })}
          </div>
        </div>
        <div><div className="mb-2 text-sm font-semibold text-ink-700">Comfort level</div>
          <Segmented value={budget} onChange={setBudget} options={[{ value: "budget", label: "Lean" }, { value: "mid", label: "Comfortable" }, { value: "premium", label: "Treat yourself" }]} /></div>
        <div><div className="mb-2 text-sm font-semibold text-ink-700">Pace</div>
          <Segmented value={pace} onChange={setPace} options={[{ value: "relaxed", label: "Relaxed" }, { value: "balanced", label: "Balanced" }, { value: "packed", label: "Packed" }]} /></div>
        <Button loading={update.isPending} disabled={!name.trim()} onClick={() => save({ name: name.trim(), preferences: { interests, budget_level: budget, pace } }, "Profile saved")}>Save changes</Button>
      </Card>

      <Card className="space-y-4 p-6">
        <div>
          <h2 className="font-display text-xl font-semibold">Emergency contacts</h2>
          <p className="text-sm text-ink-500">These people get your SOS message on WhatsApp. Up to {maxContacts}.</p>
        </div>
        <ul className="space-y-2">
          {contacts.map((c, i) => (
            <li key={c.phone} className="flex items-center gap-3 rounded-2xl bg-mist-50 p-3">
              <span className="grid size-10 place-items-center rounded-full bg-lake-100 text-lake-700"><UserRound size={18} /></span>
              <div className="min-w-0 flex-1"><div className="truncate font-semibold">{c.name}</div><div className="text-sm text-ink-500">+{c.phone}</div></div>
              <button aria-label={`Remove ${c.name}`} onClick={async () => { const next = contacts.filter((_, j) => j !== i); if (await save({ emergency_contacts: next }, "Contact removed")) setContacts(next); }} className="grid size-9 place-items-center rounded-full text-ink-400 hover:bg-sos-100 hover:text-sos-600"><Trash2 size={17} /></button>
            </li>
          ))}
          {contacts.length === 0 && <li className="rounded-2xl bg-apricot-50 p-4 text-sm text-apricot-800">No contacts yet. Add at least one before you travel.</li>}
        </ul>
        {contacts.length < maxContacts && (
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <Input placeholder="Name" aria-label="Contact name" value={cName} maxLength={60} onChange={(e) => setCName(e.target.value)} />
            <Input placeholder="03xx xxxxxxx or +92..." aria-label="Contact phone" inputMode="tel" value={cPhone} onChange={(e) => setCPhone(e.target.value)} />
            <Button variant="soft" size="lg" loading={update.isPending} onClick={addContact}><Plus size={18} /> Add</Button>
          </div>
        )}
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-3 p-6">
        <div>
          <h2 className="font-display text-xl font-semibold">Account</h2>
          <p className="text-sm text-ink-500">{ai.data?.available ? `${ai.data.remaining_today} AI requests left today` : "The AI assistant is off on this server."}</p>
        </div>
        <Button variant="outline" onClick={logout}>Sign out</Button>
      </Card>
    </div>
  );
}
