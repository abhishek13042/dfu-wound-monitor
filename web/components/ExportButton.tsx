"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";

// Saves the service's export as a JSON file. Photo links inside it are signed and expire, as the file says.
export function ExportButton() {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ text: string; failed: boolean } | null>(null);

  const run = async () => {
    setBusy(true);
    setNote(null);
    try {
      const body = await send<{ url_expires_in_seconds?: number }>("/account/export");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
      link.download = `dfu-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      const minutes = body.url_expires_in_seconds ? Math.round(body.url_expires_in_seconds / 60) : null;
      setNote({ text: minutes ? `Saved. Photo links in the file work for ${minutes} minutes.` : "Saved.", failed: false });
    } catch (error) {
      setNote({ text: problemText(error, messageFor), failed: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button variant="outline" disabled={isMock || busy} onClick={run}>
        <Download aria-hidden="true" />
        {busy ? "Preparing…" : "Export data"}
      </Button>
      <p role={note?.failed ? "alert" : "status"} className={note?.failed ? "mt-2 text-13 text-failure" : "mt-2 text-13 text-ink-2"}>
        {isMock ? "Export needs the service connection." : note?.text}
      </p>
    </>
  );
}
