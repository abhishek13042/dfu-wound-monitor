"use client";

import { signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { problemText, send } from "@/lib/api/browser";
import { isMock } from "@/lib/api/mode";
import { messageFor } from "@/lib/errors";

interface Props {
  action: string;
  title: string;
  body: string;
  word: string;
  redirect: string;
  /** The /api/v2 path that receives DELETE. */
  endpoint: string;
  /** Ends the session afterwards, for account deletion. */
  endSession?: boolean;
}

// Deletion cannot be undone, so it gets protected focus and a typed confirmation.
export function ConfirmDialog({ action, title, body, word, redirect, endpoint, endSession }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const router = useRouter();

  const confirm = async () => {
    setBusy(true);
    setProblem(null);
    try {
      if (!isMock) await send(endpoint, { method: "DELETE" });
      if (endSession && !isMock) {
        await signOut({ callbackUrl: redirect });
        return;
      }
      router.push(redirect);
      router.refresh();
    } catch (error) {
      setProblem(problemText(error, messageFor));
      setBusy(false);
    }
  };

  return (
    <>
      <Button variant="outline" className="border-failure text-failure hover:bg-failure-wash" onClick={() => dialog.current?.showModal()}>
        {action}
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby="confirm-title"
        onClose={() => {
          setTyped("");
          setProblem(null);
        }}
        className="panel m-auto w-[calc(100%-32px)] max-w-md p-5 shadow-menu backdrop:bg-aubergine/70"
      >
        <h2 id="confirm-title" className="text-lg">{title}</h2>
        <p className="mt-2 text-sm text-ink-2">{body}</p>
        <label className="mt-4 block text-sm font-medium">
          Type <span className="value">{word}</span> to confirm
          <input value={typed} onChange={(event) => setTyped(event.target.value)} autoComplete="off" className="field mt-1" />
        </label>
        {problem && <p role="alert" className="mt-3 text-sm text-failure">{problem}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => dialog.current?.close()}>Keep it</Button>
          <Button variant="destructive" disabled={typed !== word || busy} onClick={confirm}>
            {busy ? "Deleting…" : action}
          </Button>
        </div>
      </dialog>
    </>
  );
}
