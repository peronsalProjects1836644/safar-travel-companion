import { Phone, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { sendSos } from "@/api/hooks";
import type { Sos } from "@/api/types";
import { useToast } from "./Toast";
import { Button, Sheet } from "./ui";

export default function SosSheet({ open, onClose, pos }: { open: boolean; onClose: () => void; pos: { lat: number; lng: number } | null }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Sos | null>(null);
  const [where, setWhere] = useState(pos);
  useEffect(() => { if (open) { setResult(null); setWhere(pos); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const go = async () => {
    setBusy(true);
    try {
      let p = where;
      if (!p) p = await new Promise((res, rej) => navigator.geolocation.getCurrentPosition((g) => res({ lat: g.coords.latitude, lng: g.coords.longitude }), rej, { timeout: 12_000, enableHighAccuracy: true }));
      setWhere(p);
      setResult(await sendSos(p!));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Your location is not available. Call an emergency number instead.", "error");
    }
    setBusy(false);
  };
  return (
    <Sheet open={open} onClose={onClose} title="Get help">
      <div className="mb-5 grid grid-cols-2 gap-2">
        <a href="tel:1122" className="flex h-14 items-center justify-center gap-2 rounded-2xl bg-sos-600 font-semibold text-white"><Phone size={18} /> Rescue 1122</a>
        <a href="tel:15" className="flex h-14 items-center justify-center gap-2 rounded-2xl bg-ink-900 font-semibold text-white"><Phone size={18} /> Police 15</a>
      </div>
      {!result ? (
        <div className="space-y-3">
          <p className="text-ink-500">Safar prepares a WhatsApp message with your location for each of your emergency contacts. You tap send.</p>
          <Button variant="danger" size="lg" className="w-full" loading={busy} onClick={go}><ShieldAlert size={18} /> Prepare my SOS message</Button>
        </div>
      ) : result.contacts.length === 0 ? (
        <div className="space-y-3 rounded-2xl bg-apricot-50 p-4 text-apricot-800">
          <p>You have no emergency contacts yet. Add one so Safar can message them next time.</p>
          <Link to="/profile" onClick={onClose} className="font-semibold underline">Add contacts</Link>
          <p className="break-words border-t border-apricot-200 pt-3 text-sm">{result.message}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {result.contacts.map((c) => <a key={c.phone} href={c.whatsapp_url} target="_blank" rel="noreferrer" className="flex items-center justify-between rounded-2xl border border-mist-200 p-4 font-semibold hover:bg-mist-50">{c.name}<span className="text-sm text-lake-700">Open WhatsApp</span></a>)}
          <a href={result.map_url} target="_blank" rel="noreferrer" className="block pt-2 text-center text-sm font-semibold text-lake-700">View the location on a map</a>
        </div>
      )}
    </Sheet>
  );
}

