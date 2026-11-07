"use client";

import { useState } from "react";

import { MaskEditor } from "@/components/MaskEditor";
import { Button } from "@/components/ui/button";
import type { Correction } from "@/lib/api";
import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";
import { formatDate, formatNumber } from "@/lib/format";

type Props = {
  id: string;
  width: number;
  height: number;
  areaShare: number;
  image?: string;
  mask?: string;
  corrections: Correction[];
};

function ResearchToggle({ correction }: { correction: Correction }) {
  const [shared, setShared] = useState(correction.research_opt_in);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const change = async (next: boolean) => {
    setBusy(true);
    setFailed(null);
    try {
      if (!isMock) await send(`/corrections/${correction.correction_id}/research`, { method: "PUT", json: { opt_in: next } });
      setShared(next);
    } catch (error) {
      setFailed(problemText(error, messageFor));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <label className="inline-flex min-h-11 items-center gap-2 whitespace-nowrap text-sm">
        <input
          type="checkbox"
          checked={shared}
          disabled={busy}
          onChange={(event) => void change(event.target.checked)}
          className="size-5 flex-none accent-[var(--aubergine)]"
        />
        Shared for research
      </label>
      {failed && <p role="alert" className="text-13 text-reject">{failed}</p>}
    </>
  );
}

function areaText(correction: Correction) {
  const { physical, pixel, status } = correction.measurement;
  if (status === "EMPTY") return "Empty outline";
  return physical ? `${formatNumber(physical.area_mm2, 1)} mm²` : `${formatNumber(pixel.area_px, 0)} px²`;
}

// REQ-P09-S03-001 to -005: the editor, and every saved version with its own research choice.
export function Corrections({ corrections, ...editor }: Props) {
  const [open, setOpen] = useState(false);
  const latest = corrections.at(-1);

  return (
    <section aria-labelledby="correct" className="panel mt-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="correct" className="text-lg">Correct the outline</h2>
        {!open && (
          <Button type="button" variant="outline" onClick={() => setOpen(true)}>
            {latest ? "Correct it again" : "Correct the outline"}
          </Button>
        )}
      </div>
      <p className="mt-1 max-w-[62ch] text-sm text-ink-2">
        If the model&apos;s outline misses part of the wound or takes in healthy skin, redraw it. The service measures your
        outline with the same method. Trends then use your latest version and mark the value as corrected.
      </p>

      {open && (
        <div className="mt-4">
          <MaskEditor {...editor} />
          <Button type="button" variant="ghost" className="mt-2" onClick={() => setOpen(false)}>Close the editor</Button>
        </div>
      )}

      {corrections.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Saved corrections, oldest first</caption>
            <thead>
              <tr className="border-b border-rule text-left text-13 text-ink-2">
                <th scope="col" className="py-2 pr-4 font-medium">Version</th>
                <th scope="col" className="py-2 pr-4 font-medium">Saved</th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">Area</th>
                <th scope="col" className="py-2 font-medium">Research</th>
              </tr>
            </thead>
            <tbody>
              {corrections.map((correction) => (
                <tr key={correction.correction_id} className="border-b border-rule last:border-0">
                  <td className="py-2 pr-4">
                    <span className="value">{correction.version}</span>
                    {correction === latest && <span className="ml-2 text-13 text-ink-2">used in trends</span>}
                  </td>
                  <td className="py-2 pr-4">{formatDate(correction.created_at)}</td>
                  <td className="value py-2 pr-4 text-right">{areaText(correction)}</td>
                  <td className="py-2"><ResearchToggle correction={correction} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
