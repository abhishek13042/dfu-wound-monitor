"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ImageUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Case } from "@/lib/api";
import { cn } from "@/lib/utils";

const TYPES = ["png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"];
const LIMIT = 25 * 1024 * 1024;
const STAGES = ["Uploading the photo", "Verifying the file", "Adding to the queue"];

function problemWith(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!TYPES.includes(extension)) return `${file.name} is not a PNG, JPEG, BMP, TIFF or WebP file.`;
  if (file.size > LIMIT) return `${file.name} is larger than 25 MB.`;
  return null;
}

export function UploadForm({ cases, initialCase }: { cases: Case[]; initialCase?: string }) {
  const router = useRouter();
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<number | null>(null);

  const choose = (next: File | undefined) => {
    if (!next) return;
    const issue = problemWith(next);
    setProblem(issue);
    setFile(issue ? null : next);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !consent) return;
    STAGES.forEach((_, index) => setTimeout(() => setStage(index), index * 500));
    setTimeout(() => router.push("/analyses/c3f0b7"), STAGES.length * 500);
  };

  const busy = stage !== null;

  return (
    <form onSubmit={submit} className="grid max-w-[920px] gap-4 lg:grid-cols-2">
      <fieldset className="panel p-5 lg:col-span-2">
        <legend className="sr-only">Consent</legend>
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
            className="mt-1 size-5 flex-none accent-[var(--aubergine)]"
          />
          <span>
            <span className="block font-medium">I may upload this photo for research use.</span>
            <span className="block text-sm text-ink-2">
              It is stored for the retention period, which is a placeholder until one is set. Remove names and other identifiers from the frame first.
            </span>
          </span>
        </label>
      </fieldset>

      <div className="lg:row-span-2">
        <label
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            if (consent) choose(event.dataTransfer.files[0]);
          }}
          className={cn(
            "flex h-full min-h-56 flex-col items-center justify-center gap-2 border border-dashed border-rule-strong p-6 text-center has-[:focus-visible]:outline-2",
            consent ? "cursor-pointer bg-panel hover:border-ink" : "cursor-not-allowed",
            dragging && consent && "border-ink bg-secondary",
            problem && "border-reject",
          )}
        >
          <ImageUp className="size-6 text-ink-2" aria-hidden="true" />
          <span className="font-medium break-all">{file ? file.name : "Choose a photo or drop it here"}</span>
          <span className="text-13 text-ink-2">
            {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB, ready` : "PNG, JPEG, BMP, TIFF or WebP, up to 25 MB"}
          </span>
          <input
            type="file"
            disabled={!consent || busy}
            accept=".png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp"
            onChange={(event) => choose(event.target.files?.[0])}
            className="sr-only"
          />
        </label>
        {problem && <p role="alert" className="mt-2 text-sm text-reject">{problem}</p>}
      </div>

      <fieldset disabled={busy} className="panel space-y-3 p-5">
        <legend className="sr-only">Capture details</legend>
        <div>
          <label htmlFor="case" className="text-sm font-medium">Case</label>
          <select id="case" defaultValue={initialCase ?? cases[0]?.case_id} className="field mt-1">
            {cases.map((item) => (
              <option key={item.case_id} value={item.case_id}>{item.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="captured" className="text-sm font-medium">Captured on</label>
          <input id="captured" type="date" className="field mt-1" />
          <p className="mt-1 text-13 text-ink-2">Leave empty to use the date stored in the photo.</p>
        </div>
      </fieldset>

      <fieldset disabled={busy} className="panel space-y-3 p-5">
        <legend className="sr-only">Calibration</legend>
        <div>
          <label htmlFor="scale" className="text-sm font-medium">Pixels per millimetre (optional)</label>
          <input id="scale" type="number" min="0" step="0.01" inputMode="decimal" className="field value mt-1" />
          <p className="mt-1 text-13 text-ink-2">Without a scale, values stay in pixels and also reflect camera distance and zoom.</p>
        </div>
        <div>
          <label htmlFor="method" className="text-sm font-medium">Scale taken from</label>
          <select id="method" className="field mt-1">
            <option>Ruler in frame</option>
            <option>Printed marker</option>
            <option>Other</option>
          </select>
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
        <Button type="submit" size="lg" disabled={!consent || !file || busy}>Read this photo</Button>
        <p aria-live="polite" className="text-sm text-ink-2">
          {busy ? `${STAGES[stage]}…` : !consent ? "Confirm consent first." : !file ? "Choose a photo to continue." : "Nothing leaves your browser in this demonstration."}
        </p>
      </div>
    </form>
  );
}
