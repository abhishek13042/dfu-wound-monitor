"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ImageUp } from "lucide-react";

import { ErrorPanel } from "@/components/ErrorPanel";
import { Button } from "@/components/ui/button";
import type { Case } from "@/lib/api";
import { send, sha256 } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { ApiError } from "@/lib/errors";
import { problemWith } from "@/lib/upload";
import { cn } from "@/lib/utils";

const STAGES = ["Checking the file", "Uploading the photo", "Verifying the file", "Adding to the queue"];
const CONSENT_KEY = "dfu-upload-consent";

const SCALE_SOURCES = {
  ruler: { label: "Ruler in frame", method: "USER_ENTERED" },
  marker: { label: "Printed marker", method: "REFERENCE_MARKER" },
  other: { label: "Other", method: "USER_ENTERED" },
} as const;

function rememberedConsent(): boolean {
  try {
    return sessionStorage.getItem(CONSENT_KEY) === "1";
  } catch {
    return false;
  }
}

export function UploadForm({ cases, initialCase }: { cases: Case[]; initialCase?: string }) {
  const router = useRouter();
  const [consent, setConsent] = useState(rememberedConsent);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<number | null>(null);

  const choose = (next: File | undefined) => {
    if (!next) return;
    const issue = problemWith(next);
    setProblem(issue);
    setFailure(null);
    setFile(issue ? null : next);
  };

  const agree = (value: boolean) => {
    setConsent(value);
    try {
      if (value) sessionStorage.setItem(CONSENT_KEY, "1");
      else sessionStorage.removeItem(CONSENT_KEY);
    } catch {
      // Consent is asked again next time; nothing else depends on storage.
    }
  };

  const demonstrate = () => {
    STAGES.forEach((_, index) => setTimeout(() => setStage(index), index * 500));
    setTimeout(() => router.push("/analyses/c3f0b7"), STAGES.length * 500);
  };

  const upload = async (form: HTMLFormElement, photo: File) => {
    const field = (name: string) => (form.elements.namedItem(name) as HTMLInputElement | HTMLSelectElement).value.trim();
    setFailure(null);
    try {
      setStage(0);
      const digest = await sha256(photo);
      const caseId = field("case");
      const date = field("captured");
      // An examination ties the photo to its case and capture date, so the trend can place it.
      const examination = caseId
        ? await send<{ examination: { examination_id: string } }>(`/cases/${caseId}/examinations`, {
            method: "POST",
            json: date ? { captured_at: `${date}T12:00:00Z`, timestamp_source: "USER_ENTERED" } : { timestamp_source: "UNKNOWN" },
          })
        : undefined;

      setStage(1);
      const issued = await send<{ upload_id: string; url: string }>("/uploads", {
        method: "POST",
        json: { filename: photo.name, size_bytes: photo.size, sha256: digest },
      });
      // A relative URL is the service's own blob route, reached through the proxy; an absolute one is object storage.
      const put = await fetch(issued.url, { method: "PUT", body: photo, headers: { "Content-Type": photo.type || "application/octet-stream" } });
      if (!put.ok) throw ApiError.from(put.status, await put.json().catch(() => undefined), put.headers.get("Retry-After"));

      setStage(2);
      await send(`/uploads/${issued.upload_id}/verify`, { method: "POST" });

      setStage(3);
      const scale = Number(field("scale"));
      const source = SCALE_SOURCES[field("method") as keyof typeof SCALE_SOURCES];
      const job = await send<{ analysis_id: string }>("/analyses", {
        method: "POST",
        json: {
          upload_id: issued.upload_id,
          examination_id: examination?.examination.examination_id ?? null,
          ...(scale > 0 ? { pixels_per_mm: scale, calibration_method: source.method, calibration_source: source.label } : {}),
        },
      });
      router.push(`/analyses/${job.analysis_id}`);
    } catch (error) {
      setStage(null);
      setFailure(error instanceof ApiError ? error : ApiError.from(502));
    }
  };

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !consent) return;
    if (isMock) demonstrate();
    else void upload(event.currentTarget, file);
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
            disabled={busy}
            onChange={(event) => agree(event.target.checked)}
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
            if (consent && !busy) choose(event.dataTransfer.files[0]);
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
            name="photo"
            disabled={!consent || busy}
            accept=".png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp,image/png,image/jpeg,image/bmp,image/tiff,image/webp"
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
          <select id="case" name="case" defaultValue={initialCase ?? cases[0]?.case_id ?? ""} className="field mt-1">
            {cases.map((item) => (
              <option key={item.case_id} value={item.case_id}>{item.label ?? item.case_id}</option>
            ))}
            <option value="">Not linked to a case</option>
          </select>
        </div>
        <div>
          <label htmlFor="captured" className="text-sm font-medium">Captured on</label>
          <input id="captured" name="captured" type="date" className="field mt-1" />
          <p className="mt-1 text-13 text-ink-2">Leave empty if you do not know it. A photo without a date is left out of the trend.</p>
        </div>
      </fieldset>

      <fieldset disabled={busy} className="panel space-y-3 p-5">
        <legend className="sr-only">Calibration</legend>
        <div>
          <label htmlFor="scale" className="text-sm font-medium">Pixels per millimetre (optional)</label>
          <input id="scale" name="scale" type="number" min="0" step="0.01" inputMode="decimal" className="field value mt-1" />
          <p className="mt-1 text-13 text-ink-2">Without a scale, values stay in pixels and also reflect camera distance and zoom.</p>
        </div>
        <div>
          <label htmlFor="method" className="text-sm font-medium">Scale taken from</label>
          <select id="method" name="method" className="field mt-1">
            {Object.entries(SCALE_SOURCES).map(([key, source]) => (
              <option key={key} value={key}>{source.label}</option>
            ))}
          </select>
        </div>
      </fieldset>

      {failure && (
        <div className="lg:col-span-2">
          <ErrorPanel
            category={failure.category}
            requestId={failure.requestId}
            retryAfter={failure.retryAfter}
            details={failure.code.startsWith("HTTP_") ? undefined : `Code ${failure.code}.`}
            action={<Button type="submit" variant="outline">Try again</Button>}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
        <Button type="submit" size="lg" disabled={!consent || !file || busy}>Read this photo</Button>
        <p aria-live="polite" className="text-sm text-ink-2">
          {busy
            ? `${STAGES[stage]}…`
            : !consent
              ? "Confirm consent first."
              : !file
                ? "Choose a photo to continue."
                : isMock
                  ? "Nothing leaves your browser in this demonstration."
                  : "The photo is sent to the analysis service when you continue."}
        </p>
      </div>
    </form>
  );
}
