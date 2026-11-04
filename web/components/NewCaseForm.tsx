"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";

export function NewCaseForm() {
  const router = useRouter();
  const [label, setLabel] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const missing = label.trim().length === 0;

  const create = async (form: HTMLFormElement) => {
    if (isMock) return router.push("/cases/c-0026");
    const field = (name: string) => (form.elements.namedItem(name) as HTMLInputElement | HTMLSelectElement).value.trim();
    setBusy(true);
    setProblem(null);
    try {
      const created = await send<{ case: { case_id: string } }>("/cases", {
        method: "POST",
        json: {
          label: label.trim(),
          identity_status: field("identity"),
          external_reference: field("reference") || null,
          ...(field("source") ? { data_source: field("source") } : {}),
        },
      });
      router.push(`/cases/${created.case.case_id}`);
    } catch (error) {
      setProblem(problemText(error, messageFor));
      setBusy(false);
    }
  };

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        setTried(true);
        if (!missing) void create(event.currentTarget);
      }}
      className="panel max-w-xl space-y-4 p-5"
    >
      <div>
        <label htmlFor="label" className="text-sm font-medium">Label</label>
        <input
          id="label"
          value={label}
          maxLength={200}
          onChange={(event) => setLabel(event.target.value)}
          aria-invalid={tried && missing}
          aria-describedby="label-help"
          className="field mt-1"
        />
        <p id="label-help" className={tried && missing ? "mt-1 text-13 text-reject" : "mt-1 text-13 text-ink-2"}>
          {tried && missing ? "Add a label so the case can be found again." : "Do not use a name or other direct identifier."}
        </p>
      </div>
      <div>
        <label htmlFor="identity" className="text-sm font-medium">Identity status</label>
        <select id="identity" name="identity" defaultValue="UNVERIFIED" aria-describedby="identity-help" className="field mt-1">
          <option value="VERIFIED">Verified</option>
          <option value="UNVERIFIED">Unverified</option>
          <option value="UNKNOWN">Unknown</option>
        </select>
        <p id="identity-help" className="mt-1 text-13 text-ink-2">Trends and comparisons are limited until the identity is verified.</p>
      </div>
      <div>
        <label htmlFor="reference" className="text-sm font-medium">External reference (optional)</label>
        <input id="reference" name="reference" maxLength={200} className="field mt-1" />
      </div>
      <div>
        <label htmlFor="source" className="text-sm font-medium">Data source (optional)</label>
        <input id="source" name="source" className="field mt-1" />
      </div>
      {problem && <p role="alert" className="text-sm text-failure">{problem}</p>}
      <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create case"}</Button>
    </form>
  );
}
