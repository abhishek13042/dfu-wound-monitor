"use client";

import { useState } from "react";

import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";

// Keeping a case is the one way out of retention; the choice is saved as soon as it changes (REQ-P10-S03-001).
export function KeepToggle({ caseId, initial, hours }: { caseId: string; initial: boolean; hours: number }) {
  const [keep, setKeep] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ text: string; failed: boolean } | null>(null);

  const change = async (next: boolean) => {
    setBusy(true);
    setNote(null);
    try {
      if (!isMock) await send(`/cases/${caseId}/keep`, { method: "PUT", json: { keep: next } });
      setKeep(next);
      setNote({ text: next ? "Kept. Retention leaves this case alone." : `Not kept. Photos older than ${hours} hours will be deleted.`, failed: false });
    } catch (error) {
      setNote({ text: problemText(error, messageFor), failed: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={keep}
          disabled={busy}
          onChange={(event) => void change(event.target.checked)}
          className="mt-1 size-5 flex-none accent-[var(--aubergine)]"
        />
        <span>
          <span className="block font-medium">Keep this case</span>
          <span className="block max-w-[70ch] text-sm text-ink-2">
            {hours > 0
              ? `Photos, results and uploads are deleted ${hours} hours after they are added unless the case is kept. Keep it to follow a wound over time.`
              : "Retention is off on this service, so nothing is deleted automatically."}
          </span>
        </span>
      </label>
      <p aria-live="polite" className={`mt-2 min-h-5 text-13 ${note?.failed ? "text-reject" : "text-ink-2"}`}>{note?.text}</p>
    </div>
  );
}
