import { Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import { deletePlace, savePlace, useAdminUsers, usePlaces, useSetDisabled, useStats } from "@/api/hooks";
import type { Place } from "@/api/types";
import { useToast } from "@/components/Toast";
import { Button, Card, ErrorNote, Field, Input, PageTitle, Sheet, Skeleton, Tag, inputClass } from "@/components/ui";
import { cn } from "@/lib/cn";

function EditPlace({ place, onClose }: { place: Place; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [f, setF] = useState({ description: place.description, image_url: place.image_url ?? "", advisory: place.advisory ?? "", price_level: place.price_level, avg_visit_minutes: place.avg_visit_minutes, verified: place.verified });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      const { id: _id, distance_km: _d, ...rest } = place; // eslint-disable-line @typescript-eslint/no-unused-vars
      await savePlace(place.id, { ...rest, ...f, image_url: f.image_url.trim() || null, advisory: f.advisory.trim() || null } as never);
      qc.invalidateQueries({ queryKey: ["places"] });
      qc.invalidateQueries({ queryKey: ["place", place.id] });
      toast("Place saved");
      onClose();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save.", "error");
      setBusy(false);
    }
  };
  return (
    <Sheet open onClose={onClose} title={place.name} wide>
      <div className="space-y-4">
        <Field label="Description">{(id) => <textarea id={id} rows={3} maxLength={600} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} className={cn(inputClass, "h-auto py-3")} />}</Field>
        <Field label="Photo address (https://...)">{(id) => <Input id={id} value={f.image_url} onChange={(e) => setF({ ...f, image_url: e.target.value })} />}</Field>
        <Field label="Advisory (shown as a warning)">{(id) => <Input id={id} maxLength={200} value={f.advisory} onChange={(e) => setF({ ...f, advisory: e.target.value })} />}</Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Cost level (0 free to 3 premium)">{(id) => <Input id={id} type="number" min={0} max={3} value={f.price_level} onChange={(e) => setF({ ...f, price_level: Number(e.target.value) })} />}</Field>
          <Field label="Usual visit (minutes)">{(id) => <Input id={id} type="number" min={15} max={600} value={f.avg_visit_minutes} onChange={(e) => setF({ ...f, avg_visit_minutes: Number(e.target.value) })} />}</Field>
        </div>
        <label className="flex items-center gap-3 font-medium"><input type="checkbox" className="size-5 accent-[var(--color-lake-600)]" checked={f.verified} onChange={(e) => setF({ ...f, verified: e.target.checked })} /> I have checked these details</label>
        <Button size="lg" className="w-full" loading={busy} onClick={save}>Save place</Button>
      </div>
    </Sheet>
  );
}

export default function Admin() {
  const toast = useToast();
  const qc = useQueryClient();
  const stats = useStats();
  const users = useAdminUsers();
  const setDisabled = useSetDisabled();
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(20);
  const places = usePlaces({ q, limit });
  const [editing, setEditing] = useState<Place | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const s = stats.data;

  return (
    <div className="mx-auto max-w-6xl space-y-10 px-4 py-6 md:px-8 md:py-10">
      <PageTitle title="Admin" sub="Usage, accounts and place details." />
      {stats.isError && <ErrorNote message="Could not load statistics." />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[["Users", s?.users], ["Trips", s?.trips], ["Places", s?.places], ["AI calls today", s?.ai_calls_today], ["Live links", s?.active_shares]].map(([k, v]) => (
          <Card key={k as string} className="p-4"><div className="text-sm text-ink-500">{k}</div>{stats.isLoading ? <Skeleton className="mt-1 h-8 w-12" /> : <div className="font-display text-3xl font-semibold tabular-nums">{v ?? 0}</div>}</Card>
        ))}
      </div>
      {s && <p className="-mt-6 text-sm text-ink-500">Trips by planner: {s.trips_by_source.ai} AI, {s.trips_by_source.rules} standard.</p>}

      <section>
        <h2 className="mb-3 font-display text-2xl font-semibold">Places</h2>
        <div className="relative mb-4 max-w-md"><Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-ink-400" /><Input placeholder="Search places" aria-label="Search places" value={q} onChange={(e) => setQ(e.target.value)} className="pl-11" /></div>
        <Card className="divide-y divide-mist-200 overflow-hidden">
          {places.data?.items.map((p) => (
            <div key={p.id} className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1"><div className="truncate font-semibold">{p.name}</div><div className="text-sm text-ink-500">{p.destination}, {p.category}</div></div>
              <Tag tone={p.verified ? "lake" : "apricot"}>{p.verified ? "Verified" : "Unchecked"}</Tag>
              {!p.image_url && <Tag>No photo</Tag>}
              <Button size="sm" variant="soft" onClick={() => setEditing(p)}>Edit</Button>
              {confirm === p.id ? (
                <Button size="sm" variant="danger" onClick={async () => { try { await deletePlace(p.id); qc.invalidateQueries({ queryKey: ["places"] }); toast("Place deleted"); } catch { toast("Could not delete.", "error"); } setConfirm(null); }}>Confirm</Button>
              ) : <button aria-label={`Delete ${p.name}`} onClick={() => setConfirm(p.id)} className="grid size-9 place-items-center rounded-full text-ink-400 hover:bg-sos-100 hover:text-sos-600"><Trash2 size={17} /></button>}
            </div>
          ))}
        </Card>
        {places.data && limit < places.data.total && <div className="mt-4 text-center"><Button variant="outline" onClick={() => setLimit((l) => l + 20)}>Show more</Button></div>}
      </section>

      <section>
        <h2 className="mb-3 font-display text-2xl font-semibold">Users</h2>
        <Card className="divide-y divide-mist-200 overflow-hidden">
          {users.data?.map((u) => (
            <div key={u.id} className="flex items-center gap-3 p-4">
              <div className="min-w-0 flex-1"><div className="truncate font-semibold">{u.name} {u.role === "admin" && <Tag tone="lake">Admin</Tag>}</div><div className="truncate text-sm text-ink-500">{u.email}</div></div>
              {u.disabled && <Tag tone="sos">Disabled</Tag>}
              {u.role !== "admin" && <Button size="sm" variant={u.disabled ? "soft" : "outline"} onClick={() => setDisabled.mutate({ id: u.id, disabled: !u.disabled }, { onError: () => toast("Could not update the account.", "error") })}>{u.disabled ? "Enable" : "Disable"}</Button>}
            </div>
          ))}
        </Card>
      </section>
      {editing && <EditPlace place={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
